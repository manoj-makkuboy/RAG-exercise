from collections.abc import Iterator
from uuid import uuid4

from app.chat import ChatService
from app.config import Settings
from app.generation.llm import FakeLLM, LLMError
from app.models import ChatRequest, ChatTurn, RetrievedChunk


class FakeRetriever:
    def __init__(self, chunks: list[RetrievedChunk]):
        self.chunks = chunks
        self.queries: list[str] = []

    def search(self, query, top_k, document_ids):
        self.queries.append(query)
        return self.chunks[:top_k]


class MemoryTraces:
    def __init__(self):
        self.traces: list[dict] = []

    def insert_trace(self, trace: dict) -> None:
        self.traces.append(trace)


class FailingLLM:
    model = "broken"

    def stream(self, system, history, user_message) -> Iterator:
        raise LLMError("The language model is temporarily unavailable. Please retry.")
        yield  # pragma: no cover - makes this a generator


def make_chunk(similarity: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        filename="policy.md",
        page_number=None,
        content="Refunds are processed within 14 days.",
        similarity=similarity,
        score=0.03,
    )


def run(service: ChatService, question: str, history=None) -> list[dict]:
    return list(service.answer(ChatRequest(question=question, history=history or [])))


def build(chunks, llm, traces=None):
    settings = Settings(min_relevance=0.5, _env_file=None)
    return ChatService(FakeRetriever(chunks), llm, settings, traces or MemoryTraces())


def test_answers_with_sources_and_citations():
    traces = MemoryTraces()
    llm = FakeLLM("Refunds take 14 days [1].")
    events = run(build([make_chunk(0.8)], llm, traces), "How long do refunds take?")

    types = [e["type"] for e in events]
    assert types[0] == "sources" and types[-1] == "done"
    assert events[0]["sources"][0]["ref"] == 1
    answer = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "14 days [1]" in answer
    done = events[-1]
    assert done["outcome"] == "answered"
    assert done["cited"] == [1]
    assert traces.traces[0]["outcome"] == "answered"


def test_skips_llm_when_nothing_relevant():
    llm = FakeLLM("should not be called")
    events = run(build([make_chunk(0.2)], llm), "What is the meaning of life?")
    assert llm.calls == []
    assert events[-1]["outcome"] == "no_relevant_context"


def test_flags_uncited_answers():
    events = run(build([make_chunk(0.8)], FakeLLM("Refunds take 14 days.")), "Refunds?")
    assert events[-1]["outcome"] == "uncited"


def test_reports_invalid_citations():
    events = run(build([make_chunk(0.8)], FakeLLM("Yes [1] and [4].")), "Refunds?")
    assert events[-1]["cited"] == [1]
    assert events[-1]["invalid_citations"] == [4]


def test_llm_failure_becomes_error_event_and_is_traced():
    traces = MemoryTraces()
    events = run(build([make_chunk(0.8)], FailingLLM(), traces), "Refunds?")
    assert events[-1]["type"] == "error"
    assert traces.traces[0]["outcome"] == "error"


def test_follow_up_questions_include_previous_question_in_retrieval():
    retriever = FakeRetriever([make_chunk(0.8)])
    service = ChatService(retriever, FakeLLM("ok [1]"), Settings(_env_file=None), MemoryTraces())
    history = [
        ChatTurn(role="user", content="What is the refund policy?"),
        ChatTurn(role="assistant", content="14 days [1]."),
    ]
    run(service, "And for digital goods?", history)
    assert retriever.queries == ["What is the refund policy?\nAnd for digital goods?"]


def test_trace_failure_does_not_break_answer():
    class BrokenTraces:
        def insert_trace(self, trace):
            raise RuntimeError("db down")

    events = run(build([make_chunk(0.8)], FakeLLM("ok [1]"), BrokenTraces()), "Refunds?")
    assert events[-1]["outcome"] == "answered"
