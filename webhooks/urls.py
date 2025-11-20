# webhooks/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("webhooks/", views.webhook_list, name="webhook_list"),
    path("webhooks/create/", views.webhook_create, name="webhook_create"),
    path("webhooks/<int:pk>/update/", views.webhook_update, name="webhook_update"),
    path("webhooks/<int:pk>/delete/", views.webhook_delete, name="webhook_delete"),
    path("webhooks/<int:pk>/toggle/", views.webhook_toggle_enabled, name="webhook_toggle_enabled"),
    path("webhooks/<int:pk>/test/", views.webhook_test, name="webhook_test"),
]
