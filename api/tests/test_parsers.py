import pymupdf
import pytest

from app.ingest.parsers import EmptyDocument, UnsupportedFileType, parse


def _make_pdf(pages: list[str]) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_parses_pdf_page_by_page():
    pages = parse("report.pdf", _make_pdf(["Page one text", "Page two text"]))
    assert [(p.number, p.text) for p in pages] == [(1, "Page one text"), (2, "Page two text")]


def test_parses_text_and_markdown():
    assert parse("notes.txt", b"hello\r\nworld")[0].text == "hello\nworld"
    md = parse("README.md", b"# Title\n\n\n\n\nBody")[0]
    assert md.number is None
    assert md.text == "# Title\n\nBody"


def test_rejects_unsupported_types():
    with pytest.raises(UnsupportedFileType):
        parse("image.png", b"\x89PNG")


def test_rejects_documents_without_text():
    with pytest.raises(EmptyDocument):
        parse("blank.pdf", _make_pdf([""]))
    with pytest.raises(EmptyDocument):
        parse("empty.txt", b"   \n  ")
