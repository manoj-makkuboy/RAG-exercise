"""Application settings, loaded from environment variables (see .env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://docchat:docchat@localhost:5432/docchat"

    # LLM (Google Gemini). The key is read from GEMINI_API_KEY.
    gemini_api_key: str | None = None
    llm_model: str = "gemini-3.8-flash"
    # Gemini 3.x drops temperature/top_p; reasoning depth is set with thinking_level.
    # "low" keeps time-to-first-token short; grounded Q&A rarely needs deep reasoning.
    llm_thinking_level: str = "low"
    llm_max_tokens: int = 4096

    # Embeddings (local ONNX model via fastembed - no API key, no data leaves the box)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # Chunking (measured in approximate tokens, ~4 chars per token)
    chunk_size_tokens: int = 400
    chunk_overlap_tokens: int = 60

    # Retrieval
    retrieval_top_k: int = 6
    retrieval_candidates: int = 30
    # Below this cosine similarity on the best chunk, we refuse instead of calling the LLM.
    # Tuned on evals/golden_set.jsonl with bge-small: answerable questions scored >= 0.55,
    # off-topic ones 0.41-0.46. In-domain unanswerables (0.57-0.61) are left to the LLM.
    min_relevance: float = 0.50

    # Context management
    max_context_tokens: int = 6000
    max_history_turns: int = 6

    # Guardrails
    max_upload_mb: int = 20
    max_question_chars: int = 2000

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8080"]
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
