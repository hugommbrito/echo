"""The language registry is data: every spec must be complete enough to render the prompts."""

import pytest

from apps.core.languages import (
    LANGUAGES,
    LanguageCode,
    UnknownLanguage,
    get_language,
    is_known_language,
    language_codes,
)

CEFR = ["A1", "A2", "B1", "B2", "C1", "C2"]


def test_registry_matches_model_choices():
    assert language_codes() == list(LanguageCode.values) == ["en", "fr"]


@pytest.mark.parametrize("code", ["en", "fr"])
def test_every_spec_is_complete(code):
    spec = get_language(code)
    assert spec.code == code
    assert list(spec.level_examples) == CEFR
    for text in spec.level_examples.values():
        assert text.strip()
    for field in (
        "name_en",
        "name_pt",
        "whisper_code",
        "teacher_role",
        "target_language_label",
        "learner_context",
        "variety_notes",
        "filler_examples",
        "typical_errors",
        "speaking_rate_notes",
        "whisper_prompt",
    ):
        assert getattr(spec, field).strip(), field
    block = spec.level_examples_block()
    assert block.startswith("- A1: ") and "- C2: " in block


def test_french_is_quebec_flavoured():
    fr = LANGUAGES["fr"]
    assert "Québec" in fr.target_language_label
    assert "FLE" in fr.teacher_role
    assert "euh" in fr.filler_examples and "euh" in fr.whisper_prompt.lower()
    assert "épicerie" in fr.variety_notes


def test_unknown_language():
    assert not is_known_language("xx") and not is_known_language(None)
    with pytest.raises(UnknownLanguage):
        get_language("xx")
