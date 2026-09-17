from rest_framework.routers import DefaultRouter

from .views import JobNotificationViewSet, JobSourceViewSet, JobViewSet, UserJobFilterViewSet

router = DefaultRouter()
# "sources"/"filters"/"notifications" ДО пустого префикса JobViewSet ("") —
# иначе DRF-роутер по умолчанию перехватит их как <pk> из-за общего regex.
router.register("sources", JobSourceViewSet, basename="job-source")
router.register("filters", UserJobFilterViewSet, basename="job-filter")
router.register("notifications", JobNotificationViewSet, basename="job-notification")
router.register("", JobViewSet, basename="job")

urlpatterns = router.urls
