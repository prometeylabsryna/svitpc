import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.develop")

app = Celery("svitpc")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
