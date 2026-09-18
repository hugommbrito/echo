from rest_framework import serializers

from apps.leveling.elo import band_for_rating
from apps.leveling.models import LevelLog


class LevelLogSerializer(serializers.ModelSerializer):
    band_before = serializers.SerializerMethodField()
    band_after = serializers.SerializerMethodField()

    class Meta:
        model = LevelLog
        fields = [
            "rating_before",
            "rating_after",
            "delta",
            "expected",
            "actual",
            "question_rating",
            "k_factor",
            "band_before",
            "band_after",
            "logged_on",
        ]

    def get_band_before(self, log: LevelLog) -> str:
        return band_for_rating(log.rating_before)

    def get_band_after(self, log: LevelLog) -> str:
        return band_for_rating(log.rating_after)
