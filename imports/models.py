from django.db import models


class ImportJob(models.Model):
    STATUS_PENDING = "pending"
    STATUS_QUEUED = "queued"
    STATUS_PARSING = "parsing"
    STATUS_IMPORTING = "importing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_QUEUED, "Queued"),
        (STATUS_PARSING, "Parsing"),
        (STATUS_IMPORTING, "Importing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    file_key = models.CharField(max_length=255, blank=True)  # R2 key like imports/<job_id>.csv
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    total_rows = models.IntegerField(null=True, blank=True)
    processed_rows = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def progress_percent(self) -> float:
        if not self.total_rows or self.total_rows == 0:
            return 0.0
        return round(self.processed_rows * 100.0 / self.total_rows, 2)

    def __str__(self):
        return f"ImportJob {self.id} ({self.status})"

