# Working on DocChat (instructions for AI coding assistants)

This file is loaded automatically by Claude Code, and other assistants can be pointed at it.
It records the conventions this repo follows so that generated code matches them.

## Map

- `api/app/ingest/`: parse → chunk → embed. `service.py` runs the pipeline.
- `api/app/retrieval/`: query-time hybrid search (the SQL itself lives in `store.py`).
- `api/app/generation/`: prompts, guardrails and the LLM client (Gemini).
- `api/app/chat.py`: the RAG flow, emitted as SSE events (`sources`, `delta`, `done`, `error`).
- `api/app/store.py`: **all SQL**. Nothing else talks to Postgres directly.
- `web/src/`: React UI. `api.ts` + `sse.ts` hold the only network code.
- `evals/`: golden question set and the runner.

## Commands

- `make up`: run everything (UI on :8080, API on :8000)
- `make test`: API unit + integration tests, web tests and typecheck
- `make lint` / `make format`: ruff
- `make eval`: retrieval metrics (free). `make eval-llm`: end-to-end (costs Gemini tokens)

## Rules

- External dependencies (embedder, LLM, store) sit behind small Protocols. Tests use the
  fakes (`HashEmbedder`, `FakeLLM`, in-memory trace sinks) and **never call a real LLM**.
- Any change to chunking, retrieval, prompts or thresholds must be followed by `make eval`,
  and the before/after numbers go in the PR description. Don't tune by feel.
- Configuration goes in `app/config.py` (env-driven) with a comment explaining the default.
- Keep the SSE event contract in `chat.py` and `web/src/types.ts` in sync.
- Prefer clear, boring code over abstractions: no LangChain-style frameworks, no new
  dependency without a sentence on why in the PR.
- Comments explain *why*, not *what*.

## Don't

- Don't put secrets in code or tests. The key comes from `GEMINI_API_KEY`.
- Don't let observability failures break user requests (see `ChatService._save`).
- Don't weaken a guardrail just to make a test pass. Fix the test data or discuss it.
