from rest_framework import permissions, viewsets

from apps.jobs.models import FavoriteJob

from .models import Application
from .serializers import ApplicationSerializer


class ApplicationViewSet(viewsets.ModelViewSet):
    """
    GET/POST /api/applications/, GET/PATCH/DELETE /api/applications/<id>/
    — трекер откликов текущего пользователя.
    Фильтры: ?status=applied, ?job=<id>. Без пагинации — список личный
    и ограниченный, а фронтенду нужен целиком для группировки по статусам.
    """

    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        queryset = (
            Application.objects.filter(user=self.request.user)
            .select_related("job", "job__source", "profile_set")
        )
        status = self.request.query_params.get("status")
        if status:
            queryset = queryset.filter(status=status)
        job = self.request.query_params.get("job")
        if job and job.isdigit():
            queryset = queryset.filter(job_id=int(job))
        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        request = self.request
        if request is not None and request.user.is_authenticated:
            context["favorite_job_ids"] = set(
                FavoriteJob.objects.filter(user=request.user).values_list("job_id", flat=True)
            )
            context["application_statuses"] = dict(
                Application.objects.filter(user=request.user).values_list("job_id", "status")
            )
        return context

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
