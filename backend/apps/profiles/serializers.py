from rest_framework import serializers

from .models import ProfileSet


class ProfileSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfileSet
        fields = [
            "id",
            "name",
            "phone",
            "email",
            "resume",
            "github_url",
            "cover_letter",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
