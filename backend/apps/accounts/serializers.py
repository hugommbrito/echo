from __future__ import annotations

import zoneinfo

from django.conf import settings
from rest_framework import serializers

from apps.accounts.models import User


class LevelSerializer(serializers.Serializer):
    rating = serializers.IntegerField()
    band = serializers.CharField()
    provisional = serializers.BooleanField()
    counted_attempts = serializers.IntegerField()
    initial_rating = serializers.IntegerField()


class UserSerializer(serializers.ModelSerializer):
    level = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "timezone",
            "feedback_language",
            "default_new_cards_per_day",
            "is_staff",
            "level",
        ]
        read_only_fields = ["id", "email", "full_name", "is_staff", "level"]

    def get_level(self, user: User) -> dict:
        return LevelSerializer(
            {
                "rating": user.level_rating,
                "band": user.level_band,
                "provisional": user.level_provisional,
                "counted_attempts": user.counted_attempts,
                "initial_rating": user.level_rating_initial or user.level_rating,
            }
        ).data

    def validate_timezone(self, value: str) -> str:
        try:
            zoneinfo.ZoneInfo(value)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError):
            raise serializers.ValidationError("Unknown timezone.", code="invalid_timezone")
        return value

    def validate_default_new_cards_per_day(self, value: int) -> int:
        if not 0 <= value <= settings.ECHO_MAX_NEW_CARDS_PER_DAY:
            raise serializers.ValidationError(
                f"Must be between 0 and {settings.ECHO_MAX_NEW_CARDS_PER_DAY}.", code="out_of_range"
            )
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, style={"input_type": "password"})
