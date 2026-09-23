"""Data migration: every existing learner gets an English profile copied from the User row.

Reversible: the `en` profile is copied back onto the User columns and the profiles are deleted.
"""

from django.db import migrations

LEGACY_LANGUAGE = "en"


def forwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    LanguageProfile = apps.get_model("accounts", "LanguageProfile")
    for user in User.objects.all().iterator():
        LanguageProfile.objects.get_or_create(
            user=user,
            language=LEGACY_LANGUAGE,
            defaults={
                "level_rating": user.level_rating,
                "level_rating_initial": user.level_rating_initial or user.level_rating,
                "counted_attempts": user.counted_attempts,
                "default_new_cards_per_day": user.default_new_cards_per_day,
                "is_active": True,
                "activated_at": user.date_joined,
            },
        )


def backwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    LanguageProfile = apps.get_model("accounts", "LanguageProfile")
    for profile in LanguageProfile.objects.filter(language=LEGACY_LANGUAGE).iterator():
        User.objects.filter(pk=profile.user_id).update(
            level_rating=profile.level_rating,
            level_rating_initial=profile.level_rating_initial,
            counted_attempts=profile.counted_attempts,
            default_new_cards_per_day=profile.default_new_cards_per_day,
        )
    LanguageProfile.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_languageprofile")]

    operations = [migrations.RunPython(forwards, backwards)]
