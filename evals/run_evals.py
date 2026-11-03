"""Evaluate retrieval (and optionally answers) against evals/golden_set.jsonl.

Usage:
    python evals/run_evals.py                 # retrieval only: free, no LLM calls
    python evals/run_evals.py --with-llm      # also grade end-to-end answers (uses Gemini)

Metrics
  Retrieval (answerable questions):
    hit@k   - a chunk from the expected file containing the evidence text is in the top k
    MRR     - mean reciprocal rank of that chunk
  Answers (--with-llm):
    answerable   -> outcome "answered", cites at least one source, and contains the expected keywords
    unanswerable -> outcome "no_relevant_context" or "model_declined" (i.e. no hallucinated answer)

Needs only the standard library, and talks to a running API (default http://localhost:8000).
"""

import argparse
import json
import re
import sys
import time
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "evals" / "golden_set.jsonl"
SAMPLE_DOCS = ROOT / "sample_docs"
RESULTS_DIR = ROOT / "evals" / "results"


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def post_json(base: str, path: str, body: dict) -> urllib.request.Request:
    return urllib.request.Request(
        base + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )


def upload(base: str, path: Path) -> None:
    boundary = uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        base + "/api/documents",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as res:
        doc = json.load(res)
    print(f"  indexed {doc['filename']}: {doc['chunk_count']} chunks")


def search(base: str, question: str, k: int) -> list[dict]:
    with urllib.request.urlopen(post_json(base, "/api/search", {"query": question, "top_k": k})) as res:
        return json.load(res)


def chat(base: str, question: str) -> dict:
    with urllib.request.urlopen(post_json(base, "/api/chat", {"question": question}), timeout=180) as res:
        events = [json.loads(line[6:]) for line in res.read().decode().splitlines() if line.startswith("data: ")]
    answer = "".join(e["text"] for e in events if e["type"] == "delta")
    final = events[-1] if events else {"type": "error", "message": "no events"}
    return {"answer": answer, **final}


def retrieval_rank(item: dict, results: list[dict]) -> int | None:
    evidence = norm(item["evidence"])
    for i, r in enumerate(results, start=1):
        if r["filename"] == item["source"] and evidence in norm(r["content"]):
            if "page" in item and r["page_number"] != item["page"]:
                continue
            return i
    return None


def grade_answer(item: dict, result: dict) -> tuple[bool, str]:
    outcome = result.get("outcome", "error")
    if not item.get("answerable", True):
        ok = outcome in ("no_relevant_context", "model_declined")
        return ok, f"outcome={outcome}"
    if outcome != "answered":
        return False, f"outcome={outcome}"
    missing = [kw for kw in item["answer_keywords"] if norm(kw) not in norm(result["answer"])]
    return not missing, f"missing={missing}" if missing else "ok"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--k", type=int, default=6)
    parser.add_argument("--with-llm", action="store_true")
    parser.add_argument("--skip-upload", action="store_true")
    args = parser.parse_args()

    items = [json.loads(line) for line in GOLDEN.read_text().splitlines() if line.strip()]

    if not args.skip_upload:
        print("Indexing sample docs (duplicates are skipped)...")
        for path in sorted(SAMPLE_DOCS.iterdir()):
            if path.suffix in {".md", ".txt", ".pdf"}:
                upload(args.base_url, path)

    rows = []
    for item in items:
        row: dict = {"id": item["id"], "question": item["question"]}
        results = search(args.base_url, item["question"], args.k)
        row["top_similarity"] = round(results[0]["similarity"], 3) if results else None
        if item.get("answerable", True):
            row["rank"] = retrieval_rank(item, results)
        if args.with_llm:
            t0 = time.perf_counter()
            result = chat(args.base_url, item["question"])
            row["answer_ok"], row["answer_note"] = grade_answer(item, result)
            row["outcome"] = result.get("outcome")
            row["latency_ms"] = round((time.perf_counter() - t0) * 1000)
            row["answer"] = result["answer"]
        rows.append(row)
        status = f"rank={row.get('rank', '-')!s:>4}  sim={row['top_similarity']}"
        if args.with_llm:
            status += f"  answer={'PASS' if row['answer_ok'] else 'FAIL'} ({row['answer_note']})"
        print(f"  {item['id']:<22} {status}")

    answerable = [r for r in rows if "rank" in r]
    hits = sum(1 for r in answerable if r["rank"] is not None)
    mrr = sum(1 / r["rank"] for r in answerable if r["rank"]) / len(answerable)
    summary = {
        "k": args.k,
        "questions": len(rows),
        f"hit@{args.k}": round(hits / len(answerable), 3),
        "hit@1": round(sum(1 for r in answerable if r["rank"] == 1) / len(answerable), 3),
        "mrr": round(mrr, 3),
    }
    if args.with_llm:
        pos = [r for r in rows if "rank" in r]
        neg = [r for r in rows if "rank" not in r]
        summary["answer_accuracy"] = round(sum(r["answer_ok"] for r in pos) / len(pos), 3)
        summary["refusal_accuracy"] = round(sum(r["answer_ok"] for r in neg) / max(1, len(neg)), 3)
        summary["p50_latency_ms"] = sorted(r["latency_ms"] for r in rows)[len(rows) // 2]

    print("\nSummary:", json.dumps(summary, indent=2))
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    print(f"Saved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
