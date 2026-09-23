from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/jobs/", include("apps.jobs.urls")),
    path("api/profile-sets/", include("apps.profiles.urls")),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/auth/token/", obtain_auth_token, name="api-token-auth"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

# В отличие от статики (whitenoise, работает независимо от DEBUG), media
# (загруженные пользователем резюме, см. apps/profiles) раньше отдавались
# только при DEBUG=True — на проде (DEBUG=False) nginx честно проксировал
# /media/ на backend (см. frontend/nginx.conf.template), но Django там не
# регистрировал для них ни один URL, и любой /media/... отдавал 404.
# django.views.static.serve не рассчитан на большую нагрузку — но для
# личного проекта с горсткой файлов резюме этого достаточно, отдельный
# сервер раздачи (S3/nginx x-accel и т.п.) сейчас избыточен.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
