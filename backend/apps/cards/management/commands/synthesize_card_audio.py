"""Backfill the spoken question (TTS) for cards created before the feature or after a voice change.

python manage.py synthesize_card_audio            # enqueue one Celery task per card without audio
python manage.py synthesize_card_audio --sync --limit 2 --language fr   # audition a voice inline
python manage.py synthesize_card_audio --force --user ana@example.com  # re-synthesise everything
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.ai import services as ai_services
from apps.ai.exceptions import AIError
from apps.cards.models import Card, CardStatus
from apps.cards.tasks import synthesize_question_audio
from apps.core.context import owner_context
from apps.core.tasks import enqueue


class Command(BaseCommand):
    help = "Generate the spoken question (TTS) for cards that do not have one yet."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="Only this user's cards (e-mail)")
        parser.add_argument("--language", help="Only this practised language (en, fr)")
        parser.add_argument("--include-suspended", action="store_true")
        parser.add_argument(
            "--force", action="store_true", help="Re-synthesise cards that already have audio"
        )
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument(
            "--sync", action="store_true", help="Call the provider inline instead of enqueueing"
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        qs = Card.all_users.select_related("user").order_by("created_at")
        if not options["force"]:
            qs = qs.filter(question_audio="")
        if not options["include_suspended"]:
            qs = qs.filter(status=CardStatus.ACTIVE)
        if options["user"]:
            qs = qs.filter(user__email__iexact=options["user"])
        if options["language"]:
            qs = qs.filter(language=options["language"])
        if options["limit"]:
            qs = qs[: options["limit"]]
        cards = list(qs)
        self.stdout.write(f"{len(cards)} card(s) to process")
        if options["dry_run"]:
            return
        done = failed = 0
        for card in cards:
            with owner_context(card.user_id):
                if options["sync"]:
                    try:
                        ai_services.synthesize_question_audio(card=card, force=options["force"])
                        done += 1
                        self.stdout.write(
                            f"ok  {card.language} {card.id} {card.question_text[:60]}"
                        )
                    except AIError as exc:
                        failed += 1
                        self.stderr.write(f"err {card.id}: {ai_services.redact(str(exc))}")
                else:
                    enqueue(
                        synthesize_question_audio,
                        card_id=str(card.id),
                        user_id=str(card.user_id),
                        force=options["force"],
                    )
                    done += 1
        verb = "synthesised" if options["sync"] else "enqueued"
        self.stdout.write(f"{verb}={done} failed={failed}")
