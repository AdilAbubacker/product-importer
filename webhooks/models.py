# webhooks/models.py
from django.db import models
from django.utils import timezone


class Webhook(models.Model):
    EVENT_IMPORT_COMPLETED = "import.completed"
    EVENT_PRODUCT_CREATED = "product.created"
    EVENT_PRODUCT_UPDATED = "product.updated"

    EVENT_CHOICES = [
        (EVENT_IMPORT_COMPLETED, "Import completed"),
        (EVENT_PRODUCT_CREATED, "Product created"),
        (EVENT_PRODUCT_UPDATED, "Product updated"),
    ]

    name = models.CharField(max_length=100)
    target_url = models.URLField()
    event_type = models.CharField(max_length=64, choices=EVENT_CHOICES)
    is_enabled = models.BooleanField(default=True)

    # Last test / last delivery info (for UI)
    last_status_code = models.IntegerField(null=True, blank=True)
    last_response_ms = models.FloatField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def mark_result(self, status_code: int | None, elapsed_ms: float | None, error: str | None = ""):
        self.last_status_code = status_code
        self.last_response_ms = elapsed_ms
        self.last_error = error or ""
        self.last_triggered_at = timezone.now()
        self.save(update_fields=["last_status_code", "last_response_ms", "last_error", "last_triggered_at", "updated_at"])

    def __str__(self):
        return f"{self.name} ({self.event_type})"
