# imports/tasks.py
import csv
import logging
from typing import List, Dict
from django.utils import timezone
from webhooks.tasks import dispatch_webhooks_for_event

import requests
from celery import shared_task
from django.db import connection

from imports.models import ImportJob
from products.models import Product
from backend.r2 import generate_presigned_get_url  # or wherever your R2 helper lives

logger = logging.getLogger(__name__)

from webhooks.tasks import dispatch_webhooks_for_event

from typing import List, Dict
from products.models import Product


def upsert_products_batch(rows: List[Dict]):
    """
    Bulk upsert using Django's bulk_create with update_conflicts.
    """
    if not rows:
        return

    products = [
        Product(
            sku=row["sku"],
            sku_norm=row["sku_norm"],        # computed in the task
            name=row["name"],
            description=row.get("description") or "",
            active=row.get("active", True),
        )
        for row in rows
    ]

    # Django 4.1+ feature
    Product.objects.bulk_create(
        products,
        batch_size=1000,
        update_conflicts=True,
        unique_fields=["sku_norm"],         # enforce case-insensitive uniqueness
        update_fields=["sku", "name", "description", "active"],
    )


@shared_task(bind=True)
def process_import_job(self, job_id: int):
    logger.info("Starting import job %s", job_id)
    job = ImportJob.objects.get(pk=job_id)

    try:
        if not job.file_key:
            raise ValueError("ImportJob has no file_key set")

        # 1) First pass: count total rows
        job.status = ImportJob.STATUS_PARSING
        job.save(update_fields=["status", "updated_at"])

        get_url = generate_presigned_get_url(job.file_key, expires_in=3600)
        resp = requests.get(get_url, stream=True)
        resp.raise_for_status()

        total = -1  # header + data rows
        for _ in resp.iter_lines():
            total += 1
        job.total_rows = max(total, 0)
        job.save(update_fields=["total_rows", "updated_at"])

        # 2) Second pass: actual import
        job.status = ImportJob.STATUS_IMPORTING
        job.processed_rows = 0
        job.save(update_fields=["status", "processed_rows", "updated_at"])

        resp = requests.get(get_url, stream=True)
        resp.raise_for_status()

        # CSV header: sku,name,description
        def line_iter():
            for line in resp.iter_lines():
                if line:
                    yield line.decode("utf-8")

        reader = csv.DictReader(line_iter())

        BATCH_SIZE = 1000
        batch: List[Dict] = []
        processed = 0

        for row in reader:
            sku_raw = (row.get("sku") or "").strip()
            if not sku_raw:
                continue

            product_data = {
                "sku": sku_raw,
                "sku_norm": sku_raw.lower(),
                "name": (row.get("name") or "").strip(),
                "description": (row.get("description") or "").strip(),
                "active": True,  # default ON; user can toggle later
            }

            batch.append(product_data)

            if len(batch) >= BATCH_SIZE:
                upsert_products_batch(batch)
                processed += len(batch)
                batch.clear()

                job.processed_rows = processed
                job.save(update_fields=["processed_rows", "updated_at"])
                logger.info("Job %s: processed %d rows", job_id, processed)

        if batch:
            upsert_products_batch(batch)
            processed += len(batch)
            job.processed_rows = processed
            job.save(update_fields=["processed_rows", "updated_at"])

        job.status = ImportJob.STATUS_COMPLETED
        job.save(update_fields=["status", "processed_rows", "updated_at"])
        logger.info("Job %s completed: %d rows", job_id, processed)

        # 🔔 Fire import.completed webhooks asynchronously
        dispatch_webhooks_for_event.delay(
            "import.completed",
            {
                "type": "import.completed",
                "job_id": job.id,
                "file_key": job.file_key,
                "total_rows": job.total_rows,
                "processed_rows": job.processed_rows,
                "status": job.status,
                "timestamp": timezone.now().isoformat(),
            },
        )

    except Exception as e:
        logger.exception("Import job %s failed", job_id)
        job.status = ImportJob.STATUS_FAILED
        job.error_message = str(e)
        job.save(update_fields=["status", "error_message", "updated_at"])
        raise
