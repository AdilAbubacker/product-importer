from rest_framework import viewsets
from django.db.models import Q
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from .models import Product
from .serializers import ProductSerializer
from rest_framework.views import APIView


def product_list_page(request):
    return render(request, "products.html")


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer

    def get_queryset(self):
        qs = Product.objects.all().order_by("-id")

        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(sku__icontains=search) |
                Q(name__icontains=search)
            )

        active = self.request.query_params.get("active")
        if active is not None and active != "":
            qs = qs.filter(active=(active.lower() == "true"))

        return qs
    
    def create(self, request, *args, **kwargs):
        sku = request.data.get("sku", "").lower()

        # Check if product already exists
        existing = Product.objects.filter(sku=sku).first()

        if existing:
            serializer = self.get_serializer(existing, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()   
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Normal create
        return super().create(request, *args, **kwargs)


def product_form_page(request):
    return render(request, "product_form.html")




class ProductBulkDeleteView(APIView):
    def post(self, request):
        ids = request.data.get("ids", [])
        if not isinstance(ids, list):
            return Response({"error": "ids must be a list"}, status=400)

        deleted_count, _ = Product.objects.filter(id__in=ids).delete()

        return Response({"deleted": deleted_count}, status=200)
