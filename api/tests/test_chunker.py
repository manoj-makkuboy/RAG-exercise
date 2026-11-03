import itertools

import pytest

from app.ingest.chunker import chunk_pages, split_text
from app.models import Page


def test_short_text_is_a_single_chunk():
    assert split_text("Hello world.", size=100, overlap=10) == ["Hello world."]


def test_chunks_respect_max_size():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 40 for i in range(20))
    chunks = split_text(text, size=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 300 for c in chunks)


def test_neighbouring_chunks_overlap():
    sentences = [f"Sentence number {i} is here." for i in range(60)]
    chunks = split_text(" ".join(sentences), size=200, overlap=60)
    for prev, nxt in itertools.pairwise(chunks):
        last_words = prev.split()[-3:]
        assert " ".join(last_words) in nxt, "expected tail of previous chunk to be repeated"


def test_prefers_paragraph_boundaries():
    text = "First paragraph about cats.\n\nSecond paragraph about dogs."
    chunks = split_text(text, size=35, overlap=0)
    assert chunks == ["First paragraph about cats.", "Second paragraph about dogs."]


def test_hard_cuts_text_without_separators():
    chunks = split_text("x" * 250, size=100, overlap=0)
    assert [len(c) for c in chunks] == [100, 100, 50]


def test_chunk_pages_keeps_page_numbers_and_global_index():
    pages = [Page("Alpha " * 200, 1), Page("Beta " * 200, 2)]
    chunks = chunk_pages(pages, size_tokens=100, overlap_tokens=10)
    assert {c.page_number for c in chunks} == {1, 2}
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert all("Beta" not in c.text for c in chunks if c.page_number == 1)


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        chunk_pages([Page("text", None)], size_tokens=10, overlap_tokens=10)
