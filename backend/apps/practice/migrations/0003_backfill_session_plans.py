"""Data migration: one English plan per existing daily session (target + rating snapshot)."""

from django.db import migrations

LEGACY_LANGUAGE = "en"


def forwards(apps, schema_editor):
    DailySession = apps.get_model("practice", "DailySession")
    SessionLanguagePlan = apps.get_model("practice", "SessionLanguagePlan")
    SessionNewCard = apps.get_model("practice", "SessionNewCard")
    for session in DailySession.objects.all().iterator():
        generated = SessionNewCard.objects.filter(session=session, origin="generated").count()
        SessionLanguagePlan.objects.get_or_create(
            user_id=session.user_id,
            session=session,
            language=LEGACY_LANGUAGE,
            defaults={
                "new_cards_target": session.new_cards_target,
                "rating_at_start": session.rating_at_start,
                "generation_status": "failed" if session.status == "failed" else "ready",
                "generation_error": session.generation_error,
                "generated_count": generated,
            },
        )


def backwards(apps, schema_editor):
    DailySession = apps.get_model("practice", "DailySession")
    SessionLanguagePlan = apps.get_model("practice", "SessionLanguagePlan")
    for plan in SessionLanguagePlan.objects.filter(language=LEGACY_LANGUAGE).iterator():
        DailySession.objects.filter(pk=plan.session_id).update(
            new_cards_target=plan.new_cards_target, rating_at_start=plan.rating_at_start
        )
    SessionLanguagePlan.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("practice", "0002_sessionlanguageplan")]

    operations = [migrations.RunPython(forwards, backwards)]
