import shutil

import pypdfium2 as pdfium
import pytesseract

from app.core.config import settings

MAX_PAGES = 5        # a CV is rarely longer
TARGET_DPI = 200
MAX_SIDE_PX = 3000   # caps memory use on oversized pages


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def ocr_pdf(data: bytes) -> str:
    pdf = pdfium.PdfDocument(data)
    try:
        parts = []
        for i in range(min(len(pdf), MAX_PAGES)):
            page = pdf[i]
            width, height = page.get_size()
            scale = min(TARGET_DPI / 72, MAX_SIDE_PX / max(width, height))
            image = page.render(scale=scale).to_pil().convert("L")
            parts.append(pytesseract.image_to_string(image, lang=settings.ocr_langs, timeout=60))
        return "\n".join(parts).strip()
    finally:
        pdf.close()
