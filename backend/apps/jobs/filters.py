import django_filters
from django.db.models import Value
from django.db.models.functions import Coalesce

from .models import Job


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
