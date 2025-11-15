from django.urls import path
from .views import ImportCSVView

urlpatterns = [
    path("import-csv/", ImportCSVView.as_view(), name="import-csv"),
]
