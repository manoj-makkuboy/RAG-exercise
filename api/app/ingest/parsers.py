"""Turn uploaded bytes into a list of Pages."""

import re

import pymupdf

from app.models import Page

SUPPORTED_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}


class UnsupportedFileType(ValueError):
    pass


class EmptyDocument(ValueError):
    pass


def media_type_for(filename: str) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_TYPES:
        allowed = ", ".join(sorted(SUPPORTED_TYPES))
        raise UnsupportedFileType(f"Unsupported file type '{ext or filename}'. Allowed: {allowed}")
    return SUPPORTED_TYPES[ext]


def parse(filename: str, data: bytes) -> list[Page]:
    media_type = media_type_for(filename)
    if media_type == "application/pdf":
        pages = _parse_pdf(data)
    else:
        pages = [Page(text=_clean(data.decode("utf-8", errors="replace")), number=None)]

    pages = [p for p in pages if p.text]
    if not pages:
        raise EmptyDocument(
            f"No extractable text in '{filename}'. Scanned PDFs need OCR, which is not supported yet."
        )
    return pages


def _parse_pdf(data: bytes) -> list[Page]:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [
            Page(text=_clean(page.get_text("text")), number=i + 1) for i, page in enumerate(doc)
        ]


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+\n", "\n", text)  # trailing whitespace
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # re-join words hyphenated across lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
