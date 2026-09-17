from .base import env  # noqa: F401
from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE

DEBUG = False

# В базовых настройках SECRET_KEY по умолчанию — заведомо небезопасный
# dev-ключ; в проде лучше упасть на старте, чем тихо на нём заработать.
SECRET_KEY = env("DJANGO_SECRET_KEY")

# WhiteNoise раздаёт STATIC_ROOT (см. STORAGES ниже) — без этого
# middleware collectstatic создаст файлы, но отдавать их будет нечему
# (Django сам статику в DEBUG=False не сервит, а /static/ у нас
# проксируется nginx'ом фронтенда прямо на backend).
MIDDLEWARE = [MIDDLEWARE[0], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[1:]]

SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
# TLS обрывается на nginx (frontend-контейнер), к Django запросы приходят
# обычным HTTP — без этой строки Django считает вообще каждый запрос
# небезопасным и вместе с SECURE_SSL_REDIRECT=True зацикливает редирект
# https -> https в бесконечный луп.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Django 4+ проверяет Origin для CSRF на HTTPS-запросах (важно для формы
# логина в /admin/) — без явного списка POST в админку будет падать 403.
CSRF_TRUSTED_ORIGINS = [
    f"https://{host}" for host in ALLOWED_HOSTS if host not in ("localhost", "127.0.0.1")
]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
