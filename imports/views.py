from django.shortcuts import render
# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import ImportCSVSerializer
from .models import ImportJob
from .tasks import process_csv_import 

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

        # Create ImportJob entry
        job = ImportJob.objects.create(
            file_name=uploaded_file.name,
            status="pending",
        )

        # Trigger Celery
        process_csv_import.delay(job.id, file_path)

        return Response({"job_id": job.id}, status=status.HTTP_202_ACCEPTED)
