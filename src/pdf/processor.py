"""PDF inspection and high-resolution page rendering."""

from dataclasses import dataclass
from pathlib import Path

import pymupdf
from PIL import Image


class PDFProcessingError(ValueError):
    """Raised when a PDF cannot be inspected or rendered."""


@dataclass(frozen=True)
class PDFDocumentInfo:
    path: Path
    page_count: int
    pdf_kind: str


def inspect_pdf(pdf_path: str | Path) -> PDFDocumentInfo:
    path = Path(pdf_path)
    if path.suffix.lower() != ".pdf":
        raise PDFProcessingError(f"Expected a .pdf file, got: {path.name}")
    if not path.is_file():
        raise PDFProcessingError(f"PDF does not exist: {path}")

    try:
        with pymupdf.open(path) as document:
            if document.page_count == 0:
                raise PDFProcessingError(f"PDF has no pages: {path}")
            page = document[0]
            image_count = len(page.get_images(full=True))
            text_span_count = len(page.get_text("dict").get("blocks", []))
            pdf_kind = "raster" if image_count and not text_span_count else "vector-or-mixed"
            return PDFDocumentInfo(path, document.page_count, pdf_kind)
    except pymupdf.FileDataError as error:
        raise PDFProcessingError(f"Unable to open PDF: {path}") from error


def render_page(pdf_path: str | Path, page_number: int, output_path: str | Path, dpi: int = 300) -> Path:
    """Render a one-based page number to a lossless PNG."""
    if dpi <= 0:
        raise ValueError("dpi must be positive")
    info = inspect_pdf(pdf_path)
    if not 1 <= page_number <= info.page_count:
        raise PDFProcessingError(f"Page {page_number} is outside 1..{info.page_count}")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    scale = dpi / 72.0
    try:
        with pymupdf.open(info.path) as document:
            page = document[page_number - 1]
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            image.save(output, format="PNG", optimize=False)
    except (pymupdf.FitzError, OSError) as error:
        raise PDFProcessingError(f"Unable to render page {page_number}: {info.path}") from error
    return output
