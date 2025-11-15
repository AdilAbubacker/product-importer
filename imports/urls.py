
from django.urls import path
from .views import ImportStatusView, ImportCSVView

urlpatterns = [
    path("import-csv/", ImportCSVView.as_view()),
    path("import-status/<int:job_id>/", ImportStatusView.as_view()),
]
