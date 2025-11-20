# webhooks/tasks.py
import time
import requests

from celery import shared_task
from django.utils import timezone

from .models import Webhook


@shared_task(bind=True)
def dispatch_webhooks_for_event(self, event_type: str, payload: dict):
    """
    Send the given payload to all enabled webhooks for this event type.

    Runs in the background so it doesn't block requests or other workers.
    """
    webhooks = Webhook.objects.filter(event_type=event_type, is_enabled=True)

    for webhook in webhooks:
        try:
            start = time.monotonic()
            resp = requests.post(
                webhook.target_url,
                json=payload,
                timeout=5,  # seconds
            )
            elapsed_ms = (time.monotonic() - start) * 1000.0

            # Reuse mark_result so the UI shows latest result
            webhook.mark_result(
                status_code=resp.status_code,
                elapsed_ms=elapsed_ms,
                error=None,
            )

        except requests.RequestException as e:
            elapsed_ms = (time.monotonic() - start) * 1000.0
            webhook.mark_result(
                status_code=None,
                elapsed_ms=elapsed_ms,
                error=str(e),
            )
