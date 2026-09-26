from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from apps.applications.models import Application

from .filters import JobFilterSet, NullsLastOrderingFilter
from .models import FavoriteJob, Job, JobNotification, JobSource, UserJobFilter
from .serializers import (
    JobDetailSerializer,
    JobListSerializer,
    JobNotificationSerializer,
    JobSourceSerializer,
    UserJobFilterSerializer,
)


class JobSourceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Только активные источники — этот список фронтенд использует для
    чекбоксов фильтра "Источник" (см. JobFilters.tsx), показывать там
    источник, который никогда не даёт вакансий (например, нереализованный
    VK Jobs — см. README), было бы просто шумом. Полная сводка по всем
    источникам, включая неактивные, — отдельно в /api/jobs/stats/.
    """

    queryset = JobSource.objects.filter(is_active=True)
    serializer_class = JobSourceSerializer


class JobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Список/деталь вакансий + служебные эндпоинты:
      GET  /api/jobs/stats/       — статистика (публично)
      GET  /api/jobs/favorites/   — избранное текущего пользователя
      POST/DELETE /api/jobs/<id>/favorite/ — добавить/убрать из избранного

    Фильтры: см. apps/jobs/filters.py:JobFilterSet.
    Поиск: ?search=react — по title/company/description (django SearchFilter).
    Сортировка: ?ordering=-salary_from,posted_at и т.д.
    """

    queryset = Job.objects.filter(is_active=True).select_related("source")
    filter_backends = [DjangoFilterBackend, SearchFilter, NullsLastOrderingFilter]
    filterset_class = JobFilterSet
    search_fields = ["title", "company", "description"]
    ordering_fields = ["posted_at", "created_at", "salary_from", "salary_to"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return JobDetailSerializer
        return JobListSerializer

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

    @action(detail=True, methods=["post", "delete"], permission_classes=[permissions.IsAuthenticated])
    def favorite(self, request, pk=None):
        job = self.get_object()
        if request.method == "POST":
            _, created = FavoriteJob.objects.get_or_create(user=request.user, job=job)
            return Response(
                {"status": "added" if created else "already_favorited"},
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )
        deleted, _ = FavoriteJob.objects.filter(user=request.user, job=job).delete()
        return Response(status=status.HTTP_204_NO_CONTENT if deleted else status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def favorites(self, request):
        job_ids = FavoriteJob.objects.filter(user=request.user).values_list("job_id", flat=True)
        queryset = self.filter_queryset(self.get_queryset().filter(id__in=job_ids))
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def stats(self, request):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())

        active = Job.objects.filter(is_active=True)
        by_source = list(
            active.values("source__name").annotate(count=Count("id")).order_by("-count")
        )
        by_experience = list(
            active.exclude(experience_level="")
            .values("experience_level")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return Response(
            {
                "total_active": active.count(),
                "new_today": active.filter(created_at__gte=today_start).count(),
                "new_this_week": active.filter(created_at__gte=week_start).count(),
                "by_source": [
                    {"source": row["source__name"], "count": row["count"]} for row in by_source
                ],
                "by_experience_level": [
                    {"experience_level": row["experience_level"], "count": row["count"]}
                    for row in by_experience
                ],
                "sources": list(
                    JobSource.objects.values("name", "is_active", "last_sync")
                ),
            }
        )


class UserJobFilterViewSet(viewsets.ModelViewSet):
    """
    GET/POST /api/jobs/filters/, GET/PUT/PATCH/DELETE /api/jobs/filters/<id>/
    — CRUD над фильтрами текущего пользователя (нужны и для API-поиска,
    и как основа для подбора уведомлений в Telegram-боте).
    """

    serializer_class = UserJobFilterSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserJobFilter.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class JobNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/jobs/notifications/ + POST /api/jobs/notifications/<id>/mark_read/."""

    serializer_class = JobNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return JobNotification.objects.filter(user=self.request.user).select_related(
            "job", "job__source"
        )

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        return Response(self.get_serializer(notification).data)
