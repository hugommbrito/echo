"""Prompt templates (docs/PLAN.md §9). System prompts live in .md files next to this module;
user messages are rendered here so the exact wording is versioned with the code."""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

from django.conf import settings

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


def generation_system() -> str:
    return load_prompt(f"generation_{version()}.md")


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


def evaluation_system(question_level: str, feedback_language: str) -> str:
    return render(
        load_prompt(f"evaluation_{version()}.md"),
        question_level=question_level,
        feedback_language=feedback_language_name(feedback_language),
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
    lines.append(
        f"Learner's answer — automatic transcript ({duration_seconds:.0f} s, {word_count} words, "
        f"{words_per_minute:.0f} words per minute):"
    )
    lines.append('"""')
    lines.append(transcript_text.strip())
    lines.append('"""')
    return "\n".join(lines)


# --- Improved answer (on demand) --------------------------------------------------------------


def improved_answer_system(question_level: str, feedback_language: str) -> str:
    return render(
        load_prompt(f"improved_answer_{version()}.md"),
        question_level=question_level,
        feedback_language=feedback_language_name(feedback_language),
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


def whisper_prompt() -> str:
    return load_prompt("whisper_prompt.txt")
