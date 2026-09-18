"""Create (or reset) a learner from the CLI — handy for local dev and E2E runs.

python manage.py create_user aluna@example.com --password s3cret --name "Ana" --rating 1150
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create or update a learner (email login). Use --staff for an admin."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--password", required=True)
        parser.add_argument("--name", default="")
        parser.add_argument("--timezone", default="America/Sao_Paulo")
        parser.add_argument(
            "--rating", type=int, default=None, help="Initial ELO rating (default 1150)"
        )
        parser.add_argument("--staff", action="store_true", help="Grant Django admin access")

    def handle(self, *args, **options):
        email = User.objects.normalize_email(options["email"]).lower()
        rating = options["rating"]
        if rating is None:
            rating = settings.ECHO_LEVEL_INITIAL_RATING
        if not settings.ECHO_LEVEL_RATING_MIN <= rating <= settings.ECHO_LEVEL_RATING_MAX:
            raise CommandError(
                f"rating must be between {settings.ECHO_LEVEL_RATING_MIN} "
                f"and {settings.ECHO_LEVEL_RATING_MAX}"
            )
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name": options["name"],
                "timezone": options["timezone"],
                "level_rating": rating,
                "level_rating_initial": rating,
            },
        )
        user.set_password(options["password"])
        if options["name"]:
            user.full_name = options["name"]
        user.timezone = options["timezone"]
        if options["staff"]:
            user.is_staff = True
            user.is_superuser = True
        if not created and options["rating"] is not None:
            user.level_rating = rating
            user.level_rating_initial = rating
            user.counted_attempts = 0
        user.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if created else 'Updated'} {user.email} "
                f"(rating {user.level_rating}, tz {user.timezone})"
            )
        )
