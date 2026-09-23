"""The multi-language data migrations copy the legacy English state without losing anything."""

import datetime as dt
import uuid

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = [
    ("accounts", "0001_initial"),
    ("cards", "0003_seed_global_categories"),
    ("practice", "0001_initial"),
    ("leveling", "0001_initial"),
    ("ai", "0001_initial"),
    ("scheduling", "0001_initial"),
]
AFTER = [
    ("accounts", "0003_backfill_en_language_profiles"),
    ("cards", "0004_card_language"),
    ("practice", "0003_backfill_session_plans"),
    ("leveling", "0002_levellog_language"),
    ("ai", "0002_airequestlog_language"),
]


@pytest.mark.django_db(transaction=True)
def test_legacy_english_state_is_migrated_into_profiles_and_plans():
    executor = MigrationExecutor(connection)
    executor.migrate(BEFORE)
    apps = executor.loader.project_state(BEFORE).apps

    User = apps.get_model("accounts", "User")
    Category = apps.get_model("cards", "Category")
    Card = apps.get_model("cards", "Card")
    DailySession = apps.get_model("practice", "DailySession")
    SessionNewCard = apps.get_model("practice", "SessionNewCard")

    joined = dt.datetime(2026, 9, 1, 12, 0, tzinfo=dt.UTC)
    user = User.objects.create(
        email="legacy@example.com",
        password="x",
        level_rating=1234,
        level_rating_initial=1150,
        counted_attempts=7,
        default_new_cards_per_day=5,
        date_joined=joined,
    )
    category = Category.objects.filter(owner__isnull=True).first()
    card = Card.objects.create(
        id=uuid.uuid4(),
        user=user,
        category=category,
        question_text="Tell me about your city.",
        cefr_level="A2",
        difficulty_rating=1100,
    )
    session = DailySession.objects.create(
        user=user,
        session_date=dt.date(2026, 9, 21),
        new_cards_target=4,
        rating_at_start=1234,
        status="failed",
        generation_error="provider down",
    )
    SessionNewCard.objects.create(
        user=user, session=session, card=card, position=1, origin="generated"
    )

    executor = MigrationExecutor(connection)
    executor.migrate(AFTER)
    apps = executor.loader.project_state(AFTER).apps

    LanguageProfile = apps.get_model("accounts", "LanguageProfile")
    profile = LanguageProfile.objects.get(user_id=user.pk)
    assert profile.language == "en"
    assert profile.level_rating == 1234
    assert profile.level_rating_initial == 1150
    assert profile.counted_attempts == 7
    assert profile.default_new_cards_per_day == 5
    assert profile.is_active is True
    assert profile.activated_at == joined

    Card = apps.get_model("cards", "Card")
    assert Card.objects.get(pk=card.pk).language == "en"

    SessionLanguagePlan = apps.get_model("practice", "SessionLanguagePlan")
    plan = SessionLanguagePlan.objects.get(session_id=session.pk)
    assert (plan.language, plan.new_cards_target, plan.rating_at_start) == ("en", 4, 1234)
    assert plan.generation_status == "failed"
    assert plan.generation_error == "provider down"
    assert plan.generated_count == 1

    # Bring the test database back to the latest state for the other tests.
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())
