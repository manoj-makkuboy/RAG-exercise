"""The RAG question-answering flow, emitted as a stream of events for the UI.

Event types (each becomes one Server-Sent Event):
  sources  - the numbered chunks given to the model (sent first, so the UI can render them)
  delta    - a piece of answer text
  done     - outcome, citations, token usage and timings for this answer
  error    - something failed after streaming started
"""

import logging
import time
from collections.abc import Iterator
from typing import Any, Protocol
from uuid import uuid4

from app.config import Settings
from app.generation import guardrails, prompts
from app.generation.llm import LLM, Completion, LLMError, TextDelta
from app.models import ChatRequest, RetrievedChunk, SourceOut
from app.retrieval.retriever import Retriever

log = logging.getLogger(__name__)

Event = dict[str, Any]


class TraceSink(Protocol):
    def insert_trace(self, trace: dict) -> None: ...


class ChatService:
    def __init__(self, retriever: Retriever, llm: LLM, settings: Settings, traces: TraceSink):
        self._retriever = retriever
        self._llm = llm
        self._settings = settings
        self._traces = traces

    def answer(self, request: ChatRequest) -> Iterator[Event]:
        s = self._settings
        question = guardrails.validate_question(request.question, s.max_question_chars)
        history = prompts.trim_history(request.history, s.max_history_turns)
        trace: dict[str, Any] = {"id": uuid4(), "question": question, "timings_ms": {}}
        t_start = time.perf_counter()

        try:
            # 1. Retrieve. Follow-ups like "what about part-time staff?" lack the subject,
            # so for retrieval we prepend the previous user question.
            t0 = time.perf_counter()
            query = _retrieval_query(question, history)
            chunks = self._retriever.search(query, s.retrieval_top_k, request.document_ids)
            trace["timings_ms"]["retrieval"] = _ms(t0)
            trace["retrieved"] = [_trace_chunk(c) for c in chunks]

            # 2. Guardrail: no relevant context -> don't ask the LLM to improvise.
            if not guardrails.has_relevant_context(chunks, s.min_relevance):
                yield {"type": "sources", "sources": []}
                yield {"type": "delta", "text": prompts.NO_ANSWER}
                trace.update(outcome="no_relevant_context", answer=prompts.NO_ANSWER)
                yield self._done(trace, t_start, cited=[], invalid=[])
                return

            # 3. Build context within the token budget.
            relevant = guardrails.filter_relevant(chunks, s.min_relevance)
            sources_block, used = prompts.build_sources_block(relevant, s.max_context_tokens)
            yield {
                "type": "sources",
                "sources": [
                    SourceOut.from_retrieved(i + 1, c).model_dump(mode="json")
                    for i, c in enumerate(used)
                ],
            }

            # 4. Generate (streamed).
            t0 = time.perf_counter()
            first_token_ms = None
            parts: list[str] = []
            completion: Completion | None = None
            user_message = prompts.build_user_message(question, sources_block)
            for event in self._llm.stream(prompts.SYSTEM_PROMPT, history, user_message):
                if isinstance(event, TextDelta):
                    if first_token_ms is None:
                        first_token_ms = _ms(t0)
                    parts.append(event.text)
                    yield {"type": "delta", "text": event.text}
                else:
                    completion = event
            trace["timings_ms"]["llm_first_token"] = first_token_ms
            trace["timings_ms"]["llm_total"] = _ms(t0)

            # 5. Output guardrails.
            answer = "".join(parts).strip()
            check = guardrails.check_citations(answer, len(used))
            if guardrails.is_no_answer(answer):
                outcome = "model_declined"
            elif not check.cited:
                outcome = "uncited"
            else:
                outcome = "answered"
            trace.update(outcome=outcome, answer=answer)
            if completion:
                trace.update(
                    model=completion.model,
                    input_tokens=completion.input_tokens,
                    output_tokens=completion.output_tokens,
                )
            yield self._done(trace, t_start, cited=check.cited, invalid=check.invalid)

        except LLMError as exc:
            log.warning("chat.llm_error", extra={"trace_id": str(trace["id"]), "error": str(exc)})
            trace.update(outcome="error", answer=None)
            trace["timings_ms"]["total"] = _ms(t_start)
            self._save(trace)
            yield {"type": "error", "message": str(exc), "trace_id": str(trace["id"])}

    def _done(self, trace: dict, t_start: float, cited: list[int], invalid: list[int]) -> Event:
        trace["timings_ms"]["total"] = _ms(t_start)
        self._save(trace)
        log.info(
            "chat.done",
            extra={
                "trace_id": str(trace["id"]),
                "outcome": trace["outcome"],
                "timings_ms": trace["timings_ms"],
                "input_tokens": trace.get("input_tokens"),
                "output_tokens": trace.get("output_tokens"),
                "invalid_citations": invalid,
            },
        )
        return {
            "type": "done",
            "trace_id": str(trace["id"]),
            "outcome": trace["outcome"],
            "cited": cited,
            "invalid_citations": invalid,
            "model": trace.get("model"),
            "usage": {
                "input_tokens": trace.get("input_tokens"),
                "output_tokens": trace.get("output_tokens"),
            },
            "timings_ms": trace["timings_ms"],
        }

    def _save(self, trace: dict) -> None:
        trace.setdefault("retrieved", [])
        try:
            self._traces.insert_trace(trace)
        except Exception:  # observability must never break the user-facing answer
            log.exception("trace.save_failed", extra={"trace_id": str(trace["id"])})


def _retrieval_query(question: str, history: list) -> str:
    previous = next((t.content for t in reversed(history) if t.role == "user"), None)
    return f"{previous}\n{question}" if previous else question


def _trace_chunk(c: RetrievedChunk) -> dict:
    return {
        "chunk_id": str(c.chunk_id),
        "filename": c.filename,
        "page": c.page_number,
        "similarity": round(c.similarity, 4),
        "score": round(c.score, 5),
    }


def _ms(t0: float) -> int:
    return round((time.perf_counter() - t0) * 1000)
