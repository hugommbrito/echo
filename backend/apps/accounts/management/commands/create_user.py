"""Create (or reset) a learner from the CLI — handy for local dev and E2E runs.

python manage.py create_user aluna@example.com --password s3cret --name "Ana" \
    --language en:1150 --language fr:900
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import LanguageProfile, User
from apps.core.languages import is_known_language


def parse_language(raw: str) -> tuple[str, int | None]:
    code, _, rating = raw.partition(":")
    if not is_known_language(code):
        raise CommandError(f"unknown language: {code!r}")
    if not rating:
        return code, None
    try:
        return code, int(rating)
    except ValueError:
        raise CommandError(f"rating must be an integer: {raw!r}")


class Command(BaseCommand):
    help = "Create or update a learner (email login). Use --staff for an admin."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--password", required=True)
        parser.add_argument("--name", default="")
        parser.add_argument("--timezone", default="America/Sao_Paulo")
        parser.add_argument(
            "--language",
            action="append",
            dest="languages",
            metavar="CODE[:RATING]",
            help="Practised language with optional initial ELO rating; repeatable (default: en)",
        )
        parser.add_argument(
            "--rating", type=int, default=None, help="Alias for --language en:RATING"
        )
        parser.add_argument("--staff", action="store_true", help="Grant Django admin access")

    def handle(self, *args, **options):
        email = User.objects.normalize_email(options["email"]).lower()
        languages = [parse_language(raw) for raw in (options["languages"] or [])]
        if options["rating"] is not None:
            languages = [(c, r) for c, r in languages if c != settings.ECHO_DEFAULT_LANGUAGE]
            languages.append((settings.ECHO_DEFAULT_LANGUAGE, options["rating"]))
        explicit = bool(languages)
        if not languages:
            languages = [(settings.ECHO_DEFAULT_LANGUAGE, None)]
        for _, rating in languages:
            if rating is not None and not (
                settings.ECHO_LEVEL_RATING_MIN <= rating <= settings.ECHO_LEVEL_RATING_MAX
            ):
                raise CommandError(
                    f"rating must be between {settings.ECHO_LEVEL_RATING_MIN} "
                    f"and {settings.ECHO_LEVEL_RATING_MAX}"
                )

        user, created = User.objects.get_or_create(
            email=email, defaults={"full_name": options["name"], "timezone": options["timezone"]}
        )
        user.set_password(options["password"])
        if options["name"]:
            user.full_name = options["name"]
        user.timezone = options["timezone"]
        if options["staff"]:
            user.is_staff = True
            user.is_superuser = True
        user.save()

        summary = []
        for code, rating in languages:
            profile = LanguageProfile.all_users.filter(user=user, language=code).first()
            if profile is None:
                value = rating if rating is not None else settings.ECHO_LEVEL_INITIAL_RATING
                profile = LanguageProfile.all_users.create(
                    user=user, language=code, level_rating=value, level_rating_initial=value
                )
            elif explicit and rating is not None:
                profile.level_rating = rating
                profile.level_rating_initial = rating
                profile.counted_attempts = 0
                profile.is_active = True
                profile.save(
                    update_fields=[
                        "level_rating",
                        "level_rating_initial",
                        "counted_attempts",
                        "is_active",
                        "updated_at",
                    ]
                )
            summary.append(f"{profile.language} {profile.level_rating}")
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if created else 'Updated'} {user.email} "
                f"({', '.join(summary)}; tz {user.timezone})"
            )
        )
