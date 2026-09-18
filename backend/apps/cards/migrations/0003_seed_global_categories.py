from django.db import migrations

from apps.cards.seed_categories import SEED_CATEGORIES


def seed(apps, schema_editor):
    Category = apps.get_model("cards", "Category")
    for data in SEED_CATEGORIES:
        Category.objects.update_or_create(
            owner=None, slug=data["slug"], defaults={k: v for k, v in data.items() if k != "slug"}
        )


def unseed(apps, schema_editor):
    Category = apps.get_model("cards", "Category")
    Category.objects.filter(owner=None, slug__in=[d["slug"] for d in SEED_CATEGORIES]).delete()


class Migration(migrations.Migration):
    dependencies = [("cards", "0002_initial")]
    operations = [migrations.RunPython(seed, unseed)]
