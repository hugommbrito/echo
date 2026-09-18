from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["email"]
    list_display = [
        "email",
        "full_name",
        "level_rating",
        "counted_attempts",
        "is_staff",
        "is_active",
    ]
    search_fields = ["email", "full_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Profile",
            {"fields": ("full_name", "timezone", "feedback_language", "default_new_cards_per_day")},
        ),
        ("Level", {"fields": ("level_rating", "level_rating_initial", "counted_attempts")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "full_name", "password1", "password2")}),
        ("Level", {"fields": ("level_rating",)}),
        ("Profile", {"fields": ("timezone", "feedback_language", "default_new_cards_per_day")}),
    )
    readonly_fields = ["last_login", "date_joined"]
