from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import WebhookViewSet, WebhookTestView, webhooks_page

router = DefaultRouter()
router.register(r"webhooks", WebhookViewSet, basename="webhooks")

urlpatterns = [
    path("webhooks-ui/", webhooks_page),
    path("webhooks/<int:pk>/test/", WebhookTestView.as_view()),
]

urlpatterns += router.urls
