from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as serve_static
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
#
# ВАЖНО: обычный django.conf.urls.static.static() тут не подходит — он
# САМ внутри себя делает `if not settings.DEBUG: return []`, так что
# оборачивание его в свой `if settings.DEBUG:` или без него ничего не
# меняет на проде (DEBUG=False) — маршрут всё равно не регистрируется.
# Поймано вживую на проде: после "снятия" внешнего if 400 сменился на 404,
# то есть сам static() по-прежнему возвращал []. Обходим её встроенную
# DEBUG-проверку, вызывая django.views.static.serve явным re_path.
#
# django.views.static.serve не рассчитан на большую нагрузку — но для
# личного проекта с горсткой файлов резюме этого достаточно, отдельный
# сервер раздачи (S3/nginx x-accel и т.п.) сейчас избыточен.
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve_static, {"document_root": settings.MEDIA_ROOT}),
]
