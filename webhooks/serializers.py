from rest_framework import serializers
from .models import Webhook

class WebhookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Webhook
        fields = [
            "id",
            "target_url",
            "event_type",
            "active",
            "created_at",
            "updated_at",
        ]
