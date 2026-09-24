from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm as DjangoUserChangeForm
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from apps.accounts.models import LanguageProfile, User, key_hint

PROVIDERS = (("anthropic", "Anthropic", "sk-ant-"), ("openai", "OpenAI", "sk-"))


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


class UserChangeForm(DjangoUserChangeForm):
    """Write-only inputs for the per-user provider keys.

    The stored keys are never rendered back: leave the input blank to keep the current key,
    paste a new one to replace it, or tick "remove" to fall back to the global key.
    """

    new_anthropic_api_key = forms.CharField(
        label="New Anthropic API key",
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "off"}),
        help_text="Paste to set or replace; leave blank to keep the current key.",
    )
    clear_anthropic_api_key = forms.BooleanField(label="Remove Anthropic API key", required=False)
    new_openai_api_key = forms.CharField(
        label="New OpenAI API key",
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "off"}),
        help_text="Paste to set or replace; leave blank to keep the current key.",
    )
    clear_openai_api_key = forms.BooleanField(label="Remove OpenAI API key", required=False)

    class Meta(DjangoUserChangeForm.Meta):
        model = User
        exclude = ["anthropic_api_key", "openai_api_key"]

    @staticmethod
    def _clean_key(value: str, prefix: str, label: str) -> str:
        value = (value or "").strip()
        if not value:
            return ""
        if " " in value or not value.startswith(prefix):
            raise forms.ValidationError(f"This does not look like an {label} key ({prefix}…).")
        return value

    def clean_new_anthropic_api_key(self):
        return self._clean_key(
            self.cleaned_data.get("new_anthropic_api_key", ""), "sk-ant-", "Anthropic"
        )

    def clean_new_openai_api_key(self):
        return self._clean_key(self.cleaned_data.get("new_openai_api_key", ""), "sk-", "OpenAI")

    def save(self, commit=True):
        user = super().save(commit=False)
        now = timezone.now()
        for provider, _label, _prefix in PROVIDERS:
            new_key = self.cleaned_data.get(f"new_{provider}_api_key")
            clear = self.cleaned_data.get(f"clear_{provider}_api_key")
            if clear:
                setattr(user, f"{provider}_api_key", "")
                setattr(user, f"{provider}_api_key_updated_at", None)
            elif new_key:
                setattr(user, f"{provider}_api_key", new_key)
                setattr(user, f"{provider}_api_key_updated_at", now)
        if commit:
            user.save()
        return user


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserChangeForm
    ordering = ["email"]
    list_display = [
        "email",
        "full_name",
        "languages",
        "own_keys",
        "is_staff",
        "is_active",
    ]
    search_fields = ["email", "full_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Profile",
            {"fields": ("full_name", "timezone", "feedback_language")},
        ),
        (
            "Practice",
            {"fields": ("question_mode", "show_thinking_timer")},
        ),
        (
            "AI keys (bring your own key)",
            {
                "description": (
                    "Stored encrypted; never shown again. Without a key of their own the user "
                    "runs on the global keys. Only an OpenAI key → everything (text, "
                    "transcription, speech) runs on OpenAI with that key."
                ),
                "fields": (
                    "api_keys_status",
                    "new_anthropic_api_key",
                    "clear_anthropic_api_key",
                    "new_openai_api_key",
                    "clear_openai_api_key",
                ),
            },
        ),
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
    readonly_fields = ["last_login", "date_joined", "api_keys_status"]
    inlines = [LanguageProfileInline]

    @admin.display(description="Languages")
    def languages(self, user):
        profiles = LanguageProfile.all_users.filter(user=user).order_by("language")
        return ", ".join(
            f"{p.language} {p.level_rating}{'' if p.is_active else ' (paused)'}" for p in profiles
        )

    @admin.display(description="Own keys")
    def own_keys(self, user):
        names = [label for provider, label, _ in PROVIDERS if getattr(user, f"{provider}_api_key")]
        return ", ".join(names) or "—"

    @admin.display(description="Current keys")
    def api_keys_status(self, user):
        rows = []
        for provider, label, _prefix in PROVIDERS:
            value = getattr(user, f"{provider}_api_key", "")
            updated = getattr(user, f"{provider}_api_key_updated_at", None)
            if value:
                when = f", updated {updated:%Y-%m-%d %H:%M}" if updated else ""
                rows.append((label, f"configured ({key_hint(value)}{when})"))
            else:
                rows.append((label, "not configured → global key"))
        return format_html(
            "<ul style='margin:0;padding-left:1em'>{}</ul>",
            format_html_join("", "<li><strong>{}</strong>: {}</li>", rows),
        )
