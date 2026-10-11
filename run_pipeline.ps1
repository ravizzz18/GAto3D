[CmdletBinding()]
param(
    [string]$InputPdf = "data\raw\sample1.pdf",
    [int]$Page = 1
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Write-StageLog {
    param(
        [string]$Message,
        [string]$LogPath,
        [string]$Level = "INFO"
    )

    $line = "[{0}] {1} {2}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Level, $Message
    Write-Host $line
    Add-Content -LiteralPath $LogPath -Value $line
}

function Invoke-PipelineCommand {
    param(
        [string]$Name,
        [string]$Executable,
        [string[]]$Arguments,
        [string]$LogPath
    )

    Write-StageLog "Starting ${Name}: $Executable $($Arguments -join ' ')" $LogPath
    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -Wait -PassThru `
        -NoNewWindow -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $exitCode = $process.ExitCode
    if (Test-Path -LiteralPath $stdoutPath) {
        Get-Content -LiteralPath $stdoutPath | ForEach-Object {
            Write-Host $_
            Add-Content -LiteralPath $LogPath -Value $_
        }
    }
    if (Test-Path -LiteralPath $stderrPath) {
        Get-Content -LiteralPath $stderrPath | ForEach-Object {
            Write-Host $_
            Add-Content -LiteralPath $LogPath -Value $_
        }
    }
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    if ($exitCode -ne 0) {
        Write-StageLog "$Name failed with exit code $exitCode." $LogPath "ERROR"
        return $false
    }

    Write-StageLog "$Name completed successfully." $LogPath
    return $true
}

function Add-Status {
    param(
        [System.Collections.ArrayList]$Statuses,
        [string]$Stage,
        [string]$Status,
        [string]$OutputPath,
        [string]$Details
    )

    [void]$Statuses.Add([pscustomobject]@{
        Stage = $Stage
        Status = $Status
        OutputPath = $OutputPath
        Details = $Details
    })
}

function Require-Path {
    param(
        [string]$Path,
        [string]$Description,
        [string]$LogPath
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Write-StageLog "$Description is missing: $Path" $LogPath "ERROR"
        return $false
    }

    Write-StageLog "$Description found: $Path" $LogPath
    return $true
}

$ProjectRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path
Set-Location -LiteralPath $ProjectRoot

$RunId = Get-Date -Format "yyyyMMdd-HHmmss"
$RunRoot = Join-Path $ProjectRoot ("outputs\runs\" + $RunId)
$suffix = 1
while (Test-Path -LiteralPath $RunRoot) {
    $RunId = "{0}-{1}" -f (Get-Date -Format "yyyyMMdd-HHmmss"), $suffix
    $RunRoot = Join-Path $ProjectRoot ("outputs\runs\" + $RunId)
    $suffix++
}

$stage1Dir = Join-Path $RunRoot "stage1_input"
$stage2Dir = Join-Path $RunRoot "stage2_preprocessing"
$stage3Dir = Join-Path $RunRoot "stage3_drawing_analysis"
$stage4Dir = Join-Path $RunRoot "stage4_ocr"
$evaluationDir = Join-Path $RunRoot "stage4_evaluation"
$testsDir = Join-Path $RunRoot "tests"
$logPath = Join-Path $RunRoot "pipeline.log"
$summaryPath = Join-Path $RunRoot "run_summary.txt"

New-Item -ItemType Directory -Path $stage1Dir, $stage2Dir, $stage3Dir, $stage4Dir, $evaluationDir, $testsDir | Out-Null
New-Item -ItemType File -Path $logPath -Force | Out-Null
$statuses = New-Object System.Collections.ArrayList

$summaryHeader = @(
    "GAto3D pipeline run summary",
    "Run ID: $RunId",
    "Project root: $ProjectRoot",
    "Started: $(Get-Date -Format o)",
    ""
)
Set-Content -LiteralPath $summaryPath -Value $summaryHeader

try {
    Write-StageLog "Project root: $ProjectRoot" $logPath
    Write-StageLog "Run root: $RunRoot" $logPath

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
    }
    if (-not $pythonCommand) {
        Write-StageLog "Python was not found on PATH." $logPath "ERROR"
        Add-Status $statuses "Environment checks" "FAILED" $RunRoot "Python is required."
    }
    else {
        $python = $pythonCommand.Source
        Write-StageLog "Using Python: $python" $logPath
        $dependencyCheck = @(
            "fitz",
            "cv2",
            "numpy",
            "PIL",
            "pytesseract",
            "pytest"
        )
        $dependencyCode = "import " + ($dependencyCheck -join ",")
        & $python -c $dependencyCode 2>&1 | Tee-Object -FilePath $logPath -Append
        $dependencyOk = ($LASTEXITCODE -eq 0)
        if (-not $dependencyOk) {
            Write-StageLog "One or more Python dependencies are unavailable." $logPath "ERROR"
            Add-Status $statuses "Environment checks" "FAILED" $RunRoot "Required Python dependency check failed."
        }
        else {
            Write-StageLog "Required Python dependencies are available." $logPath
        }

        $tesseractCandidates = @(
            (Join-Path ${env:ProgramFiles} "Tesseract-OCR\tesseract.exe"),
            (Join-Path ${env:ProgramFiles(x86)} "Tesseract-OCR\tesseract.exe"),
            (Join-Path $ProjectRoot ".venv\Lib\site-packages\tesseract.exe")
        )
        $tesseractCommand = Get-Command tesseract -ErrorAction SilentlyContinue
        $tesseractPath = $null
        if ($tesseractCommand) {
            $tesseractPath = $tesseractCommand.Source
        }
        else {
            foreach ($candidate in $tesseractCandidates) {
                if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
                    $tesseractPath = $candidate
                    break
                }
            }
        }
        if ($tesseractPath) {
            $tesseractDirectory = Split-Path -Parent $tesseractPath
            $env:Path = "$tesseractDirectory;$env:Path"
            Write-StageLog "Using Tesseract: $tesseractPath" $logPath
            & $tesseractPath --version 2>&1 | Tee-Object -FilePath $logPath -Append
            $tesseractAvailable = ($LASTEXITCODE -eq 0)
        }
        else {
            $tesseractAvailable = $false
            Write-StageLog "Tesseract was not found. OCR will be skipped." $logPath "WARNING"
        }

        $inputPath = Join-Path $ProjectRoot $InputPdf
        $inputAvailable = Require-Path $inputPath "Input PDF" $logPath
        $configPath = Join-Path $ProjectRoot "config\default.json"
        $configAvailable = Require-Path $configPath "Configuration" $logPath
        $environmentOk = ($dependencyOk -and $inputAvailable -and $configAvailable)
        if (-not $environmentOk) {
            Add-Status $statuses "Environment checks" "FAILED" $RunRoot "Python, input, configuration, or dependency checks failed."
        }
        else {
            Copy-Item -LiteralPath $inputPath -Destination (Join-Path $stage1Dir (Split-Path -Leaf $inputPath))
            Add-Status $statuses "Environment checks" "SUCCESS" $RunRoot "Python, dependencies, input PDF, configuration, and environment checks passed."
        }

        $stage2RunDir = Join-Path $stage2Dir ("runs\" + $RunId)
        $stage2Report = Join-Path $stage2Dir "comparison_report.json"
        if ($environmentOk) {
            $stage2Args = @(
                "main.py", $inputPath, "--page", $Page,
                "--config", $configPath, "--output-dir", $stage2Dir,
                "--report", $stage2Report, "--run-id", $RunId
            )
            $stage2Ok = Invoke-PipelineCommand "PDF processing and preprocessing" $python $stage2Args $logPath
            $stage2Expected = @("original.png", "grayscale.png", "denoised.png", "enhanced.png", "thresholded.png", "deskewed.png", "final.png", "run_manifest.json")
            $stage2Missing = @($stage2Expected | Where-Object { -not (Test-Path -LiteralPath (Join-Path $stage2RunDir $_) -PathType Leaf) })
            if ($stage2Ok -and $stage2Missing.Count -eq 0 -and (Test-Path -LiteralPath $stage2Report -PathType Leaf)) {
                Add-Status $statuses "PDF processing and preprocessing" "SUCCESS" $stage2RunDir "Images, manifest, and comparison report were created."
            }
            else {
                $detail = "Required output missing: " + ($stage2Missing -join ", ")
                Add-Status $statuses "PDF processing and preprocessing" "FAILED" $stage2RunDir $detail
            }
        }
        else {
            $stage2Ok = $false
            Add-Status $statuses "PDF processing and preprocessing" "SKIPPED" $stage2Dir "Skipped because environment checks failed."
        }

        $stage3RunDir = Join-Path $stage3Dir ("runs\" + $RunId)
        if ($stage2Ok) {
            $stage3Args = @("analyze.py", $stage2RunDir, "--config", $configPath, "--output-dir", $stage3Dir, "--run-id", $RunId)
            $stage3Ok = Invoke-PipelineCommand "Drawing analysis" $python $stage3Args $logPath
            $stage3Expected = @("lines.png", "contours.png", "text_regions.png", "drawing_regions.png", "overlay.png", "report.json", "run_manifest.json")
            $stage3Missing = @($stage3Expected | Where-Object { -not (Test-Path -LiteralPath (Join-Path $stage3RunDir $_) -PathType Leaf) })
            if ($stage3Ok -and $stage3Missing.Count -eq 0) {
                Add-Status $statuses "Drawing analysis" "SUCCESS" $stage3RunDir "Analysis visualizations, report, and manifest were created."
            }
            else {
                Add-Status $statuses "Drawing analysis" "FAILED" $stage3RunDir ("Required output missing: " + ($stage3Missing -join ", "))
            }
        }
        else {
            $stage3Ok = $false
            Add-Status $statuses "Drawing analysis" "SKIPPED" $stage3Dir "Skipped because preprocessing failed."
        }

        $stage4RunDir = Join-Path $stage4Dir ("runs\" + $RunId)
        if ($stage3Ok -and $tesseractAvailable) {
            $stage4Args = @("ocr.py", $stage2RunDir, "--config", $configPath, "--output-dir", $stage4Dir, "--run-id", $RunId)
            $stage4Ok = Invoke-PipelineCommand "OCR" $python $stage4Args $logPath
            $stage4Expected = @("extracted_text.txt", "ocr_results.json", "ocr_visualization.png", "run_manifest.json")
            $stage4Missing = @($stage4Expected | Where-Object { -not (Test-Path -LiteralPath (Join-Path $stage4RunDir $_) -PathType Leaf) })
            if ($stage4Ok -and $stage4Missing.Count -eq 0) {
                Add-Status $statuses "OCR" "SUCCESS" $stage4RunDir "OCR text, JSON, visualization, and manifest were created."
            }
            else {
                Add-Status $statuses "OCR" "FAILED" $stage4RunDir ("Required output missing: " + ($stage4Missing -join ", "))
            }
        }
        else {
            $stage4Ok = $false
            $reason = "Skipped because drawing analysis failed."
            if (-not $tesseractAvailable) { $reason = "Skipped because Tesseract is unavailable." }
            Add-Status $statuses "OCR" "SKIPPED" $stage4Dir $reason
        }

        $groundTruthCandidates = @(
            (Join-Path $ProjectRoot "outputs\ocr\ground_truth\sample1_annotations.json"),
            (Join-Path $ProjectRoot "data\annotations\sample1_annotations.json"),
            (Join-Path $ProjectRoot "data\annotations\sample1.json")
        )
        $groundTruth = $groundTruthCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
        $evaluationReport = Join-Path $evaluationDir "report.json"
        if ($stage4Ok -and $groundTruth) {
            $evaluationArgs = @("evaluate_ocr.py", $groundTruth, (Join-Path $stage4RunDir "ocr_results.json"), "--output", $evaluationReport)
            $evaluationOk = Invoke-PipelineCommand "OCR evaluation" $python $evaluationArgs $logPath
            if ($evaluationOk -and (Test-Path -LiteralPath $evaluationReport -PathType Leaf)) {
                Add-Status $statuses "OCR evaluation" "SUCCESS" $evaluationReport "Evaluation report was created."
            }
            else {
                Add-Status $statuses "OCR evaluation" "FAILED" $evaluationDir "Evaluation command failed or report was not created."
            }
        }
        elseif (-not $groundTruth) {
            $evaluationOk = $false
            Add-Status $statuses "OCR evaluation" "SKIPPED" $evaluationDir "No ground-truth annotation file was found."
        }
        else {
            $evaluationOk = $false
            Add-Status $statuses "OCR evaluation" "SKIPPED" $evaluationDir "Skipped because OCR did not succeed."
        }

        $testLog = Join-Path $testsDir "pytest.log"
        $testsOk = Invoke-PipelineCommand "Automated tests" $python @("-m", "pytest") $testLog
        if ($testsOk) {
            Add-Status $statuses "Automated tests" "SUCCESS" $testsDir "pytest completed successfully; see pytest.log."
        }
        else {
            Add-Status $statuses "Automated tests" "FAILED" $testsDir "pytest failed; see pytest.log."
        }
    }
}
catch {
    Write-StageLog $_.Exception.Message $logPath "ERROR"
    Add-Status $statuses "Pipeline execution" "FAILED" $RunRoot $_.Exception.Message
}

$summaryLines = @(
    "GAto3D pipeline run summary",
    "Run ID: $RunId",
    "Project root: $ProjectRoot",
    "Run root: $RunRoot",
    "Completed: $(Get-Date -Format o)",
    ""
)
foreach ($status in $statuses) {
    $summaryLines += "{0}: {1}" -f $status.Stage, $status.Status
    $summaryLines += "  Output: $($status.OutputPath)"
    $summaryLines += "  Details: $($status.Details)"
}
$summaryLines += ""
$summaryLines += "Pipeline log: $logPath"
Set-Content -LiteralPath $summaryPath -Value $summaryLines
Get-Content -LiteralPath $summaryPath

$requiredFailures = @($statuses | Where-Object {
    $_.Status -eq "FAILED" -and $_.Stage -ne "OCR evaluation" -and $_.Stage -ne "Automated tests"
})
if ($requiredFailures.Count -gt 0) {
    exit 1
}
if (@($statuses | Where-Object { $_.Stage -eq "Automated tests" -and $_.Status -eq "FAILED" }).Count -gt 0) {
    exit 1
}
exit 0
