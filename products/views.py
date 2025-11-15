from rest_framework import viewsets, filters
from .models import Product
from .serializers import ProductSerializer



class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all().order_by("-created_at")
    serializer_class = ProductSerializer

    search_fields = ["sku", "name"]


    def get_queryset(self):
        queryset = Product.objects.all().order_by("-created_at")[:5]

        # filter by "active" query param
        active = self.request.query_params.get("active")
        if active is not None:
            queryset = queryset.filter(active=(active.lower() == "true"))

        return queryset