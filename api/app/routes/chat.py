import json
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.generation.guardrails import GuardrailViolation, validate_question
from app.models import ChatRequest, SearchRequest, SourceOut

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
def chat(request: Request, body: ChatRequest) -> StreamingResponse:
    """Answer a question as a Server-Sent Events stream (see app/chat.py for event types)."""
    try:
        validate_question(body.question, request.app.state.settings.max_question_chars)
    except GuardrailViolation as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    events = request.app.state.chat.answer(body)
    return StreamingResponse(
        _sse(events),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/search", response_model=list[SourceOut])
def search(request: Request, body: SearchRequest) -> list[SourceOut]:
    """Retrieval only, no LLM. Used by the eval harness and handy for debugging."""
    chunks = request.app.state.retriever.search(body.query, body.top_k, body.document_ids)
    return [SourceOut.from_retrieved(i + 1, c) for i, c in enumerate(chunks)]


@router.get("/traces")
def traces(request: Request, limit: int = 50) -> list[dict]:
    return request.app.state.store.recent_traces(min(limit, 200))


def _sse(events: Iterator[dict]) -> Iterator[str]:
    for event in events:
        yield f"data: {json.dumps(event, default=str)}\n\n"
