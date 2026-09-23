from django.contrib import admin

from apps.cards.models import Card, Category
from apps.core.admin import OwnedModelAdmin


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "scope", "owner", "is_active", "sort_order"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Scope")
    def scope(self, obj):
        return obj.scope


@admin.register(Card)
class CardAdmin(OwnedModelAdmin):
    list_display = [
        "question_text",
        "language",
        "category",
        "cefr_level",
        "difficulty_rating",
        "probe",
        "status",
    ]
    list_filter = ["language", "status", "cefr_level", "probe"]
    search_fields = ["question_text"]
    readonly_fields = ["question_text", "key_points", "generation_model", "prompt_version"]
