from django.shortcuts import render
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt

from imports.models import ImportJob
from imports.tasks import process_import_job
from backend.r2 import generate_presigned_put_url  # adjust path if needed

from datetime import timedelta
from django.utils import timezone
from django.http import JsonResponse, Http404


STALE_MINUTES = 1

def upload_products_page(request):
    """
    Render the Products CSV upload page.
    """
    return render(request, "imports/upload_products.html", {
        "current_section": "upload",   
    })


@require_POST
def create_upload_job(request):
    job = ImportJob.objects.create(
        status=ImportJob.STATUS_PENDING,
        processed_rows=0,
    )

    object_key = f"imports/{job.id}.csv"
    upload_url = generate_presigned_put_url(
        object_key=object_key,
        content_type="text/csv",
        expires_in=600,
    )

    job.file_key = object_key
    job.save(update_fields=["file_key"])

    return JsonResponse(
        {
            "job_id": job.id,
            "upload_url": upload_url,
        }
    )


@require_POST
def start_import_job(request, job_id: int):
    try:
        job = ImportJob.objects.get(pk=job_id)
    except ImportJob.DoesNotExist:
        raise Http404("Job not found")

    if job.status not in [ImportJob.STATUS_PENDING, ImportJob.STATUS_FAILED]:
        return JsonResponse(
            {"error": f"Job in status {job.status}, cannot start"},
            status=400,
        )

    job.status = ImportJob.STATUS_QUEUED
    job.error_message = ""
    job.save(update_fields=["status", "error_message", "updated_at"])

    process_import_job.delay(job.id)

    return JsonResponse({"job_id": job.id, "status": job.status})






@require_GET
def import_job_status(request, job_id: int):
    try:
        job = ImportJob.objects.get(pk=job_id)
    except ImportJob.DoesNotExist:
        raise Http404("Job not found")

    # If a job is "in progress" but hasn't updated for a long time,
    # assume worker crashed / stalled and mark as failed.
    if job.status in [
        ImportJob.STATUS_QUEUED,
        ImportJob.STATUS_PARSING,
        ImportJob.STATUS_IMPORTING,
    ]:
        cutoff = timezone.now() - timedelta(minutes=STALE_MINUTES)
        if job.updated_at < cutoff:
            job.status = ImportJob.STATUS_FAILED
            if not job.error_message:
                job.error_message = (
                    "Import stalled (worker may have crashed or timed out). "
                    "You can retry the import."
                )
            job.save(update_fields=["status", "error_message", "updated_at"])

    data = {
        "job_id": job.id,
        "status": job.status,
        "processed_rows": job.processed_rows,
        "total_rows": job.total_rows,
        "percentage": job.progress_percent(),
        "error_message": job.error_message,
        "created": getattr(job, "created_count", None),
        "updated": getattr(job, "updated_count", None),     
    }
    return JsonResponse(data)



