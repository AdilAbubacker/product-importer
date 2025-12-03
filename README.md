# 🚀 Scalable Product Ingestion Engine

[![Live Demo](https://img.shields.io/badge/LIVE%20DEMO-Click%20Here-brightgreen?style=for-the-badge)](https://web-production-60e3e.up.railway.app/)  
A production-grade **Django + Celery + PostgreSQL** application designed to handle large-scale data ingestion. This system supports importing **500,000+ products** via CSV without HTTP timeouts, utilizing **Presigned URLs** for direct object storage uploads and **Celery** for asynchronous processing.

    

-----

## 📖 Table of Contents

- [Key Features](#-key-features)
- [Architecture & Design](#-architecture--design)  
    - [The 500k Row Challenge](#the-500k-row-challenge)  
    - [End-to-End Import Flow](#end-to-end-import-flow)  
- [Tech Stack](#-tech-stack)
- [Data Model](#-data-model)
- [Installation & Setup](#-installation--setup)
- [Usage Guide](#-usage-guide)
- [API Overview](#-api-overview)

-----

## 📦 Key Features

### ⚡ High-Performance Ingestion

  - **Zero-Timeout Uploads:** Uses **Presigned URLs** to upload CSVs directly from the browser to Cloudflare R2 (S3-compatible), bypassing the Django application server entirely.
  - **Async Processing:** Heavy parsing and database writes are offloaded to **Celery workers**.
  - **Streaming & Batching:** Workers stream files from storage (low memory footprint) and use bulk upserts (high database throughput).

### 📊 User Experience

  - **Real-Time Progress:** Dedicated polling endpoints provide live feedback for both the upload phase and the server-side processing phase.
  - **Data Integrity:** Enforces case-insensitive SKU uniqueness. Duplicates in the CSV overwrite existing records based on SKU.
  - **Resiliency:** Users can retry failed uploads instantly without server overhead.

### 🛠 Management Tools

  - **Product CRUD:** Full UI to list, filter (SKU, Name, Active status), paginate, and edit products.
  - **Bulk Actions:** "Delete All" functionality with confirmation.
  - **Webhooks System:** UI to register webhooks (e.g., `product.created`), test them, and view latency/response codes.

-----

## 🏗 Architecture & Design

### The 500k Row Challenge

Handling half a million rows in a standard web request is impossible due to:

1.  **HTTP Timeouts:** Browsers and load balancers (Nginx/AWS ALB) usually time out after 30-60 seconds.
2.  **Memory Overhead:** Loading a 500MB CSV into Django's memory crashes the worker.

**The Solution:**
We decouple the **Data Transfer** (Browser to Storage) from the **Data Processing** (Storage to DB).

### End-to-End Import Flow

1.  **Presign:** User clicks "Upload". Backend generates a secure, time-limited **Presigned PUT URL** for Cloudflare R2.
2.  **Direct Upload:** Browser uploads the CSV directly to R2. **No data touches the Django server.**
3.  **Enqueue:** Browser sends the file key to Django. Django creates a `ImportJob` record and queues a Celery task.
4.  **Stream & Upsert:**
      * Celery worker picks up the task.
      * Streams the CSV row-by-row (constant memory usage).
      * Batches records (e.g., 1,000 at a time) and performs `ON CONFLICT` bulk upserts into Postgres.
5.  **Feedback:** Frontend polls the status endpoint to show a progress bar (e.g., "Importing: 45%").

---

## 🔁 Reliability & Failure Handling

Long-running imports are built to be resilient to both transient infrastructure issues and silent failures. The core ideas:

### 1. Retry with Exponential Backoff (Transient Failures)

The Celery import task only retries for transient, likely-to-recover errors (e.g. R2/network issues):

- `max_retries = 5`
- Exponential backoff (1s → 2s → 4s → …) with jitter
- Backoff capped to 5 minutes

This allows short storage/network glitches to resolve without failing a 500k-row import, while avoiding retry storms against R2 or the database.

Permanent errors (e.g. CSV format issues, validation failures, logic bugs) fail fast and are **not** retried, so problems remain visible instead of being hidden behind retries.

### 2. Heartbeat + Stale Job Reconciliation (Silent Failures)

Celery retries only trigger on exceptions, but some failures produce no exception (e.g. worker hang, deadlock, worker down without restart).

To handle these:

- The worker updates `ImportJob.updated_at` regularly as it processes batches (heartbeat).
- A stale checker (or the status endpoint) marks a job as failed if:
  - `status ∈ { queued, parsing, importing }`
  - `updated_at` is older than a configurable `STALE_MINUTES` cutoff.

This prevents “importing forever” states in the UI. Every job eventually reaches a terminal state (`completed`, `partial_success`, or `failed`), and users can safely retry.

### 3. attempt_id Run Token (Prevents Zombie Tasks / Split-Brain)

Each import run is identified by an `attempt_id` stored on the `ImportJob`. The Celery task receives both `job_id` and `attempt_id`, and every state update is guarded:

- Updates are only applied if `(id, attempt_id)` matches the current row in the database and the job is in a running state.
- If the guard fails, the task exits immediately.

This prevents stale or duplicated tasks from mutating job state after:

- A stale checker has marked the job as failed.
- The user has started a new attempt (retry).
- The broker has redelivered a task after worker loss.

Product writes themselves are idempotent upserts on a normalized SKU key, so even if an old task continues briefly, it can only re-apply the same data. Combined with `attempt_id` gating, this avoids split-brain behaviour in both metadata and data paths.

### 4. Crash Recovery: Late ACK + Requeue on Worker Loss

The import task is configured with:

- `acks_late = True` → the broker only marks the message as acknowledged after the task completes.
- `task_reject_on_worker_lost = True` → if a worker dies mid-task, the message is treated as unprocessed and requeued.

If a worker crashes mid-import, Celery can safely redeliver the task to another worker. Because the import logic is chunked and idempotent (upserts keyed by `sku_norm`), re-processing the file after a crash is safe: previously imported rows are simply updated to the same values again.

### 5. Failure Scenario Matrix

| Failure Scenario                       | What Happens                                                             | Result                                 |
|---------------------------------------|---------------------------------------------------------------------------|----------------------------------------|
| R2 / network glitch                   | Task raises `RequestException` → retried with exponential backoff        | Often succeeds automatically           |
| Bad CSV / logic bug                   | Treated as permanent error → no retry                                    | Fast, clear failure                    |
| Worker crashes mid-task               | Message not ACKed, `task_reject_on_worker_lost=True` → message requeued  | Automatic recovery via re-execution    |
| Worker hangs (no exception)           | Heartbeat stops → stale checker marks job as failed                      | No infinite spinner in the UI          |
| User retries while old task exists    | New `attempt_id` invalidates stale updates from old task                 | No split-brain / zombie state updates  |

Compared to a “simple Celery task” import, this design:

- Handles both exception-based failures (retries) and silent failures (stale detection).
- Prevents state corruption during retries and redelivery via `attempt_id` gating.
- Supports at-least-once execution semantics safely via idempotent upserts.
- Guarantees user-facing clarity: imports always converge to a terminal state, with progress and failure reasons exposed for debugging.

-----

## 💻 Tech Stack

  * **Backend:** Python 3, Django, Django REST Framework (DRF)
  * **Asynchronous Task Queue:** Celery
  * **Message Broker:** Redis
  * **Database:** PostgreSQL (with unique indices for SKU enforcement)
  * **Object Storage:** Cloudflare R2 (S3-Compatible) using `boto3`
  * **Frontend:** HTML5, Vanilla JavaScript, Bootstrap (for clean UI)

-----


## 🚀 Installation & Setup

### Prerequisites

  * Python 3.9+
  * PostgreSQL
  * Redis (running on port 6379)
  * An AWS S3 Bucket or Cloudflare R2 Bucket

### 1\. Clone and Configure

```bash
git clone https://github.com/yourusername/product-importer.git
cd product-importer

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2\. Environment Variables

Create a `.env` file in the root directory:

```ini
DEBUG=True
SECRET_KEY=your_secret_key
DATABASE_URL=postgres://user:password@localhost:5432/product_importer
REDIS_URL=redis://localhost:6379/0

# Object Storage (R2 or S3)
R2_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=your_bucket_name
```

### 3\. Database & Migrations

Ensure your Postgres database is created, then run:

```bash
python manage.py migrate
```

### 4\. Run the Application

You need two terminal windows.

**Terminal 1: Django Server**

```bash
python manage.py runserver
```

**Terminal 2: Celery Worker**

```bash
# Replace 'config' with your actual project name containing celery.py
celery -A config worker --loglevel=info
```

Visit `http://127.0.0.1:8000` to start using the app.

-----

## 📖 Usage Guide

### Importing Products

1.  Navigate to the **Import** tab.
2.  Select a CSV file (headers should match: `sku`, `name`, `description`, `active`).
3.  Click **Upload & Import**.
4.  Watch the progress bar:
      * **Phase 1:** Browser uploads file to R2.
      * **Phase 2:** Celery worker parses and adds data to DB.

### Webhooks

1.  Navigate to the **Webhooks** tab.
2.  Add a target URL (e.g., a `webhook.site` URL for testing).
3.  Click **Test** to fire a sample payload.
4.  View the **Last Status** and **Latency** columns to verify connectivity.

-----

## 🔌 API Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/imports/presign/` | Returns a presigned PUT URL for S3/R2. |
| `POST` | `/api/imports/start/` | Triggers the Celery import task. |
| `GET` | `/api/imports/{id}/status/` | Returns job status and progress percentage. |
| `GET` | `/api/products/` | List products (supports filtering). |
| `DELETE`| `/api/products/bulk_delete/` | Deletes all products. |
| `POST` | `/api/webhooks/` | Register a new webhook. |

