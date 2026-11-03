"""All SQL lives here. Services depend on this module, never on raw queries."""

import json
from collections.abc import Sequence
from uuid import UUID, uuid4

import numpy as np
from psycopg_pool import ConnectionPool

from app.models import Chunk, DocumentOut, RetrievedChunk

# Reciprocal Rank Fusion constant. 60 is the value from the original RRF paper and the
# common default; it damps the influence of any single list's top ranks.
RRF_K = 60


class Store:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    # --- documents -----------------------------------------------------------

    def find_document_by_hash(self, sha256: str) -> DocumentOut | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT id, filename, media_type, page_count, chunk_count, created_at "
                "FROM documents WHERE sha256 = %s",
                (sha256,),
            ).fetchone()
        return DocumentOut(**row) if row else None

    def insert_document(
        self,
        *,
        filename: str,
        media_type: str,
        sha256: str,
        page_count: int,
        chunks: Sequence[Chunk],
        embeddings: Sequence[np.ndarray],
    ) -> DocumentOut:
        doc_id = uuid4()
        with self._pool.connection() as conn, conn.transaction():
            row = conn.execute(
                "INSERT INTO documents (id, filename, media_type, sha256, page_count, chunk_count) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "RETURNING id, filename, media_type, page_count, chunk_count, created_at",
                (doc_id, filename, media_type, sha256, page_count, len(chunks)),
            ).fetchone()
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO chunks "
                    "(id, document_id, chunk_index, page_number, content, token_count, embedding) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    [
                        (uuid4(), doc_id, c.index, c.page_number, c.text, c.token_count, e)
                        for c, e in zip(chunks, embeddings, strict=True)
                    ],
                )
        return DocumentOut(**row)

    def list_documents(self) -> list[DocumentOut]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                "SELECT id, filename, media_type, page_count, chunk_count, created_at "
                "FROM documents ORDER BY created_at DESC"
            ).fetchall()
        return [DocumentOut(**r) for r in rows]

    def delete_document(self, doc_id: UUID) -> bool:
        with self._pool.connection() as conn:
            cur = conn.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
            return cur.rowcount > 0

    # --- retrieval -----------------------------------------------------------

    def hybrid_search(
        self,
        *,
        query_text: str,
        query_embedding: np.ndarray,
        candidates: int,
        top_k: int,
        document_ids: list[UUID] | None,
    ) -> list[RetrievedChunk]:
        """Dense (pgvector cosine) + sparse (Postgres full-text) search fused with RRF.

        Dense search catches paraphrases; full-text catches exact terms the embedding
        model blurs (product codes, names, acronyms). RRF merges the two rankings without
        having to calibrate their very different score scales.
        """
        doc_filter = "AND c.document_id = ANY(%(doc_ids)s)" if document_ids else ""
        sql = f"""
            WITH dense AS (
                SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> %(qvec)s) AS rnk
                FROM chunks c
                WHERE true {doc_filter}
                ORDER BY c.embedding <=> %(qvec)s
                LIMIT %(candidates)s
            ),
            sparse AS (
                SELECT c.id,
                       row_number() OVER (ORDER BY ts_rank_cd(c.tsv, q) DESC) AS rnk
                FROM chunks c, websearch_to_tsquery('english', %(qtext)s) q
                WHERE c.tsv @@ q {doc_filter}
                ORDER BY ts_rank_cd(c.tsv, q) DESC
                LIMIT %(candidates)s
            ),
            fused AS (
                SELECT id,
                       COALESCE(1.0 / (%(rrf_k)s + dense.rnk), 0)
                     + COALESCE(1.0 / (%(rrf_k)s + sparse.rnk), 0) AS score
                FROM dense FULL OUTER JOIN sparse USING (id)
            )
            SELECT c.id AS chunk_id, c.document_id, d.filename, c.page_number, c.content,
                   1 - (c.embedding <=> %(qvec)s) AS similarity, fused.score
            FROM fused
            JOIN chunks c ON c.id = fused.id
            JOIN documents d ON d.id = c.document_id
            ORDER BY fused.score DESC
            LIMIT %(top_k)s
        """
        params = {
            "qvec": query_embedding,
            "qtext": query_text,
            "candidates": candidates,
            "top_k": top_k,
            "rrf_k": RRF_K,
            "doc_ids": document_ids,
        }
        with self._pool.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            RetrievedChunk(
                **{**r, "similarity": float(r["similarity"]), "score": float(r["score"])}
            )
            for r in rows
        ]

    # --- observability -------------------------------------------------------

    def insert_trace(self, trace: dict) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                "INSERT INTO query_traces (id, question, outcome, retrieved, answer, model, "
                "input_tokens, output_tokens, timings_ms) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    trace["id"],
                    trace["question"],
                    trace["outcome"],
                    json.dumps(trace["retrieved"]),
                    trace.get("answer"),
                    trace.get("model"),
                    trace.get("input_tokens"),
                    trace.get("output_tokens"),
                    json.dumps(trace["timings_ms"]),
                ),
            )

    def recent_traces(self, limit: int = 50) -> list[dict]:
        with self._pool.connection() as conn:
            return conn.execute(
                "SELECT * FROM query_traces ORDER BY created_at DESC LIMIT %s", (limit,)
            ).fetchall()
