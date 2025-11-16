from celery import shared_task
from .models import Webhook
import requests

@shared_task(bind=True, max_retries=3)
def deliver_webhook(self, event_type, payload):
    """
    Sends webhook payload to all active webhooks listening to this event.
    Runs in background using Celery.
    """
    webhooks = Webhook.objects.filter(event_type=event_type, active=True)

    for hook in webhooks:
        try:
            r = requests.post(hook.target_url, json=payload, timeout=5)

            # (optional) log r.status_code somewhere
        except requests.RequestException as e:
            # Retry after 5 seconds
            try:
                self.retry(countdown=5, exc=e)
            except self.MaxRetriesExceededError:
                pass  # can log permanently failed webhook attempt
                