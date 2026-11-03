"""Domain objects and API schemas."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Page:
    """A unit of parsed text. For PDFs this is a real page; for text files, number is None."""

    text: str
    number: int | None


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    page_number: int | None
    token_count: int


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: UUID
    document_id: UUID
    filename: str
    page_number: int | None
    content: str
    similarity: float  # cosine similarity of the dense embedding, 0..1
    score: float  # fused rank score used for ordering


class DocumentOut(BaseModel):
    id: UUID
    filename: str
    media_type: str
    page_count: int
    chunk_count: int
    created_at: datetime


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=20_000)


class ChatRequest(BaseModel):
    question: str
    history: list[ChatTurn] = Field(default_factory=list)
    document_ids: list[UUID] | None = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=6, ge=1, le=50)
    document_ids: list[UUID] | None = None


class SourceOut(BaseModel):
    ref: int  # the [n] number the model uses to cite this source
    chunk_id: UUID
    document_id: UUID
    filename: str
    page_number: int | None
    content: str
    similarity: float

    @classmethod
    def from_retrieved(cls, ref: int, c: RetrievedChunk) -> "SourceOut":
        return cls(
            ref=ref,
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            filename=c.filename,
            page_number=c.page_number,
            content=c.content,
            similarity=round(c.similarity, 4),
        )
