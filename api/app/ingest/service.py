"""Ingestion pipeline: bytes -> pages -> chunks -> embeddings -> Postgres."""

import hashlib
import logging
import time

from app.ingest import parsers
from app.ingest.chunker import chunk_pages
from app.ingest.embedder import Embedder
from app.models import DocumentOut
from app.store import Store

log = logging.getLogger(__name__)


class FileTooLarge(ValueError):
    pass


class IngestionService:
    def __init__(
        self,
        store: Store,
        embedder: Embedder,
        chunk_size_tokens: int,
        chunk_overlap_tokens: int,
        max_upload_bytes: int,
    ):
        self._store = store
        self._embedder = embedder
        self._chunk_size = chunk_size_tokens
        self._chunk_overlap = chunk_overlap_tokens
        self._max_bytes = max_upload_bytes

    def ingest(self, filename: str, data: bytes) -> tuple[DocumentOut, bool]:
        """Returns (document, created). Re-uploading identical bytes is a no-op."""
        if len(data) > self._max_bytes:
            raise FileTooLarge(f"File exceeds {self._max_bytes // (1024 * 1024)} MB limit.")
        media_type = parsers.media_type_for(filename)

        sha256 = hashlib.sha256(data).hexdigest()
        if existing := self._store.find_document_by_hash(sha256):
            log.info(
                "ingest.duplicate",
                extra={"doc_filename": filename, "document_id": str(existing.id)},
            )
            return existing, False

        t0 = time.perf_counter()
        pages = parsers.parse(filename, data)
        chunks = chunk_pages(pages, self._chunk_size, self._chunk_overlap)
        # Prefix the filename when embedding (not when storing): a cheap form of
        # "contextual chunk headers" that helps queries like "what does the handbook say".
        embeddings = self._embedder.embed_documents([f"{filename}\n\n{c.text}" for c in chunks])
        doc = self._store.insert_document(
            filename=filename,
            media_type=media_type,
            sha256=sha256,
            page_count=len(pages),
            chunks=chunks,
            embeddings=embeddings,
        )
        log.info(
            "ingest.done",
            extra={
                "document_id": str(doc.id),
                "doc_filename": filename,
                "pages": len(pages),
                "chunks": len(chunks),
                "ms": round((time.perf_counter() - t0) * 1000),
            },
        )
        return doc, True
