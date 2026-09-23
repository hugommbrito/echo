"""Structured-output schemas (Pydantic) for the three Anthropic calls."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

CEFR = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
Difficulty = Literal["easier", "typical", "harder"]
GrammarIssueType = Literal[
    "verb_tense",
    "subject_verb_agreement",
    "article",
    "preposition",
    "word_order",
    "plural",
    "pronoun",
    "word_choice",
    "missing_word",
    "extra_word",
    "agreement",
    "verb_form",
    "negation",
    "register",
    "other",
]
GRAMMAR_ISSUE_TYPES: tuple[str, ...] = GrammarIssueType.__args__  # type: ignore[attr-defined]


class GeneratedQuestion(BaseModel):
    slot: int
    category: str
    level: CEFR
    difficulty_within_level: Difficulty
    scenario: str | None
    question: str
    key_points: list[str]


class GenerationOutput(BaseModel):
    questions: list[GeneratedQuestion]


def _clamp_score(value: int) -> int:
    return max(1, min(5, int(value)))


class DimensionScore(BaseModel):
    score: int
    feedback: str

    @field_validator("score")
    @classmethod
    def _bounded(cls, value: int) -> int:
        return _clamp_score(value)


class GrammarIssue(BaseModel):
    quote: str
    correction: str
    type: GrammarIssueType
    explanation: str


class GrammarScore(DimensionScore):
    issues: list[GrammarIssue] = Field(default_factory=list)


class FluencyMarkers(BaseModel):
    fillers: int
    false_starts: int
    repetitions: int


class FluencyScore(DimensionScore):
    markers: FluencyMarkers


class EvaluationOutput(BaseModel):
    structure: DimensionScore
    grammar: GrammarScore
    fluency: FluencyScore


class ImprovedAnswerOutput(BaseModel):
    improved_answer: str
    notes: list[str]
