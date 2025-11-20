from django.db import models

import uuid
from django.db import models


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # original SKU as user-facing
    sku = models.CharField(max_length=64)
    # normalized SKU (lowercase, trimmed) used for uniqueness
    sku_norm = models.CharField(max_length=64, unique=True, editable=False)

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.sku_norm = self.sku.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sku} - {self.name}"

