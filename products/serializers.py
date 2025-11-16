from rest_framework import serializers
from .models import Product

class ProductSerializer(serializers.ModelSerializer):

    def validate_sku(self, value):
        return value.lower()

    class Meta:
        model = Product
        fields = [
            "id",
            "sku",
            "name",
            "description",
            "active",
            "created_at",
            "updated_at",
        ]
