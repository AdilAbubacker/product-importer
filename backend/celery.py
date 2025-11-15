import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

app = Celery("backend")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Discover tasks from all installed Django apps
app.autodiscover_tasks()

# Ensure tasks are registered - print registered tasks for debugging
@app.on_after_configure.connect
def on_after_configure(sender, **kwargs):
    print(f"[Celery] App configured. Registered tasks: {list(sender.tasks.keys())}")