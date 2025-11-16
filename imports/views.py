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

from django.shortcuts import render


def upload_page(request):
    return render(request, "upload.html")

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
        
        # IMPORTANT: Check 'is not None' explicitly, because 0 is falsy!
        # If redis_processed is 0, we still want to use it, not fallback to DB
        redis_processed = cache.get(redis_key)
        
        # Debug: Log what we're getting from Redis
        print(f"[ImportStatusView] Redis key: {redis_key}, value: {redis_processed}, DB value: {job.processed_rows}")
        
        if redis_processed is not None:
            # Redis has data (even if it's 0) - use it for real-time updates
            processed_rows = int(redis_processed)
            progress_source = "redis"
            print(f"[ImportStatusView] Using Redis: {processed_rows}")
        else:
            # Redis doesn't have data yet, use DB (only updated every 50k rows)
            processed_rows = job.processed_rows
            progress_source = "db"
            print(f"[ImportStatusView] Redis not available, using DB: {processed_rows}")

        data = {
            "job_id": job_id,
            "status": job.status,
            "processed_rows": processed_rows,
            "total_rows": job.total_rows,
            "error_message": job.error_message,
            "progress_source": progress_source,  # Debug: shows if using redis or db
        }

        return Response(data)
