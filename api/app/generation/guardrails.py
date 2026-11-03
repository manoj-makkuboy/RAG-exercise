"""Input and output guardrails.

Input:  reject empty / oversized questions before spending anything on them.
Retrieval: if nothing relevant was found, answer "not found" without calling the LLM at all.
           This is the cheapest and most effective hallucination guard we have.
Output: verify that citations point at sources we actually supplied, and flag answers
        that make claims without citing anything.
"""

import re
from dataclasses import dataclass

from app.generation.prompts import NO_ANSWER
from app.models import RetrievedChunk

CITATION_RE = re.compile(r"\[(\d{1,3})\]")


class GuardrailViolation(ValueError):
    pass


def validate_question(question: str, max_chars: int) -> str:
    cleaned = question.strip()
    if not cleaned:
        raise GuardrailViolation("Question is empty.")
    if len(cleaned) > max_chars:
        raise GuardrailViolation(f"Question is too long ({len(cleaned)} > {max_chars} characters).")
    return cleaned


def has_relevant_context(chunks: list[RetrievedChunk], min_similarity: float) -> bool:
    return bool(chunks) and max(c.similarity for c in chunks) >= min_similarity


def filter_relevant(chunks: list[RetrievedChunk], min_similarity: float) -> list[RetrievedChunk]:
    """Drop chunks far below the bar. Keyword-only hits get a little slack (0.8x)
    because exact-term matches can be relevant even when the embedding disagrees."""
    floor = min_similarity * 0.8
    return [c for c in chunks if c.similarity >= floor]


@dataclass(frozen=True)
class CitationCheck:
    cited: list[int]  # valid source numbers, in order of first appearance
    invalid: list[int]  # numbers that don't correspond to any supplied source


def check_citations(answer: str, source_count: int) -> CitationCheck:
    seen: list[int] = []
    invalid: list[int] = []
    for match in CITATION_RE.finditer(answer):
        n = int(match.group(1))
        target = seen if 1 <= n <= source_count else invalid
        if n not in target:
            target.append(n)
    return CitationCheck(cited=seen, invalid=invalid)


def is_no_answer(answer: str) -> bool:
    return answer.strip().startswith(NO_ANSWER)
