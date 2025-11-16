
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
