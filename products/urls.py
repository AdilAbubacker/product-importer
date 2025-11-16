
from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, product_list_page, product_form_page, ProductBulkDeleteView

router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="products")

urlpatterns = [
    path("products-ui/", product_list_page),
    path("product-form/", product_form_page),
    path("products/bulk-delete/", ProductBulkDeleteView.as_view()),
]

urlpatterns += router.urls
