from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.db import connection

from .models import Product
from webhooks.tasks import dispatch_webhooks_for_event
from django.utils import timezone


@require_http_methods(["GET"])
def product_list(request):
    """
    List products with filtering + pagination.
    """
    qs = Product.objects.all().order_by("id")

    sku_query = request.GET.get("sku", "").strip()
    search_query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()  # "", "active", "inactive"

    if sku_query:
        qs = qs.filter(sku__icontains=sku_query)

    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if status == "active":
        qs = qs.filter(active=True)
    elif status == "inactive":
        qs = qs.filter(active=False)

    page_number = request.GET.get("page", 1)
    paginator = Paginator(qs, 25)  # 25 per page
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "sku_query": sku_query,
        "search_query": search_query,
        "status": status,
        "current_section": "products",
    }
    return render(request, "products/product_list.html", context)


@require_POST
def product_create(request):
    """
    Create a new product from the modal form.
    """
    sku = (request.POST.get("sku") or "").strip()
    name = (request.POST.get("name") or "").strip()
    description = (request.POST.get("description") or "").strip()
    active = request.POST.get("active") == "on"

    if not sku or not name:
        messages.error(request, "SKU and Name are required.")
        return redirect("product_list")

    product = Product(
        sku=sku,
        name=name,
        description=description,
        active=active,
    )
    try:
        product.save()
        messages.success(request, f"Product '{product.sku}' created.")
    except Exception as e:
        messages.error(request, f"Failed to create product: {e}")
        return redirect("product_list")

    # 🔔 Fire product.created webhooks
    dispatch_webhooks_for_event.delay(
        "product.created",
        {
            "type": "product.created",
            "product": {
                "id": str(product.id),
                "sku": product.sku,
                "name": product.name,
                "description": product.description,
                "active": product.active,
            },
            "timestamp": timezone.now().isoformat(),
        },
    )

    return redirect("product_list")



@require_POST
def product_update(request, pk: int):
    """
    Update an existing product from the modal form.
    """
    product = get_object_or_404(Product, pk=pk)

    sku = (request.POST.get("sku") or "").strip()
    name = (request.POST.get("name") or "").strip()
    description = (request.POST.get("description") or "").strip()
    active = request.POST.get("active") == "on"

    if not sku or not name:
        messages.error(request, "SKU and Name are required.")
        return redirect("product_list")

    product.sku = sku
    product.name = name
    product.description = description
    product.active = active

    try:
        product.save()
        messages.success(request, f"Product '{product.sku}' updated.")
    except Exception as e:
        messages.error(request, f"Failed to update product: {e}")
        return redirect("product_list")

    # 🔔 Fire product.updated webhooks
    dispatch_webhooks_for_event.delay(
        "product.updated",
        {
            "type": "product.updated",
            "product": {
                "id": str(product.id),
                "sku": product.sku,
                "name": product.name,
                "description": product.description,
                "active": product.active,
            },
            "timestamp": timezone.now().isoformat(),
        },
    )

    return redirect("product_list")



@require_POST
def product_delete(request, pk: int):
    """
    Delete a single product (with JS confirmation on the UI).
    """
    product = get_object_or_404(Product, pk=pk)
    sku = product.sku
    product.delete()
    messages.success(request, f"Product '{sku}' deleted.")
    return redirect("product_list")


@require_POST
def product_bulk_delete(request):
    """
    Delete all products. Uses TRUNCATE on Postgres for speed, falls back to
    ORM delete on SQLite for local development.
    """
    vendor = connection.vendor  # 'postgresql', 'sqlite', 'mysql', etc.

    if vendor == "postgresql":
        # Fast path for Postgres
        with connection.cursor() as cursor:
            cursor.execute('TRUNCATE TABLE "products_product" RESTART IDENTITY CASCADE;')
    else:
        # Safe fallback for SQLite / other DBs
        Product.objects.all().delete()

    messages.success(request, "All products have been deleted.")
    return redirect("product_list")
