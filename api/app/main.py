"""FastAPI app factory. Run with `uvicorn app.main:create_app --factory`.

Components are built once at startup and hung off app.state; tests pass their own
(fake) components into create_app instead."""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.chat import ChatService
from app.config import Settings, get_settings
from app.generation.llm import LLM
from app.ingest.embedder import Embedder
from app.ingest.service import IngestionService
from app.logging_setup import configure_logging, request_id_var
from app.retrieval.retriever import HybridRetriever
from app.routes import chat, documents
from app.store import Store

log = logging.getLogger(__name__)


@dataclass
class Components:
    store: Store
    embedder: Embedder
    llm: LLM


def build_components(settings: Settings) -> Components:
    from app.db import create_pool, run_migrations
    from app.generation.llm import GeminiLLM
    from app.ingest.embedder import FastEmbedEmbedder

    pool = create_pool(settings.database_url)
    run_migrations(pool)
    return Components(
        store=Store(pool),
        embedder=FastEmbedEmbedder(settings.embedding_model, settings.embedding_dim),
        llm=GeminiLLM(
            api_key=settings.gemini_api_key,
            model=settings.llm_model,
            thinking_level=settings.llm_thinking_level,
            max_tokens=settings.llm_max_tokens,
        ),
    )


def create_app(settings: Settings | None = None, components: Components | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        c = components or build_components(settings)
        retriever = HybridRetriever(c.store, c.embedder, settings.retrieval_candidates)
        app.state.settings = settings
        app.state.store = c.store
        app.state.retriever = retriever
        app.state.ingestion = IngestionService(
            c.store,
            c.embedder,
            settings.chunk_size_tokens,
            settings.chunk_overlap_tokens,
            settings.max_upload_mb * 1024 * 1024,
        )
        app.state.chat = ChatService(retriever, c.llm, settings, traces=c.store)
        log.info(
            "app.ready",
            extra={"llm_model": c.llm.model, "embedding_model": settings.embedding_model},
        )
        yield

    app = FastAPI(title="DocChat API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token = request_id_var.set(rid)
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["x-request-id"] = rid
        log.info(
            "http.request",
            extra={
                "request_id": rid,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": round((time.perf_counter() - t0) * 1000),
            },
        )
        return response

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    app.include_router(documents.router)
    app.include_router(chat.router)
    return app
