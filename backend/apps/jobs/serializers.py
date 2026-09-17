from rest_framework import serializers

from .models import FavoriteJob, Job, JobNotification, JobSource, UserJobFilter


class JobSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobSource
        fields = ["id", "name", "url", "icon", "is_active", "last_sync"]


class _IsFavoritedMixin(serializers.Serializer):
    """SerializerMethodField, общий для списка и деталей вакансии."""

    is_favorited = serializers.SerializerMethodField()

    def get_is_favorited(self, obj: Job) -> bool:
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        favorite_ids = self.context.get("favorite_job_ids")
        if favorite_ids is not None:
            return obj.id in favorite_ids
        return FavoriteJob.objects.filter(user=request.user, job=obj).exists()


class JobListSerializer(_IsFavoritedMixin, serializers.ModelSerializer):
    source = serializers.CharField(source="source.name", read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "source",
            "title",
            "company",
            "salary_from",
            "salary_to",
            "currency",
            "location",
            "experience_level",
            "employment_type",
            "required_skills",
            "url",
            "posted_at",
            "is_favorited",
        ]


class JobDetailSerializer(_IsFavoritedMixin, serializers.ModelSerializer):
    source = JobSourceSerializer(read_only=True)

    class Meta:
        model = Job
        fields = "__all__"


class UserJobFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserJobFilter
        fields = [
            "id",
            "min_salary",
            "max_salary",
            "locations",
            "experience_levels",
            "keywords",
            "excluded_keywords",
            "job_types",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class JobNotificationSerializer(serializers.ModelSerializer):
    job = JobListSerializer(read_only=True)

    class Meta:
        model = JobNotification
        fields = ["id", "job", "notified_at", "sent_to_telegram", "is_read"]
        read_only_fields = ["id", "job", "notified_at", "sent_to_telegram"]
