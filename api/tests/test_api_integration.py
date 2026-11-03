"""End-to-end API tests against a real Postgres+pgvector, with a fake embedder and LLM.

Run via `make test` (spins up the db) or set DATABASE_URL to a disposable database.
"""

import json
import os

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import create_pool, run_migrations
from app.generation.llm import FakeLLM
from app.ingest.embedder import HashEmbedder
from app.main import Components, create_app
from app.store import Store

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL not set"),
]

POLICY = b"""# Refund policy

Customers can request a refund within 30 days of purchase.
Refunds are paid back to the original payment method within 14 business days.

# Shipping

Orders over 50 EUR ship for free. Standard delivery takes 3 to 5 days.
"""


@pytest.fixture
def client():
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS chunks, documents, query_traces CASCADE")
    pool = create_pool(DATABASE_URL)
    run_migrations(pool)
    llm = FakeLLM("Refunds are paid within 14 business days [1].")
    # HashEmbedder similarities are lower than a real model's, so relax the threshold.
    settings = Settings(database_url=DATABASE_URL, min_relevance=0.05, _env_file=None)
    app = create_app(settings, Components(store=Store(pool), embedder=HashEmbedder(), llm=llm))
    with TestClient(app) as c:
        c.llm = llm
        yield c
    pool.close()


def upload(client, name="policy.md", data=POLICY):
    return client.post("/api/documents", files={"file": (name, data, "text/markdown")})


def sse_events(response) -> list[dict]:
    return [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]


def test_upload_list_and_deduplicate(client):
    first = upload(client)
    assert first.status_code == 201
    assert first.json()["chunk_count"] >= 1

    again = upload(client, name="copy.md")
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]

    docs = client.get("/api/documents").json()
    assert [d["filename"] for d in docs] == ["policy.md"]


def test_rejects_bad_uploads(client):
    assert upload(client, name="photo.png", data=b"\x89PNG").status_code == 415
    assert upload(client, name="empty.txt", data=b"  ").status_code == 422


def test_search_finds_keyword_and_semantic_matches(client):
    upload(client)
    results = client.post("/api/search", json={"query": "refund payment method"}).json()
    assert results
    assert "Refunds are paid back" in results[0]["content"]


def test_chat_streams_sources_answer_and_trace(client):
    upload(client)
    resp = client.post("/api/chat", json={"question": "How long do refunds take?"})
    assert resp.status_code == 200
    events = sse_events(resp)
    assert events[0]["type"] == "sources" and events[0]["sources"]
    done = events[-1]
    assert done["outcome"] == "answered"
    assert done["cited"] == [1]

    traces = client.get("/api/traces").json()
    assert traces[0]["question"] == "How long do refunds take?"
    assert traces[0]["outcome"] == "answered"


def test_chat_refuses_without_documents(client):
    events = sse_events(client.post("/api/chat", json={"question": "How long do refunds take?"}))
    assert events[-1]["outcome"] == "no_relevant_context"
    assert client.llm.calls == []


def test_chat_validates_question(client):
    assert client.post("/api/chat", json={"question": "   "}).status_code == 422


def test_delete_document_removes_its_chunks(client):
    doc_id = upload(client).json()["id"]
    assert client.delete(f"/api/documents/{doc_id}").status_code == 204
    assert client.post("/api/search", json={"query": "refund"}).json() == []
    assert client.delete(f"/api/documents/{doc_id}").status_code == 404
