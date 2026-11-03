"""Query-time retrieval: embed the query, run hybrid search."""

from typing import Protocol
from uuid import UUID

from app.ingest.embedder import Embedder
from app.models import RetrievedChunk
from app.store import Store


class Retriever(Protocol):
    def search(
        self, query: str, top_k: int, document_ids: list[UUID] | None
    ) -> list[RetrievedChunk]: ...


class HybridRetriever:
    def __init__(self, store: Store, embedder: Embedder, candidates: int):
        self._store = store
        self._embedder = embedder
        self._candidates = candidates

    def search(
        self, query: str, top_k: int, document_ids: list[UUID] | None
    ) -> list[RetrievedChunk]:
        return self._store.hybrid_search(
            query_text=query,
            query_embedding=self._embedder.embed_query(query),
            candidates=max(self._candidates, top_k),
            top_k=top_k,
            document_ids=document_ids,
        )
