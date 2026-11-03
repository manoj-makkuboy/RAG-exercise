"""LLM client behind a minimal streaming interface.

The rest of the app only sees `LLM.stream(...)` yielding TextDelta events and one final
Completion. Swapping providers (or faking the model in tests) touches only this file.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from app.models import ChatTurn


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class Completion:
    model: str
    input_tokens: int | None
    output_tokens: int | None
    finish_reason: str | None


LLMEvent = TextDelta | Completion


class LLMError(RuntimeError):
    """A provider failure we can show to the user (message is safe to display)."""


class LLM(Protocol):
    model: str

    def stream(
        self, system: str, history: list[ChatTurn], user_message: str
    ) -> Iterator[LLMEvent]: ...


class GeminiLLM:
    def __init__(self, api_key: str | None, model: str, thinking_level: str, max_tokens: int):
        from google import genai
        from google.genai import types

        # Without a key the app still starts (upload, search and the UI keep working);
        # chat requests then fail with a clear message instead of the whole API crashing.
        self._client = genai.Client(api_key=api_key) if api_key else None
        self._types = types
        self.model = model
        self._config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(thinking_level=thinking_level),
        )

    def stream(self, system: str, history: list[ChatTurn], user_message: str) -> Iterator[LLMEvent]:
        from google.genai import errors

        if self._client is None:
            raise LLMError(
                "GEMINI_API_KEY is not configured on the server, so answers are disabled."
            )
        types = self._types
        contents = [
            types.Content(
                role="model" if turn.role == "assistant" else "user",
                parts=[types.Part(text=turn.content)],
            )
            for turn in history
        ]
        contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
        config = self._config.model_copy(update={"system_instruction": system})

        usage = None
        finish_reason = None
        try:
            for chunk in self._client.models.generate_content_stream(
                model=self.model, contents=contents, config=config
            ):
                if chunk.usage_metadata:
                    usage = chunk.usage_metadata
                if chunk.candidates and chunk.candidates[0].finish_reason:
                    finish_reason = str(chunk.candidates[0].finish_reason.value)
                if chunk.text:
                    yield TextDelta(chunk.text)
        except errors.ClientError as exc:  # 4xx: bad key, quota, invalid request
            raise LLMError(f"The language model rejected the request ({exc.code}).") from exc
        except errors.ServerError as exc:  # 5xx: provider outage; SDK already retried
            raise LLMError("The language model is temporarily unavailable. Please retry.") from exc

        yield Completion(
            model=self.model,
            input_tokens=usage.prompt_token_count if usage else None,
            output_tokens=usage.candidates_token_count if usage else None,
            finish_reason=finish_reason,
        )


class FakeLLM:
    """Deterministic LLM for tests: replays a canned answer word by word."""

    def __init__(self, answer: str, model: str = "fake-llm"):
        self.answer = answer
        self.model = model
        self.calls: list[str] = []

    def stream(self, system: str, history: list[ChatTurn], user_message: str) -> Iterator[LLMEvent]:
        self.calls.append(user_message)
        for word in self.answer.split(" "):
            yield TextDelta(word + " ")
        yield Completion(model=self.model, input_tokens=100, output_tokens=20, finish_reason="STOP")
