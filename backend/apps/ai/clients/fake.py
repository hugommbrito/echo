"""Deterministic fakes used in tests and in local dev without API keys (ECHO_AI_PROVIDER=fake).

Tests can enqueue scripted responses with `FakeLLM.queue_evaluation(...)` etc.; otherwise the
fakes derive plausible output from the input (word count, slots).
"""

from __future__ import annotations

import hashlib
import re
from collections import deque
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from apps.ai.clients.base import LLMResult, ProbeResult, TranscriptionResult
from apps.ai.exceptions import AudioProbeError
from apps.ai.schemas import (
    DimensionScore,
    EvaluationOutput,
    FluencyMarkers,
    FluencyScore,
    GeneratedQuestion,
    GenerationOutput,
    GrammarIssue,
    GrammarScore,
    ImprovedAnswerOutput,
)

T = TypeVar("T", bound=BaseModel)

_SLOT_RE = re.compile(r"^(\d+)\. category: ([a-z0-9-]+) — level: (A1|A2|B1|B2|C1|C2)", re.M)
_ALREADY_RE = re.compile(r"^\[[a-z0-9-]+\] (.+)$", re.M)
_TRANSCRIPT_RE = re.compile(r'"""\n(.*?)\n"""', re.S)
_WORDS_RE = re.compile(r"\((\d+) s, (\d+) words, (\d+) words per minute\)")

QUESTION_BANK = {
    "A1": "What do you usually do on a {day}? Tell me about it.",
    "A2": "Tell me about the last time you {past}. What happened?",
    "B1": "Why do you think {topic} matters, and can you give me an example from your life?",
    "B2": (
        "Describe a time you had to {hard}. How did you handle it, "
        "and what would you do differently?"
    ),
    "C1": "How has {topic} changed what people expect from each other, and how would you adapt?",
    "C2": "Some people say {topic} is overrated. Weigh both sides and tell me where you stand.",
}
FILLERS = {
    "day": ["Saturday morning", "weekday evening", "Sunday", "rainy day"],
    "past": ["went shopping", "travelled somewhere new", "helped a neighbour", "had an interview"],
    "topic": ["good customer service", "teamwork", "punctuality", "learning a language"],
    "hard": [
        "deal with an unhappy customer",
        "disagree with a manager",
        "solve a problem at work",
        "change plans at the last minute",
    ],
}


class FakeLLM:
    provider = "fake"
    _queued: dict[type, deque] = {}
    calls: list[dict] = []
    fail_next: Exception | None = None

    @classmethod
    def queue(cls, output: BaseModel) -> None:
        cls._queued.setdefault(type(output), deque()).append(output)

    @classmethod
    def reset(cls) -> None:
        cls._queued.clear()
        cls.calls.clear()
        cls.fail_next = None

    def parse(
        self,
        *,
        model,
        system,
        user,
        output_format: type[T],
        effort="medium",
        max_tokens=8000,
        timeout=None,
    ) -> LLMResult[T]:
        FakeLLM.calls.append(
            {
                "model": model,
                "system": system,
                "user": user,
                "output_format": output_format.__name__,
            }
        )
        if FakeLLM.fail_next is not None:
            exc, FakeLLM.fail_next = FakeLLM.fail_next, None
            raise exc
        queued = FakeLLM._queued.get(output_format)
        if queued:
            parsed = queued.popleft()
        elif output_format is GenerationOutput:
            parsed = self._generate(user)
        elif output_format is EvaluationOutput:
            parsed = self._evaluate(user)
        elif output_format is ImprovedAnswerOutput:
            parsed = self._improve(user)
        else:  # pragma: no cover
            raise NotImplementedError(output_format)
        return LLMResult(
            parsed=parsed,  # type: ignore[arg-type]
            model=model,
            input_tokens=len(system.split()) + len(user.split()),
            output_tokens=120,
            cache_read_input_tokens=len(system.split()),
            latency_ms=5,
            stop_reason="end_turn",
            raw={"fake": True},
        )

    # --- generation ---------------------------------------------------------------------
    def _generate(self, user: str) -> GenerationOutput:
        already = set(_ALREADY_RE.findall(user))
        questions = []
        for number, slug, level in _SLOT_RE.findall(user):
            seed = 0
            while True:
                text = self._question_text(slug, level, seed, len(already))
                if text not in already:
                    break
                seed += 1
            already.add(text)
            digest = int(hashlib.md5(text.encode()).hexdigest(), 16)
            questions.append(
                GeneratedQuestion(
                    slot=int(number),
                    category=slug,
                    level=level,  # type: ignore[arg-type]
                    difficulty_within_level=["easier", "typical", "harder"][digest % 3],
                    scenario=f"You are talking to someone in Canada about {slug.replace('-', ' ')}."
                    if digest % 2
                    else None,
                    question=text,
                    key_points=[
                        "describes one concrete situation",
                        "gives a reason",
                        "says how it ended",
                    ],
                )
            )
        return GenerationOutput(questions=questions)

    @staticmethod
    def _question_text(slug: str, level: str, seed: int, salt: int) -> str:
        template = QUESTION_BANK[level]
        index = (salt + seed) % 4
        values = {key: options[index] for key, options in FILLERS.items()}
        return f"[{slug}] " + template.format(**values)

    # --- evaluation -----------------------------------------------------------------------
    def _evaluate(self, user: str) -> EvaluationOutput:
        match = _TRANSCRIPT_RE.search(user)
        transcript = match.group(1).strip() if match else ""
        words = len(transcript.split())
        if words < 5:
            note = "Não detectamos fala suficiente para avaliar."
            return EvaluationOutput(
                structure=DimensionScore(score=1, feedback=note),
                grammar=GrammarScore(score=1, feedback=note, issues=[]),
                fluency=FluencyScore(
                    score=1,
                    feedback=note,
                    markers=FluencyMarkers(fillers=0, false_starts=0, repetitions=0),
                ),
            )
        structure = min(5, max(1, 1 + words // 25))
        grammar = 3 if "I have work" not in transcript else 2
        fillers = sum(transcript.lower().count(f) for f in (" um", " uh", "you know"))
        fluency = 4 if fillers <= 1 else 3 if fillers <= 4 else 2
        issues = []
        if "I have work" in transcript:
            issues.append(
                GrammarIssue(
                    quote="I have work there",
                    correction="I have worked there",
                    type="verb_tense",
                    explanation="Present perfect precisa do particípio.",
                )
            )
        return EvaluationOutput(
            structure=DimensionScore(
                score=structure, feedback="Você respondeu à pergunta com um exemplo concreto."
            ),
            grammar=GrammarScore(
                score=grammar, feedback="Atenção aos tempos verbais.", issues=issues
            ),
            fluency=FluencyScore(
                score=fluency,
                feedback="Boa continuidade; reduza os marcadores de hesitação.",
                markers=FluencyMarkers(fillers=fillers, false_starts=0, repetitions=0),
            ),
        )

    def _improve(self, user: str) -> ImprovedAnswerOutput:
        match = _TRANSCRIPT_RE.search(user)
        transcript = match.group(1).strip() if match else ""
        improved = (
            transcript.replace("I have work", "I have worked").replace(" um", "").replace(" uh", "")
        )
        return ImprovedAnswerOutput(
            improved_answer=improved or "(nothing to improve)",
            notes=["Removemos hesitações.", "Corrigimos o present perfect."],
        )


class FakeTranscriber:
    provider = "fake"
    _queued: deque[str] = deque()
    fail_next: Exception | None = None

    @classmethod
    def queue(cls, text: str) -> None:
        cls._queued.append(text)

    @classmethod
    def reset(cls) -> None:
        cls._queued.clear()
        cls.fail_next = None

    def transcribe(self, path, *, model=None) -> TranscriptionResult:
        if FakeTranscriber.fail_next is not None:
            exc, FakeTranscriber.fail_next = FakeTranscriber.fail_next, None
            raise exc
        if FakeTranscriber._queued:
            text = FakeTranscriber._queued.popleft()
        else:
            text = (
                "So, um, last year I worked in a store and one day a customer was really angry "
                "because her order was late. I listened to her, I apologised and I offered a "
                "discount. In the end she was happy and she came back the next week."
            )
        return TranscriptionResult(
            text=text,
            model=model or "fake-whisper",
            segments=[{"start": 0, "end": 30, "text": text}],
            duration_seconds=None,
            latency_ms=3,
            raw={"fake": True},
        )


class FakeProbe:
    default_duration = 30.0
    _queued: deque[float | Exception] = deque()

    @classmethod
    def queue(cls, value: float | Exception) -> None:
        cls._queued.append(value)

    @classmethod
    def reset(cls) -> None:
        cls._queued.clear()

    def probe(self, path) -> ProbeResult:
        if FakeProbe._queued:
            value = FakeProbe._queued.popleft()
            if isinstance(value, Exception):
                raise value
            return ProbeResult(duration_seconds=float(value), format_name="fake")
        if Path(path).stat().st_size == 0:
            raise AudioProbeError("Audio file is empty.")
        return ProbeResult(duration_seconds=self.default_duration, format_name="fake")
