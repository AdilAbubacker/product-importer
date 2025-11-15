import pandas as pd
from celery import shared_task
from django.db import transaction
from .models import Product

@shared_task(bind=True)
def import_products_task(self, file_path):
    """
    file_path = temporary CSV path saved by Django.
    """
    df = pd.read_csv(file_path)

    # Normalize SKU case-insensitive
    df["SKU"] = df["SKU"].astype(str).str.strip().str.upper()

    total = len(df)

    for index, row in df.iterrows():
        sku = row["SKU"]
        name = row.get("Name", "")
        description = row.get("Description", "")

        # Overwrite if exists
        Product.objects.update_or_create(
            sku=sku,
            defaults={
                "name": name,
                "description": description,
                "active": True,  # default per assignment
            }
        )

        # Optional progress tracking
        self.update_state(
            state="PROGRESS",
            meta={"current": index + 1, "total": total}
        )

    return {"status": "completed", "total": total}
