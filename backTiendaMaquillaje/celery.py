import os
from celery import Celery

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "backTiendaMaquillaje.settings"
)

app = Celery("backTiendaMaquillaje")

# Lee configuración desde Django settings con prefijo CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

# Autodiscover tasks en todas las apps instaladas
app.autodiscover_tasks()