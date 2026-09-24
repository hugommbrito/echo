from decimal import Decimal

import pytest

from apps.ai import pricing, prompts
from apps.ai.clients.fake import FakeLLM
from apps.ai.schemas import EvaluationOutput, GenerationOutput, GrammarIssue
from apps.core.languages import get_language
from apps.leveling.probes import plan_slots

EN = get_language("en")
FR = get_language("fr")


def test_evaluation_system_prompt_is_rendered_per_level_and_language():
    text = prompts.evaluation_system(EN, "B1", "pt-BR")
    assert "written for CEFR level B1" in text
    assert "Brazilian Portuguese" in text
    assert "experienced ESL teacher" in text and "English speaking-practice app" in text
    assert "(um, uh, like, you know, so)" in text
    assert "Quote the learner's English exactly" in text
    assert "{" not in text.replace("{question_level}", "") or "{question_level}" not in text
    assert (
        "Brazilian Portuguese"
        not in prompts.evaluation_system(EN, "B1", "en").split("Write all feedback text in ")[1][:8]
    )


def test_prompts_are_rendered_per_practised_language():
    generation = prompts.generation_system(FR)
    assert "Canadian French (Québec) speaking-practice app" in generation
    assert "write the questions in Canadian French (Québec)" in generation
    assert "- A1: " in generation and "épicerie" in generation and "« vous »" in generation
    assert "{" not in generation

    evaluation = prompts.evaluation_system(FR, "A2", "pt-BR")
    assert "experienced FLE teacher" in evaluation
    assert "(euh, ben, là, tsé" in evaluation
    assert "Quote the learner's Canadian French (Québec) exactly" in evaluation
    assert "Accept France-French forms" in evaluation
    assert "gender and number agreement" in evaluation
    assert "{" not in evaluation

    improved = prompts.improved_answer_system(FR, "A2", "pt-BR")
    assert "Write natural spoken Canadian French (Québec) one step above A2" in improved
    assert "{" not in improved

    assert prompts.whisper_prompt(FR).startswith("Euh, ben")
    assert prompts.whisper_prompt(EN).startswith("Um, uh")


def test_render_leaves_unknown_braces_alone():
    assert prompts.render("{a} and {unknown} {b}", a=1, b=2) == "1 and {unknown} 2"


@pytest.mark.django_db
def test_generation_user_prompt_lists_slots_categories_and_history(global_categories):
    cats = [global_categories["job-interview"], global_categories["travel"]]
    slots = plan_slots(5, cats, "B1")
    text = prompts.generation_user(
        slots, cats, [("job-interview", "Can you tell me about yourself?")]
    )
    assert text.startswith(
        "Slots:\n1. category: job-interview — level: B1\n2. category: travel — level: B1\n3. category: job-interview — level: B2 (probe: one level above the learner)"
    )
    assert "- job-interview: Job interview — Interview questions" in text
    assert "Guidance: Phrase questions exactly as an interviewer would." in text
    assert "[job-interview] Can you tell me about yourself?" in text


def test_generation_user_prompt_without_history(global_categories):
    text = prompts.generation_user([], [], [])
    assert text.endswith("(none yet)")


def test_evaluation_user_prompt_format():
    text = prompts.evaluation_user(
        category_name="Job interview",
        question_level="B1",
        scenario=None,
        question_text="Tell me about yourself.",
        key_points=["a", "b"],
        transcript_text="I am Ana.",
        duration_seconds=61.0,
        word_count=98,
        words_per_minute=96.4,
    )
    assert "Scenario: (none)" in text
    assert "- a\n- b" in text
    assert "(61 s, 98 words, 96 words per minute)" in text
    assert text.endswith('"""\nI am Ana.\n"""')


def test_evaluation_system_prompt_treats_thinking_time_as_a_weak_signal():
    text = prompts.evaluation_system(EN, "B1", "pt-BR")
    assert "treat it exactly like the speaking rate: a weak secondary signal only" in text
    assert "Do not quote these numbers in the feedback." in text


_EVAL_KWARGS = dict(
    category_name="Job interview",
    question_level="B1",
    scenario=None,
    question_text="Tell me about yourself.",
    key_points=["a", "b"],
    transcript_text="I am Ana.",
    duration_seconds=61.0,
    word_count=98,
    words_per_minute=96.4,
)


def test_evaluation_user_prompt_thinking_time_line():
    text = prompts.evaluation_user(**_EVAL_KWARGS, thinking_seconds=8, thinking_baseline_seconds=6)
    assert (
        "Thinking time before recording: 8 s (the learner's own recent median: 6 s — "
        "somewhat slower than usual)." in text
    )
    assert text.index("Thinking time") < text.index("Learner's answer")
    assert text.endswith('"""\nI am Ana.\n"""')
    fast = prompts.evaluation_user(**_EVAL_KWARGS, thinking_seconds=5, thinking_baseline_seconds=6)
    assert "within the learner's usual range" in fast
    slow = prompts.evaluation_user(**_EVAL_KWARGS, thinking_seconds=20, thinking_baseline_seconds=6)
    assert "much slower than usual" in slow
    fresh = prompts.evaluation_user(
        **_EVAL_KWARGS, thinking_seconds=8, thinking_baseline_seconds=None
    )
    assert "Thinking time before recording: 8 s (no personal reference yet)." in fresh
    # without a measurement the message is byte-identical to the historical format
    plain = prompts.evaluation_user(**_EVAL_KWARGS)
    assert plain == prompts.evaluation_user(**_EVAL_KWARGS, thinking_seconds=None)
    assert "Thinking time" not in plain


def test_pricing_openai_and_tts():
    assert pricing.token_cost("gpt-6-sol", 1_000_000, 0) == Decimal("2.000000")
    assert pricing.token_cost("gpt-6-sol-2026-08-01", 1_000_000, 0) == Decimal("2.000000")  # prefix
    assert pricing.token_cost("gpt-6-astra", 0, 1_000_000) == Decimal("50.000000")
    assert pricing.token_cost("gpt-6-sol", 0, 0, 1_000_000) == Decimal("0.200000")
    assert pricing.tts_cost("gpt-4o-mini-tts", 60) == Decimal("0.015000")
    assert pricing.tts_cost("unknown", 60) == Decimal(0)
    assert pricing.tts_cost("tts-1", None) == Decimal(0)


def test_improved_answer_prompt_lists_issues():
    text = prompts.improved_answer_user(
        question_text="Q",
        scenario="S",
        transcript_text="T",
        issues=[{"quote": "I have work", "correction": "I have worked"}],
    )
    assert "I have work → I have worked" in text
    assert "(none)" not in text


def test_pricing():
    assert pricing.token_cost("claude-opus-5", 1_000_000, 0) == Decimal("5.000000")
    assert pricing.token_cost("claude-sonnet-5", 0, 1_000_000) == Decimal("10.000000")
    assert pricing.token_cost("claude-opus-5", 0, 0, 1_000_000) == Decimal("0.500000")
    assert pricing.audio_cost("whisper-1", 60) == Decimal("0.006000")
    assert pricing.token_cost("unknown", 100, 100) == Decimal(0)


@pytest.mark.django_db
def test_fake_llm_generates_one_question_per_slot_without_repeats(global_categories):
    FakeLLM.reset()
    cats = [global_categories["job-interview"], global_categories["travel"]]
    slots = plan_slots(6, cats, "B1")
    already = [
        (
            "job-interview",
            "[job-interview] Why do you think good customer service matters, and can you give me an example from your life?",
        )
    ]
    result = FakeLLM().parse(
        model="m",
        system="s",
        user=prompts.generation_user(slots, cats, already),
        output_format=GenerationOutput,
    )
    questions = result.parsed.questions
    assert [q.slot for q in questions] == [1, 2, 3, 4, 5, 6]
    assert [q.level for q in questions] == [s.level for s in slots]
    assert len({q.question for q in questions}) == 6
    assert already[0][1] not in {q.question for q in questions}


@pytest.mark.django_db
def test_fake_llm_writes_french_when_the_system_prompt_asks_for_it(global_categories):
    cats = [global_categories["shopping"]]
    slots = plan_slots(2, cats, "A1")
    result = FakeLLM().parse(
        model="m",
        system=prompts.generation_system(FR),
        user=prompts.generation_user(slots, cats, []),
        output_format=GenerationOutput,
    )
    texts = [q.question for q in result.parsed.questions]
    assert all("[shopping]" in t for t in texts)
    assert any("vous" in t or "Racontez" in t for t in texts)
    scenarios = [q.scenario for q in result.parsed.questions if q.scenario]
    assert all(s.startswith("Vous parlez") for s in scenarios)


def test_grammar_issue_types_cover_french_agreement():
    for kind in ("agreement", "verb_form", "negation", "register"):
        assert GrammarIssue(quote="q", correction="c", type=kind, explanation="e").type == kind


def test_fake_llm_scores_short_transcripts_as_one():
    out = (
        FakeLLM()
        .parse(
            model="m", system="s", user='x\n"""\nHello there\n"""', output_format=EvaluationOutput
        )
        .parsed
    )
    assert (out.structure.score, out.grammar.score, out.fluency.score) == (1, 1, 1)
