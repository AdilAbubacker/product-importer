# products/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("products/", views.product_list, name="product_list"),
    path("products/create/", views.product_create, name="product_create"),

    # change int -> uuid here:
    path("products/<uuid:pk>/update/", views.product_update, name="product_update"),
    path("products/<uuid:pk>/delete/", views.product_delete, name="product_delete"),

    path("products/bulk-delete/", views.product_bulk_delete, name="product_bulk_delete"),
]
