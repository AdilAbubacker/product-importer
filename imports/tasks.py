from celery import shared_task
from .models import ImportJob

@shared_task
def process_csv_import(job_id, file_path):
    job = ImportJob.objects.get(id=job_id)

    # Mark as running
    job.status = "running"
    job.save()

    # TODO: real CSV processing will go here
    print("Received job:", job_id, file_path)

    # For now, simulate work
    import time
    time.sleep(3)

    # Mark as completed
    job.status = "completed"
    job.save()

    return True
