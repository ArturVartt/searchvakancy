import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("searchvakancy")

# Все настройки CELERY_* читаются из Django settings (namespace="CELERY").
app.config_from_object("django.conf:settings", namespace="CELERY")

# Автоматически подхватывать tasks.py из каждого приложения в INSTALLED_APPS.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
