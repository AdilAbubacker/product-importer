from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, Mock
import json

from .models import ImportJob


class ImportJobModelTests(TestCase):
    """Test ImportJob model functionality."""

    def test_import_job_creation(self):
        """Test creating an import job."""
        job = ImportJob.objects.create(
            status=ImportJob.STATUS_PENDING,
            processed_rows=0
        )
        self.assertEqual(job.status, ImportJob.STATUS_PENDING)
        self.assertEqual(job.processed_rows, 0)
        self.assertIsNone(job.total_rows)

    def test_progress_percent_no_total_rows(self):
        """Test progress calculation when total_rows is None."""
        job = ImportJob.objects.create(
            status=ImportJob.STATUS_PENDING,
            processed_rows=0
        )
        self.assertEqual(job.progress_percent(), 0.0)

    def test_progress_percent_zero_total(self):
        """Test progress calculation when total_rows is 0."""
        job = ImportJob.objects.create(
            status=ImportJob.STATUS_PENDING,
            total_rows=0,
            processed_rows=0
        )
        self.assertEqual(job.progress_percent(), 0.0)

    def test_progress_percent_calculation(self):
        """Test progress calculation."""
        job = ImportJob.objects.create(
            status=ImportJob.STATUS_IMPORTING,
            total_rows=100,
            processed_rows=50
        )
        self.assertEqual(job.progress_percent(), 50.0)

    def test_progress_percent_rounding(self):
        """Test progress calculation rounds correctly."""
        job = ImportJob.objects.create(
            status=ImportJob.STATUS_IMPORTING,
            total_rows=3,
            processed_rows=1
        )
        # 1/3 = 33.333... should round to 33.33
        self.assertEqual(job.progress_percent(), 33.33)

    def test_import_job_str_representation(self):
        """Test import job string representation."""
        job = ImportJob.objects.create(
            status=ImportJob.STATUS_PENDING
        )
        self.assertIn(str(job.id), str(job))
        self.assertIn(ImportJob.STATUS_PENDING, str(job))


class ImportViewTests(TestCase):
    """Test Import views."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    @patch('imports.views.generate_presigned_put_url')
    def test_create_upload_job(self, mock_presigned_url):
        """Test creating an upload job."""
        mock_presigned_url.return_value = "https://example.com/upload-url"
        
        response = self.client.post(reverse("create_upload_job"))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertIn("job_id", data)
        self.assertIn("upload_url", data)
        self.assertEqual(data["upload_url"], "https://example.com/upload-url")
        
        # Verify job was created
        job = ImportJob.objects.get(id=data["job_id"])
        self.assertEqual(job.status, ImportJob.STATUS_PENDING)
        self.assertIn("imports/", job.file_key)

    @patch('imports.views.process_import_job')
    def test_start_import_job_success(self, mock_task):
        """Test starting an import job successfully."""
        job = ImportJob.objects.create(
            status=ImportJob.STATUS_PENDING,
            file_key="imports/1.csv"
        )
        
        response = self.client.post(
            reverse("start_import_job", args=[job.id])
        )
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data["status"], ImportJob.STATUS_QUEUED)
        
        # Verify job status updated
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJob.STATUS_QUEUED)
        
        # Verify task was called
        mock_task.delay.assert_called_once_with(job.id)

    def test_start_import_job_not_found(self):
        """Test starting non-existent job returns 404."""
        response = self.client.post(
            reverse("start_import_job", args=[999])
        )
        self.assertEqual(response.status_code, 404)

    def test_start_import_job_wrong_status(self):
        """Test starting job in wrong status returns error."""
        job = ImportJob.objects.create(
            status=ImportJob.STATUS_COMPLETED,
            file_key="imports/1.csv"
        )
        
        response = self.client.post(
            reverse("start_import_job", args=[job.id])
        )
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertIn("error", data)

    def test_import_job_status_success(self):
        """Test getting import job status."""
        job = ImportJob.objects.create(
            status=ImportJob.STATUS_IMPORTING,
            total_rows=100,
            processed_rows=50,
            file_key="imports/1.csv"
        )
        
        response = self.client.get(
            reverse("import_job_status", args=[job.id])
        )
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data["job_id"], job.id)
        self.assertEqual(data["status"], ImportJob.STATUS_IMPORTING)
        self.assertEqual(data["processed_rows"], 50)
        self.assertEqual(data["total_rows"], 100)
        self.assertEqual(data["percentage"], 50.0)

    def test_import_job_status_not_found(self):
        """Test getting status of non-existent job returns 404."""
        response = self.client.get(
            reverse("import_job_status", args=[999])
        )
        self.assertEqual(response.status_code, 404)

    def test_upload_products_page(self):
        """Test upload products page loads."""
        response = self.client.get(reverse("upload_products_page"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload")


class ImportTaskTests(TestCase):
    """Test Import tasks (with mocking)."""

    @patch('imports.tasks.generate_presigned_get_url')
    @patch('imports.tasks.requests.get')
    @patch('imports.tasks.upsert_products_batch')
    @patch('imports.tasks.dispatch_webhooks_for_event')
    def test_process_import_job_success(
        self, mock_webhook, mock_upsert, mock_requests_get, mock_presigned
    ):
        """Test processing import job successfully."""
        # Mock presigned URL
        mock_presigned.return_value = "https://example.com/file.csv"
        
        # Mock CSV content
        csv_content = "sku,name,description\nPROD-001,Product 1,Desc 1\nPROD-002,Product 2,Desc 2\n"
        mock_response = Mock()
        mock_response.iter_lines.return_value = [
            b"sku,name,description",
            b"PROD-001,Product 1,Desc 1",
            b"PROD-002,Product 2,Desc 2"
        ]
        mock_response.raise_for_status = Mock()
        mock_requests_get.return_value = mock_response
        
        # Create job
        job = ImportJob.objects.create(
            status=ImportJob.STATUS_PENDING,
            file_key="imports/1.csv"
        )
        
        # Import and call task synchronously for testing
        from imports.tasks import process_import_job
        process_import_job.apply(args=[job.id])
        
        # Verify job completed
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJob.STATUS_COMPLETED)
        self.assertEqual(job.total_rows, 2)
        self.assertEqual(job.processed_rows, 2)
        
        # Verify upsert was called
        self.assertTrue(mock_upsert.called)
        
        # Verify webhook was called
        mock_webhook.delay.assert_called_once()

    @patch('imports.tasks.generate_presigned_get_url')
    @patch('imports.tasks.requests.get')
    def test_process_import_job_handles_missing_file_key(
        self, mock_requests_get, mock_presigned
    ):
        """Test processing job without file_key raises error."""
        job = ImportJob.objects.create(
            status=ImportJob.STATUS_PENDING,
            file_key=""  # No file key
        )
        
        from imports.tasks import process_import_job
        
        # Call task synchronously - should raise ValueError
        with self.assertRaises(ValueError):
            process_import_job.apply(args=[job.id])
        
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJob.STATUS_FAILED)
        self.assertIn("file_key", job.error_message)
