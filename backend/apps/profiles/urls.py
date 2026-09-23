from rest_framework.routers import DefaultRouter

from .views import ProfileSetViewSet

router = DefaultRouter()
router.register("", ProfileSetViewSet, basename="profile-set")

urlpatterns = router.urls
