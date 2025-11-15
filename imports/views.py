from django.shortcuts import render
# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import ImportCSVSerializer
from .models import ImportJob
from .tasks import process_csv_import 
import os

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from .models import ImportJob

class ImportCSVView(APIView):
    def post(self, request):
        serializer = ImportCSVSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data["file"]

        # Save the file to disk
        file_path = f"uploads/{uploaded_file.name}"
        with open(file_path, "wb+") as dest:
            for chunk in uploaded_file.chunks():
                dest.write(chunk)

        print("Saving to:", file_path)
        print("Absolute path:", os.path.abspath(file_path))
        print("File exists:", os.path.exists(file_path))

        # Create ImportJob entry
        job = ImportJob.objects.create(
            file_name=uploaded_file.name,
            status="pending",
        )

        # Trigger Celery

        process_csv_import.delay(job.id, file_path)

        return Response({"job_id": job.id}, status=status.HTTP_202_ACCEPTED)





class ImportStatusView(APIView):
    def get(self, request, job_id):
        try:
            job = ImportJob.objects.get(id=job_id)
        except ImportJob.DoesNotExist:
            return Response(
                {"error": "Invalid job_id"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Redis key for progress
        redis_key = f"import:{job_id}:processed"
        redis_processed = cache.get(redis_key)

        processed_rows = redis_processed or job.processed_rows

        data = {
            "job_id": job_id,
            "status": job.status,
            "processed_rows": processed_rows,
            "total_rows": job.total_rows,
            "error_message": job.error_message,
        }

        return Response(data)
