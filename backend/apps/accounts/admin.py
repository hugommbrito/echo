from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import LanguageProfile, User


class LanguageProfileInline(admin.TabularInline):
    model = LanguageProfile
    extra = 0
    fields = [
        "language",
        "is_active",
        "level_rating",
        "level_rating_initial",
        "counted_attempts",
        "default_new_cards_per_day",
        "activated_at",
    ]

    def get_queryset(self, request):
        return LanguageProfile.all_users.get_queryset()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["email"]
    list_display = [
        "email",
        "full_name",
        "languages",
        "is_staff",
        "is_active",
    ]
    search_fields = ["email", "full_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name", "timezone", "feedback_language")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "full_name", "password1", "password2")}),
        ("Profile", {"fields": ("timezone", "feedback_language")}),
    )
    readonly_fields = ["last_login", "date_joined"]
    inlines = [LanguageProfileInline]

    @admin.display(description="Languages")
    def languages(self, user):
        profiles = LanguageProfile.all_users.filter(user=user).order_by("language")
        return ", ".join(
            f"{p.language} {p.level_rating}{'' if p.is_active else ' (paused)'}" for p in profiles
        )
