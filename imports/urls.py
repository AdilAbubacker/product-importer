
from django.urls import path
from .views import ImportStatusView, ImportCSVView, upload_page

urlpatterns = [
    path("import-csv/", ImportCSVView.as_view()),
    path("import-status/<int:job_id>/", ImportStatusView.as_view()),

    path("upload-ui/", upload_page),

]
