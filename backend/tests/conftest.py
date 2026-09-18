from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.cards.models import Card, Category, CEFRLevel
from apps.core.context import owner_context
from apps.scheduling.models import SchedulerState


@pytest.fixture
def user_a(db) -> User:
    return User.objects.create_user(
        email="ana@example.com", password="pass12345", full_name="Ana", timezone="America/Sao_Paulo"
    )


@pytest.fixture
def user_b(db) -> User:
    return User.objects.create_user(
        email="bruno@example.com",
        password="pass12345",
        full_name="Bruno",
        timezone="America/Toronto",
    )


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
    from apps.ai.clients.fake import FakeLLM, FakeProbe, FakeTranscriber

    FakeLLM.reset()
    FakeTranscriber.reset()
    FakeProbe.reset()
    yield
    FakeLLM.reset()
    FakeTranscriber.reset()
    FakeProbe.reset()


@pytest.fixture
def audio_file():
    from django.core.files.uploadedfile import SimpleUploadedFile

    def _make(name: str = "recording.webm", content_type: str = "audio/webm", size: int = 2048):
        content = (b"\x1aE\xdf\xa3" + b"0" * size) if size > 0 else b""
        return SimpleUploadedFile(name, content, content_type=content_type)

    return _make
