"""Practised-language registry (docs/PLAN.md addendum: multi-language).

Everything that is *data* about a language lives here: display names, the speech-to-text code,
and the fragments rendered into the v2 prompts. Adding a language is a new `LanguageSpec` plus
fixtures in `apps.ai.clients.fake`; no model or UI change is needed.

Prompt fragments are written in English because the prompts themselves are in English; the model
writes the questions / reads the transcript in the target language.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import models


class LanguageCode(models.TextChoices):
    EN = "en", "English"
    FR = "fr", "French (Canada)"


class UnknownLanguage(ValueError):
    pass


@dataclass(frozen=True)
class LanguageSpec:
    code: str
    name_en: str
    name_pt: str
    whisper_code: str
    teacher_role: str
    target_language_label: str
    learner_context: str
    variety_notes: str
    evaluator_notes: str
    level_examples: dict[str, str]
    filler_examples: str
    typical_errors: str
    speaking_rate_notes: str
    whisper_prompt: str

    def level_examples_block(self) -> str:
        return "\n".join(f"- {level}: {text}" for level, text in self.level_examples.items())


ENGLISH = LanguageSpec(
    code="en",
    name_en="English",
    name_pt="Inglês",
    whisper_code="en",
    teacher_role="ESL teacher",
    target_language_label="English",
    learner_context=(
        "a Brazilian Portuguese speaker preparing to move to Canada and find a job there"
    ),
    variety_notes=(
        "Sound like something a real person would actually say in Canada — an interviewer, a "
        "shop assistant, a neighbour, a border officer, a colleague, a landlord. Natural spoken "
        "English."
    ),
    evaluator_notes="",
    level_examples={
        "A1": (
            "very simple, concrete, about the learner's immediate life; present tense; answerable "
            'with a few short sentences. "What do you usually have for breakfast?"'
        ),
        "A2": (
            "familiar everyday topics; a short description or a simple past narrative; one clear "
            'idea. "Tell me about the last time you went to a supermarket. What did you buy?"'
        ),
        "B1": (
            "personal experiences, opinions with reasons, plans, simple comparisons; classic "
            'interview questions. "Why do you want to work in customer service?" / "Tell me about '
            'a time you helped a colleague."'
        ),
        "B2": (
            "hypothetical or abstract situations, justifying trade-offs, persuading, handling "
            'conflict; behavioural interview questions with two parts. "Describe a time you '
            'disagreed with a manager. How did you handle it, and what would you do differently?"'
        ),
        "C1": (
            'nuanced, evaluative, multi-part questions requiring structured argument. "How do you '
            "think remote work has changed what employers expect from new hires, and how would "
            'you position yourself for that?"'
        ),
        "C2": ("like C1 with subtle framing, irony, or the need to weigh several perspectives."),
    },
    filler_examples="um, uh, like, you know, so",
    typical_errors="verb tense, subject–verb agreement, missing articles",
    speaking_rate_notes=(
        "Use the speaking rate given with the transcript only as a weak secondary signal (below "
        "~70 words per minute suggests heavy hesitation; 100–150 is typical relaxed conversation)."
    ),
    whisper_prompt=(
        "Um, uh, so, like... I think, hmm, you know, I mean, well... Let me think. Okay, so "
        "basically..."
    ),
)

FRENCH_CA = LanguageSpec(
    code="fr",
    name_en="French (Canada/Québec)",
    name_pt="Francês (Canadá/Québec)",
    whisper_code="fr",
    teacher_role="FLE teacher (français langue étrangère)",
    target_language_label="Canadian French (Québec)",
    learner_context=(
        "a Brazilian Portuguese speaker who also studies English, preparing to live, settle and "
        "work in Québec (Canada): immigration procedures, housing, everyday errands and job "
        "interviews"
    ),
    variety_notes=(
        "Sound like something a real person would actually say in Québec — un recruteur or a "
        "gestionnaire in an interview, a commis at the épicerie, the pharmacie or the SAQ, a "
        "propriétaire (landlord), an agent d'immigration or a douanier at the airport, a voisin, "
        "a collègue, a préposé at a service counter (Service Canada, SAAQ, RAMQ, a caisse). "
        "Natural spoken Québec French: use everyday Québec vocabulary where it is what people "
        "actually say (fin de semaine, magasiner, dépanneur, déjeuner/dîner/souper, courriel, "
        "cellulaire, stationnement, gestionnaire, cégep), but avoid heavy slang and joual "
        "spellings. Register: « vous » in interviews and with officers, landlords and staff; "
        "« tu » with neighbours and colleagues — stay consistent inside one question. Write in "
        "standard orthography with full negation (« ne … pas »)."
    ),
    evaluator_notes=(
        "Accept France-French forms as fully correct (week-end, faire du shopping, parking, "
        "petit-déjeuner, portable). Dropping « ne » in spoken negation and Québec discourse "
        "markers (là, tsé, faque, ben) are normal spoken usage — never list them as grammar "
        "errors. Common anglicisms heard in Québec are acceptable unless they hurt understanding. "
        'Mixing tu/vous counts as an issue of type "register" only when the scenario is formal. '
        "Watch for Portuguese interference: false friends, gender transferred from Portuguese, "
        "« avoir » vs « être » as the auxiliary."
    ),
    level_examples={
        "A1": (
            "very simple, concrete, about the learner's immediate life; present tense; answerable "
            "with a few short sentences. « Qu'est-ce que vous mangez d'habitude le matin ? » / "
            "« Parlez-moi de votre quartier. »"
        ),
        "A2": (
            "familiar everyday topics; a short description or a simple past narrative; one clear "
            "idea. « Racontez-moi la dernière fois que vous êtes allé à l'épicerie. Qu'est-ce que "
            "vous avez acheté ? »"
        ),
        "B1": (
            "personal experiences, opinions with reasons, plans, simple comparisons; classic "
            "interview questions. « Pourquoi voulez-vous travailler au service à la clientèle ? » "
            "/ « Parlez-moi d'une fois où vous avez aidé un collègue. »"
        ),
        "B2": (
            "hypothetical or abstract situations, justifying trade-offs, persuading, handling "
            "conflict; behavioural interview questions with two parts. « Décrivez une situation "
            "où vous n'étiez pas d'accord avec votre gestionnaire. Comment avez-vous géré ça, et "
            "que feriez-vous différemment ? »"
        ),
        "C1": (
            "nuanced, evaluative, multi-part questions requiring structured argument. « Selon "
            "vous, comment le télétravail a-t-il changé ce que les employeurs attendent des "
            "nouveaux employés, et comment vous positionneriez-vous par rapport à ça ? »"
        ),
        "C2": ("like C1 with subtle framing, irony, or the need to weigh several perspectives."),
    },
    filler_examples="euh, ben, là, tsé, genre, comme, faque, en fait, je veux dire, disons",
    typical_errors=(
        "gender and number agreement, choice of auxiliary and past-participle agreement in the "
        "passé composé, verb forms after « il faut que », prepositions with places (à/en/au), "
        "partitive articles, pronoun placement (y, en, direct/indirect objects)"
    ),
    speaking_rate_notes=(
        "Treat the speaking rate given with the transcript as an even weaker signal than in "
        "English: below ~70 words per minute suggests heavy hesitation; roughly 110–160 is relaxed "
        "conversation. Contractions (j'ai, qu'est-ce) count as one word."
    ),
    whisper_prompt=(
        "Euh, ben, là, tsé... Je pense que, hmm, en fait, je veux dire, bon... Laissez-moi "
        "réfléchir. Ok, faque, disons que..."
    ),
)

LANGUAGES: dict[str, LanguageSpec] = {spec.code: spec for spec in (ENGLISH, FRENCH_CA)}


def language_codes() -> list[str]:
    return list(LANGUAGES)


def get_language(code: str) -> LanguageSpec:
    try:
        return LANGUAGES[code]
    except KeyError:
        raise UnknownLanguage(f"Unknown language: {code!r}") from None


def is_known_language(code: str | None) -> bool:
    return code in LANGUAGES
