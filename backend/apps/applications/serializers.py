from rest_framework import serializers

from apps.jobs.models import Job
from apps.jobs.serializers import JobListSerializer
from apps.profiles.models import ProfileSet

from .models import Application


class ApplicationSerializer(serializers.ModelSerializer):
    job = JobListSerializer(read_only=True)
    job_id = serializers.PrimaryKeyRelatedField(queryset=Job.objects.all(), source="job", write_only=True)
    profile_set = serializers.PrimaryKeyRelatedField(
        queryset=ProfileSet.objects.none(), allow_null=True, required=False
    )
    profile_set_name = serializers.CharField(source="profile_set.name", read_only=True, default=None)

    class Meta:
        model = Application
        fields = [
            "id",
            "job",
            "job_id",
            "status",
            "profile_set",
            "profile_set_name",
            "note",
            "applied_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "applied_at", "created_at", "updated_at"]

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            # Нельзя привязать отклик к чужому сету профиля.
            fields["profile_set"].queryset = ProfileSet.objects.filter(user=request.user)
        return fields

    def create(self, validated_data):
        # Один отклик на вакансию: повторный POST обновляет существующий,
        # а не падает на уникальном ограничении.
        user = validated_data.pop("user")
        job = validated_data.pop("job")
        existing = Application.objects.filter(user=user, job=job).first()
        if existing is not None:
            return self.update(existing, validated_data)
        return Application.objects.create(user=user, job=job, **validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("job", None)
        return super().update(instance, validated_data)
