"""Recursive, structure-aware text chunking.

Splits on the coarsest boundary that works (paragraph -> line -> sentence -> word),
then greedily merges pieces up to the target size with a small overlap so a fact that
straddles a boundary still appears whole in at least one chunk.

Chunks never cross a page boundary: that keeps page citations exact, at the cost of
occasionally splitting a paragraph that continues onto the next page.
"""

from app.models import Chunk, Page

CHARS_PER_TOKEN = 4  # rough average for English; good enough for sizing, not billing
SEPARATORS = ("\n\n", "\n", ". ", " ")


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def chunk_pages(pages: list[Page], size_tokens: int, overlap_tokens: int) -> list[Chunk]:
    if overlap_tokens >= size_tokens:
        raise ValueError("overlap must be smaller than chunk size")
    size, overlap = size_tokens * CHARS_PER_TOKEN, overlap_tokens * CHARS_PER_TOKEN

    chunks: list[Chunk] = []
    for page in pages:
        for text in split_text(page.text, size, overlap):
            chunks.append(
                Chunk(
                    index=len(chunks),
                    text=text,
                    page_number=page.number,
                    token_count=estimate_tokens(text),
                )
            )
    return chunks


def split_text(text: str, size: int, overlap: int) -> list[str]:
    """Split text into pieces of at most `size` chars with ~`overlap` chars shared between neighbours."""
    pieces = _split_recursive(text, SEPARATORS, size)

    chunks: list[str] = []
    window: list[str] = []
    window_len = 0
    for piece in pieces:
        if window and window_len + len(piece) > size:
            chunks.append("".join(window).strip())
            # Keep a tail of the previous chunk as overlap for the next one.
            while window and (window_len > overlap or window_len + len(piece) > size):
                window_len -= len(window.pop(0))
        window.append(piece)
        window_len += len(piece)
    if window:
        chunks.append("".join(window).strip())

    return [c for c in chunks if c]


def _split_recursive(text: str, separators: tuple[str, ...], size: int) -> list[str]:
    if len(text) <= size:
        return [text]

    sep = next((s for s in separators if s in text), None)
    if sep is None:  # no natural boundary left: hard cut
        return [text[i : i + size] for i in range(0, len(text), size)]

    parts = text.split(sep)
    # Re-attach the separator so joining pieces reproduces the original text.
    parts = [p + sep for p in parts[:-1]] + [parts[-1]]
    remaining = separators[separators.index(sep) + 1 :]

    out: list[str] = []
    for part in parts:
        if len(part) <= size:
            out.append(part)
        else:
            out.extend(_split_recursive(part, remaining, size))
    return out
