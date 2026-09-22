import django_filters
from django.db.models import F, Value
from django.db.models.functions import Coalesce
from rest_framework.filters import OrderingFilter

from .models import Job


class NullsLastOrderingFilter(OrderingFilter):
    """
    Обычный OrderingFilter передаёт в order_by() голые строки поля, а
    Postgres по умолчанию сортирует NULL как "больше любого значения" при
    DESC — вакансии без posted_at (источники, не отдающие дату публикации,
    например Zarplata.ru) оказывались бы выше реально свежих вакансий.
    Подменяем "-posted_at"/"posted_at" на F-выражение с явным nulls_last —
    то же самое, что уже сделано в Job.Meta.ordering по умолчанию, только
    здесь это применяется и к сортировке, явно запрошенной через ?ordering=.
    """

    NULLABLE_FIELDS = {"posted_at"}

    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)
        if not ordering:
            return ordering
        return [self._to_expression(field) for field in ordering]

    def _to_expression(self, field: str):
        name = field[1:] if field.startswith("-") else field
        if name not in self.NULLABLE_FIELDS:
            return field
        return F(name).desc(nulls_last=True) if field.startswith("-") else F(name).asc(nulls_last=True)


class JobFilterSet(django_filters.FilterSet):
    """
    ?min_salary=150000&max_salary=300000&location=Москва
    &experience_level=junior,middle&job_type=full_time&source=1

    Семантика min/max_salary специально зеркалит UserJobFilter.matches(),
    чтобы результаты API и уведомления в Telegram по одному и тому же
    фильтру не расходились.
    """

    min_salary = django_filters.NumberFilter(method="filter_min_salary")
    max_salary = django_filters.NumberFilter(method="filter_max_salary")
    location = django_filters.CharFilter(field_name="location", lookup_expr="icontains")
    experience_level = django_filters.MultipleChoiceFilter(choices=Job.ExperienceLevel.choices)
    job_type = django_filters.MultipleChoiceFilter(choices=Job.JobType.choices)
    employment_type = django_filters.MultipleChoiceFilter(choices=Job.EmploymentType.choices)
    posted_after = django_filters.DateFilter(field_name="posted_at", lookup_expr="gte")

    class Meta:
        model = Job
        fields = ["source", "experience_level", "job_type", "employment_type", "location"]

    def filter_min_salary(self, queryset, name, value):
        return queryset.annotate(
            _effective_salary=Coalesce("salary_to", "salary_from", Value(0))
        ).filter(_effective_salary__gte=value)

    def filter_max_salary(self, queryset, name, value):
        return queryset.annotate(
            _effective_salary_cap=Coalesce("salary_from", "salary_to", Value(0))
        ).filter(_effective_salary_cap__lte=value)
