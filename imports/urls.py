# imports/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("products/upload/", views.upload_products_page, name="upload_products_page"),

    path("api/imports/create-upload/", views.create_upload_job, name="create_upload_job"),
    path("api/imports/<int:job_id>/start/", views.start_import_job, name="start_import_job"),
    path("api/imports/<int:job_id>/status/", views.import_job_status, name="import_job_status"),
]
