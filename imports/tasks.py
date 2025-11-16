from celery import shared_task
from .models import ImportJob
from products.models import Product
import csv
import os
from django.core.cache import cache

CHUNK_SIZE = 10000  # optimized chunk size


def _process_chunk(rows):
    """
    Process a chunk of CSV rows:
    - Normalize SKUs
    - Dedupe inside chunk
    - Bulk update or create products
    """

    # 1. Normalize & dedupe inside the chunk
    normalized = {}  # sku -> last row
    for r in rows:
        sku = r["sku"].lower()
        normalized[sku] = r

    skus = list(normalized.keys())

    # 2. Fetch existing products from DB
    existing_products = Product.objects.filter(sku__in=skus)
    existing_map = {p.sku: p for p in existing_products}

    to_update = []
    to_create = []

    # 3. Classify rows
    for sku, r in normalized.items():
        if sku in existing_map:
            product = existing_map[sku]
            product.name = r.get("name", product.name)
            product.description = r.get("description", product.description)
            to_update.append(product)
        else:
            to_create.append(
                Product(
                    sku=sku,
                    name=r.get("name", ""),
                    description=r.get("description", "")
                )
            )

    # 4. Bulk operations
    if to_update:
        Product.objects.bulk_update(to_update, ["name", "description"])

    if to_create:
        Product.objects.bulk_create(to_create)


@shared_task(name="imports.tasks.process_csv_import")
def process_csv_import(job_id, file_path):
    print(f"[Celery] Starting job {job_id}")
    print(f"[Celery] File path: {file_path}")
    print(f"[Celery] File exists: {os.path.exists(file_path)}")

    job = ImportJob.objects.get(id=job_id)

    try:
        job.status = "running"
        job.save(update_fields=["status"])
        
        # Cache initial job data in Redis
        cache.set(f"import:{job_id}:status", "running", timeout=None)

        # STEP 1 — Count total rows
        with open(file_path, newline="", encoding="utf-8") as f:
            total_rows = sum(1 for _ in f) - 1  # minus header
        job.total_rows = max(total_rows, 0)
        job.save(update_fields=["total_rows"])
        
        # Cache total_rows in Redis
        cache.set(f"import:{job_id}:total_rows", job.total_rows, timeout=None)

        print(f"[Celery] Total rows: {total_rows}")

        # STEP 2 — Process CSV in chunks
        processed = 0
        chunk_index = 0

        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            buffer = []

            for row in reader:
                buffer.append(row)

                if len(buffer) == CHUNK_SIZE:
                    print(f"[Celery] Processing chunk {chunk_index}...")
                    _process_chunk(buffer)

                    processed += len(buffer)
                    buffer = []
                    chunk_index += 1

                    # Update Redis every chunk with progress data (timeout=None means never expire)
                    redis_key = f"import:{job_id}:processed"
                    print(f"[Celery] Updated cache progress: {processed} (key: {redis_key})")
                    cache.set(redis_key, processed, timeout=None)
                    # Verify it was set
                    verify = cache.get(redis_key)
                    if verify != processed:
                        print(f"[Celery] WARNING: Cache verification failed! Set {processed}, got {verify}")

                    # Update DB only every 5 chunks
                    if chunk_index % 5 == 0:
                        job.processed_rows = processed
                        job.save(update_fields=["processed_rows"])
                        print(f"[Celery] Updated DB progress: {processed}")

            # Process any remaining rows
            if buffer:
                print(f"[Celery] Processing final chunk...")
                _process_chunk(buffer)
                processed += len(buffer)
                chunk_index += 1
                cache.set(f"import:{job_id}:processed", processed, timeout=None)

        # Final DB update
        job.processed_rows = processed
        job.status = "completed"
        job.save(update_fields=["processed_rows", "status"])
        
        # Final cache update (keep for 1 hour after completion for status polling)
        cache.set(f"import:{job_id}:processed", processed, timeout=3600)
        cache.set(f"import:{job_id}:status", "completed", timeout=3600)
        print(f"[Celery] Job {job_id} completed successfully.")

    except Exception as e:
        print(f"[Celery] ERROR in job {job_id}: {e}")

        job.status = "failed"
        job.error_message = str(e)
        job.save(update_fields=["status", "error_message"])
        
        # Cache failure status
        cache.set(f"import:{job_id}:status", "failed", timeout=3600)
        cache.set(f"import:{job_id}:error_message", str(e), timeout=3600)

        raise
