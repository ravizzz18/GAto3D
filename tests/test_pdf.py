from pathlib import Path

import fitz
import pytest
from PIL import Image

from src.pdf.processor import PDFProcessingError, inspect_pdf, render_page


def create_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=200, height=100)
    page.insert_text((20, 50), "SHIP GA TEST")
    document.save(path)
    document.close()


def test_inspect_and_render_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "drawing.pdf"
    create_pdf(pdf_path)
    info = inspect_pdf(pdf_path)
    assert info.page_count == 1
    assert info.pdf_kind == "vector-or-mixed"
    output = render_page(pdf_path, 1, tmp_path / "rendered.png", dpi=144)
    with Image.open(output) as image:
        assert image.size == (400, 200)


def test_render_rejects_invalid_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "drawing.pdf"
    create_pdf(pdf_path)
    with pytest.raises(PDFProcessingError):
        render_page(pdf_path, 2, tmp_path / "rendered.png")
