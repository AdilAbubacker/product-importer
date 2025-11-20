
# Create your views here.
from rest_framework import viewsets
from .models import Webhook
from .serializers import WebhookSerializer
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
import requests

def webhooks_page(request):
    return render(request, "webhooks.html")


class WebhookViewSet(viewsets.ModelViewSet):
    queryset = Webhook.objects.all().order_by("-created_at")
    serializer_class = WebhookSerializer


class WebhookTestView(APIView):
    def post(self, request, pk):
        webhook = Webhook.objects.get(id=pk)

        test_payload = {
            "event_type": webhook.event_type,
            "test": True,
            "message": "Webhook test successful."
        }

        try:
            r = requests.post(webhook.target_url, json=test_payload, timeout=5)
            return Response({"status": "success", "response_code": r.status_code})
        except Exception as e:
            return Response({"status": "failed", "error": str(e)}, status=400)


# webhooks/views.py
import time
import requests

from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods, require_POST

from .models import Webhook

from .models import Webhook

# webhooks/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from .models import Webhook

@require_http_methods(["GET"])
def webhook_list(request):
    webhooks = Webhook.objects.all().order_by("id")
    return render(
        request,
        "webhooks/webhook_list.html",
        {
            "webhooks": webhooks,
            "current_section": "webhooks", 
        },
    )



@require_POST
def webhook_create(request):
    name = (request.POST.get("name") or "").strip()
    target_url = (request.POST.get("target_url") or "").strip()
    event_type = (request.POST.get("event_type") or "").strip()
    is_enabled = request.POST.get("is_enabled") == "on"

    if not name or not target_url or not event_type:
        messages.error(request, "Name, URL, and event type are required.")
        return redirect("webhook_list")

    webhook = Webhook(
        name=name,
        target_url=target_url,
        event_type=event_type,
        is_enabled=is_enabled,
    )
    try:
        webhook.save()
        messages.success(request, f"Webhook '{webhook.name}' created.")
    except Exception as e:
        messages.error(request, f"Failed to create webhook: {e}")

    return redirect("webhook_list")


@require_POST
def webhook_update(request, pk: int):
    webhook = get_object_or_404(Webhook, pk=pk)

    name = (request.POST.get("name") or "").strip()
    target_url = (request.POST.get("target_url") or "").strip()
    event_type = (request.POST.get("event_type") or "").strip()
    is_enabled = request.POST.get("is_enabled") == "on"

    if not name or not target_url or not event_type:
        messages.error(request, "Name, URL, and event type are required.")
        return redirect("webhook_list")

    webhook.name = name
    webhook.target_url = target_url
    webhook.event_type = event_type
    webhook.is_enabled = is_enabled

    try:
        webhook.save()
        messages.success(request, f"Webhook '{webhook.name}' updated.")
    except Exception as e:
        messages.error(request, f"Failed to update webhook: {e}")

    return redirect("webhook_list")


@require_POST
def webhook_delete(request, pk: int):
    webhook = get_object_or_404(Webhook, pk=pk)
    name = webhook.name
    webhook.delete()
    messages.success(request, f"Webhook '{name}' deleted.")
    return redirect("webhook_list")


@require_POST
def webhook_toggle_enabled(request, pk: int):
    """
    Simple enable/disable toggle.
    """
    webhook = get_object_or_404(Webhook, pk=pk)
    webhook.is_enabled = not webhook.is_enabled
    webhook.save(update_fields=["is_enabled", "updated_at"])

    state = "enabled" if webhook.is_enabled else "disabled"
    messages.success(request, f"Webhook '{webhook.name}' {state}.")
    return redirect("webhook_list")


@require_POST
def webhook_test(request, pk: int):
    """
    Manually trigger a test call to a webhook and record
    response code + response time.
    """
    webhook = get_object_or_404(Webhook, pk=pk)

    if not webhook.is_enabled:
        messages.error(request, f"Webhook '{webhook.name}' is disabled; enable it before testing.")
        return redirect("webhook_list")

    payload = {
        "type": "test",
        "event": webhook.event_type,
        "webhook_id": webhook.pk,
        "message": "Test webhook from product-importer",
    }

    try:
        start = time.monotonic()
        resp = requests.post(
            webhook.target_url,
            json=payload,
            timeout=5,  # seconds
        )
        elapsed_ms = (time.monotonic() - start) * 1000.0

        webhook.mark_result(status_code=resp.status_code, elapsed_ms=elapsed_ms, error=None)

        messages.success(
            request,
            f"Test sent to '{webhook.name}': {resp.status_code} ({elapsed_ms:.1f} ms)",
        )
    except requests.RequestException as e:
        elapsed_ms = (time.monotonic() - start) * 1000.0
        webhook.mark_result(status_code=None, elapsed_ms=elapsed_ms, error=str(e))

        messages.error(
            request,
            f"Test to '{webhook.name}' failed: {e}",
        )

    return redirect("webhook_list")
