from __future__ import annotations

import zoneinfo

from django.conf import settings
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import LanguageProfile, User
from apps.core.languages import LanguageCode, get_language


class LevelSerializer(serializers.Serializer):
    rating = serializers.IntegerField()
    band = serializers.CharField()
    provisional = serializers.BooleanField()
    counted_attempts = serializers.IntegerField()
    initial_rating = serializers.IntegerField()


class LanguageProfileSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="language", read_only=True)
    name = serializers.SerializerMethodField()
    level = serializers.SerializerMethodField()

    class Meta:
        model = LanguageProfile
        fields = ["code", "name", "is_active", "default_new_cards_per_day", "activated_at", "level"]
        read_only_fields = ["code", "name", "activated_at", "level"]

    def get_name(self, profile: LanguageProfile) -> str:
        return get_language(profile.language).name_pt

    @extend_schema_field(LevelSerializer)
    def get_level(self, profile: LanguageProfile) -> dict:
        return LevelSerializer(
            {
                "rating": profile.level_rating,
                "band": profile.level_band,
                "provisional": profile.level_provisional,
                "counted_attempts": profile.counted_attempts,
                "initial_rating": profile.level_rating_initial,
            }
        ).data

    def validate_default_new_cards_per_day(self, value: int) -> int:
        if not 0 <= value <= settings.ECHO_MAX_NEW_CARDS_PER_DAY:
            raise serializers.ValidationError(
                f"Must be between 0 and {settings.ECHO_MAX_NEW_CARDS_PER_DAY}.", code="out_of_range"
            )
        return value


class LanguageActivateSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=LanguageCode.choices)
    starting_level = serializers.ChoiceField(
        choices=[(lvl, lvl) for lvl in settings.ECHO_SELF_PLACEMENT_LEVELS],
        required=False,
        default=settings.ECHO_SELF_PLACEMENT_DEFAULT_LEVEL,
    )


class LanguageCatalogSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    name_en = serializers.CharField()
    starting_levels = serializers.ListField(child=serializers.CharField())


class UserSerializer(serializers.ModelSerializer):
    languages = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "timezone",
            "feedback_language",
            "is_staff",
            "languages",
        ]
        read_only_fields = ["id", "email", "full_name", "is_staff", "languages"]

    @extend_schema_field(LanguageProfileSerializer(many=True))
    def get_languages(self, user: User) -> list[dict]:
        from apps.accounts.services import all_profiles

        return LanguageProfileSerializer(all_profiles(user), many=True).data

    def validate_timezone(self, value: str) -> str:
        try:
            zoneinfo.ZoneInfo(value)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError("Unknown timezone.", code="invalid_timezone")
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, style={"input_type": "password"})
