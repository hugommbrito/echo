from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import LanguageProfile, User
from apps.cards.models import Card, Category, CEFRLevel
from apps.core.context import owner_context
from apps.scheduling.models import SchedulerState


def _profile(user: User, language: str = "en", rating: int = 1150, **extra) -> LanguageProfile:
    return LanguageProfile.all_users.create(
        user=user,
        language=language,
        level_rating=rating,
        level_rating_initial=rating,
        **extra,
    )


@pytest.fixture
def user_a(db) -> User:
    user = User.objects.create_user(
        email="ana@example.com", password="pass12345", full_name="Ana", timezone="America/Sao_Paulo"
    )
    _profile(user)
    return user


@pytest.fixture
def user_b(db) -> User:
    user = User.objects.create_user(
        email="bruno@example.com",
        password="pass12345",
        full_name="Bruno",
        timezone="America/Toronto",
    )
    _profile(user)
    return user


@pytest.fixture
def make_profile(db):
    """Create (or replace) a language profile for a user, outside any owner context."""

    def _make(
        user: User,
        language: str,
        *,
        rating: int | None = None,
        starting_level: str | None = None,
        is_active: bool = True,
        default_new_cards_per_day: int = 3,
        counted_attempts: int = 0,
    ) -> LanguageProfile:
        from apps.leveling.elo import rating_for_level

        if rating is None:
            rating = rating_for_level(starting_level or "A1")
        LanguageProfile.all_users.filter(user=user, language=language).delete()
        return _profile(
            user,
            language,
            rating,
            is_active=is_active,
            default_new_cards_per_day=default_new_cards_per_day,
            counted_attempts=counted_attempts,
        )

    return _make


@pytest.fixture
def admin_user(db) -> User:
    return User.objects.create_superuser(email="admin@example.com", password="pass12345")


@pytest.fixture
def as_user():
    """`with as_user(user): ...` binds the owner context for direct ORM access in tests."""

    def _bind(user):
        return owner_context(user.pk)

    return _bind


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def client_a(user_a) -> APIClient:
    client = APIClient()
    client.force_login(user_a)
    return client


@pytest.fixture
def client_b(user_b) -> APIClient:
    client = APIClient()
    client.force_login(user_b)
    return client


@pytest.fixture
def global_categories(db) -> dict[str, Category]:
    return {c.slug: c for c in Category.objects.filter(owner__isnull=True)}


@pytest.fixture
def make_card(db):
    """Create a card (+ scheduler state) for a user; runs inside the user's owner context."""

    def _make(
        user: User,
        category: Category | None = None,
        *,
        question: str = "Tell me about yourself.",
        level: str = CEFRLevel.B1,
        language: str = "en",
        difficulty_rating: int | None = None,
        probe: str = "none",
        status: str = "active",
        maturity: str = "new",
        due_date: dt.date | None = None,
        interval_days: int = 0,
        repetitions: int = 0,
        ease: Decimal = Decimal("2.50"),
        key_points: list[str] | None = None,
        session=None,
    ) -> Card:
        from apps.leveling.elo import rating_for_level

        category = category or Category.objects.filter(owner__isnull=True).first()
        with owner_context(user.pk):
            card = Card.objects.create(
                category=category,
                language=language,
                question_text=question,
                scenario=None,
                key_points=key_points or ["gives one concrete example", "explains why"],
                cefr_level=level,
                difficulty_rating=(
                    difficulty_rating if difficulty_rating is not None else rating_for_level(level)
                ),
                probe=probe,
                status=status,
                created_in_session=session,
                generation_model="test",
                prompt_version="v1",
            )
            SchedulerState.objects.create(
                card=card,
                maturity=maturity,
                due_date=due_date,
                interval_days=interval_days,
                repetitions=repetitions,
                ease_factor=ease,
            )
        return card

    return _make


@pytest.fixture(autouse=True)
def _reset_fakes():
    from apps.ai.clients.fake import FakeLLM, FakeProbe, FakeTranscriber, FakeTTS

    for fake in (FakeLLM, FakeTranscriber, FakeProbe, FakeTTS):
        fake.reset()
    yield
    for fake in (FakeLLM, FakeTranscriber, FakeProbe, FakeTTS):
        fake.reset()


@pytest.fixture
def audio_file():
    from django.core.files.uploadedfile import SimpleUploadedFile

    def _make(name: str = "recording.webm", content_type: str = "audio/webm", size: int = 2048):
        content = (b"\x1aE\xdf\xa3" + b"0" * size) if size > 0 else b""
        return SimpleUploadedFile(name, content, content_type=content_type)

    return _make
