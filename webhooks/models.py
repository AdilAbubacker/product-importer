from django.db import models

class Webhook(models.Model):
    EVENT_CHOICES = [
        ("product.updated", "Product Updated"),
    ]

    target_url = models.URLField()
    event_type = models.CharField(max_length=50, choices=EVENT_CHOICES)
    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.event_type} -> {self.target_url}"
