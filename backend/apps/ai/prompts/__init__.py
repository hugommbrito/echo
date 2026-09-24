"""Prompt templates (docs/PLAN.md §9 + multi-language addendum).

System prompts live in .md files next to this module and are rendered per practised language
from a `LanguageSpec`; user messages are built here so the exact wording is versioned with
the code.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from django.conf import settings

from apps.core.languages import LanguageSpec

PROMPTS_DIR = Path(__file__).resolve().parent

FEEDBACK_LANGUAGE_NAMES = {"pt-BR": "Brazilian Portuguese", "en": "English"}

_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


@cache
def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8").strip()


def render(template: str, **values: object) -> str:
    """Replace `{name}` placeholders for the given names only (other braces are left alone)."""

    def _sub(match: re.Match) -> str:
        key = match.group(1)
        if key in values:
            return str(values[key])
        return match.group(0)

    return _PLACEHOLDER.sub(_sub, template)


def feedback_language_name(code: str) -> str:
    return FEEDBACK_LANGUAGE_NAMES.get(code, "Brazilian Portuguese")


def version() -> str:
    return settings.ECHO_PROMPT_VERSION


# --- Generation -----------------------------------------------------------------------------


def _language_values(language: LanguageSpec) -> dict[str, str]:
    return {
        "target_language": language.target_language_label,
        "teacher_role": language.teacher_role,
        "learner_context": language.learner_context,
        "variety_notes": language.variety_notes,
        "evaluator_notes": language.evaluator_notes,
        "level_examples": language.level_examples_block(),
        "filler_examples": language.filler_examples,
        "typical_errors": language.typical_errors,
        "speaking_rate_notes": language.speaking_rate_notes,
    }


def generation_system(language: LanguageSpec) -> str:
    return render(load_prompt(f"generation_{version()}.md"), **_language_values(language))


def generation_user(slots, categories, recent_questions: list[tuple[str, str]]) -> str:
    lines = ["Slots:"]
    for slot in slots:
        probe = ""
        if slot.probe == "above":
            probe = " (probe: one level above the learner)"
        elif slot.probe == "below":
            probe = " (probe: one level below the learner)"
        lines.append(f"{slot.number}. category: {slot.category.slug} — level: {slot.level}{probe}")
    lines.append("")
    lines.append("Categories:")
    for category in categories:
        hint = f" Guidance: {category.generation_hint}" if category.generation_hint else ""
        lines.append(f"- {category.slug}: {category.name} — {category.description}{hint}")
    lines.append("")
    lines.append("Already asked to this learner (do not repeat or paraphrase):")
    if recent_questions:
        lines.extend(f"[{slug}] {text}" for slug, text in recent_questions)
    else:
        lines.append("(none yet)")
    return "\n".join(lines)


# --- Evaluation -----------------------------------------------------------------------------


def evaluation_system(language: LanguageSpec, question_level: str, feedback_language: str) -> str:
    return render(
        load_prompt(f"evaluation_{version()}.md"),
        question_level=question_level,
        feedback_language=feedback_language_name(feedback_language),
        **_language_values(language),
    )


def evaluation_user(
    *,
    category_name: str,
    question_level: str,
    scenario: str | None,
    question_text: str,
    key_points: list[str],
    transcript_text: str,
    duration_seconds: float,
    word_count: int,
    words_per_minute: float,
    thinking_seconds: float | None = None,
    thinking_baseline_seconds: float | None = None,
) -> str:
    lines = [
        f"Category: {category_name}",
        f"Question level: {question_level}",
        f"Scenario: {scenario or '(none)'}",
        f"Question: {question_text}",
        "What a complete answer usually covers:",
    ]
    lines.extend(f"- {point}" for point in key_points)
    lines.append("")
    if thinking_seconds is not None:
        lines.append(thinking_time_line(thinking_seconds, thinking_baseline_seconds))
    lines.append(
        f"Learner's answer — automatic transcript ({duration_seconds:.0f} s, {word_count} words, "
        f"{words_per_minute:.0f} words per minute):"
    )
    lines.append('"""')
    lines.append(transcript_text.strip())
    lines.append('"""')
    return "\n".join(lines)


def thinking_time_line(seconds: float, baseline: float | None) -> str:
    """One line for the evaluator: the pause before speaking, against the learner's own median.

    A weak signal only (the system prompt says so); the wording never scores anything itself.
    """
    if baseline is None or baseline <= 0:
        return f"Thinking time before recording: {seconds:.0f} s (no personal reference yet)."
    ratio = seconds / baseline
    if ratio <= 1.0:
        label = "within the learner's usual range"
    elif ratio <= settings.ECHO_THINKING_YELLOW_RATIO:
        label = "somewhat slower than usual"
    else:
        label = "much slower than usual"
    return (
        f"Thinking time before recording: {seconds:.0f} s "
        f"(the learner's own recent median: {baseline:.0f} s — {label})."
    )


# --- Improved answer (on demand) --------------------------------------------------------------


def improved_answer_system(
    language: LanguageSpec, question_level: str, feedback_language: str
) -> str:
    return render(
        load_prompt(f"improved_answer_{version()}.md"),
        question_level=question_level,
        feedback_language=feedback_language_name(feedback_language),
        **_language_values(language),
    )


def improved_answer_user(
    *, question_text: str, scenario: str | None, transcript_text: str, issues: list[dict]
) -> str:
    issue_lines = [f"{i.get('quote')} → {i.get('correction')}" for i in issues if i.get("quote")]
    lines = [
        f"Question: {question_text}",
        f"Scenario: {scenario or '(none)'}",
        "Learner's transcript:",
        '"""',
        transcript_text.strip(),
        '"""',
        "Grammar issues already identified (for reference): "
        + ("\n" + "\n".join(issue_lines) if issue_lines else "(none)"),
    ]
    return "\n".join(lines)


def whisper_prompt(language: LanguageSpec) -> str:
    return language.whisper_prompt
