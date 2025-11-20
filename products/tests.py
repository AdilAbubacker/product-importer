from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.messages import get_messages
from django.db import IntegrityError

from .models import Product


class ProductModelTests(TestCase):
    """Test Product model functionality."""

    def test_product_creation(self):
        """Test creating a product."""
        product = Product.objects.create(
            sku="PROD-001",
            name="Test Product",
            description="A test product",
            active=True
        )
        self.assertEqual(product.sku, "PROD-001")
        self.assertEqual(product.sku_norm, "prod-001")
        self.assertTrue(product.active)
        self.assertIsNotNone(product.id)

    def test_sku_normalization(self):
        """Test that SKU is normalized (lowercase, trimmed)."""
        product = Product.objects.create(
            sku="  PROD-001  ",
            name="Test Product"
        )
        self.assertEqual(product.sku_norm, "prod-001")

    def test_sku_case_insensitive_uniqueness(self):
        """Test that SKUs are unique case-insensitively."""
        Product.objects.create(sku="PROD-001", name="Product 1")
        
        # Should fail - same SKU different case
        with self.assertRaises(IntegrityError):
            Product.objects.create(sku="prod-001", name="Product 2")

    def test_product_str_representation(self):
        """Test product string representation."""
        product = Product.objects.create(
            sku="PROD-001",
            name="Test Product"
        )
        self.assertEqual(str(product), "PROD-001 - Test Product")

    def test_product_defaults(self):
        """Test default values."""
        product = Product.objects.create(
            sku="PROD-001",
            name="Test Product"
        )
        self.assertTrue(product.active)
        self.assertIsNotNone(product.created_at)
        self.assertIsNotNone(product.updated_at)


class ProductViewTests(TestCase):
    """Test Product views."""

    def setUp(self):
        """Set up test client and sample data."""
        self.client = Client()
        self.product = Product.objects.create(
            sku="PROD-001",
            name="Test Product",
            description="Test description",
            active=True
        )
        self.product2 = Product.objects.create(
            sku="PROD-002",
            name="Another Product",
            description="Another description",
            active=False
        )

    def test_product_list_view(self):
        """Test product list page loads."""
        response = self.client.get(reverse("product_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Product")
        self.assertContains(response, "Another Product")

    def test_product_list_filtering_by_sku(self):
        """Test filtering products by SKU."""
        response = self.client.get(reverse("product_list") + "?sku=PROD-001")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Product")
        self.assertNotContains(response, "Another Product")

    def test_product_list_filtering_by_search_query(self):
        """Test filtering products by name/description search."""
        response = self.client.get(reverse("product_list") + "?q=Another")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Another Product")
        self.assertNotContains(response, "Test Product")

    def test_product_list_filtering_by_status_active(self):
        """Test filtering products by active status."""
        response = self.client.get(reverse("product_list") + "?status=active")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Product")
        self.assertNotContains(response, "Another Product")

    def test_product_list_filtering_by_status_inactive(self):
        """Test filtering products by inactive status."""
        response = self.client.get(reverse("product_list") + "?status=inactive")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Another Product")
        self.assertNotContains(response, "Test Product")

    def test_product_list_pagination(self):
        """Test pagination works."""
        # Create 30 products to test pagination (25 per page)
        for i in range(28):
            Product.objects.create(
                sku=f"PROD-{i+100}",
                name=f"Product {i+100}"
            )
        
        response = self.client.get(reverse("product_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(hasattr(response.context["page_obj"], "paginator"))

    def test_product_create_success(self):
        """Test creating a product successfully."""
        response = self.client.post(
            reverse("product_create"),
            {
                "sku": "PROD-003",
                "name": "New Product",
                "description": "New description",
                "active": "on"
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirect
        self.assertTrue(Product.objects.filter(sku="PROD-003").exists())
        
        # Check success message
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("created" in str(m).lower() for m in messages))

    def test_product_create_missing_sku(self):
        """Test creating product without SKU fails."""
        response = self.client.post(
            reverse("product_create"),
            {
                "name": "New Product",
                "description": "New description"
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(name="New Product").exists())
        
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("required" in str(m).lower() for m in messages))

    def test_product_create_missing_name(self):
        """Test creating product without name fails."""
        response = self.client.post(
            reverse("product_create"),
            {
                "sku": "PROD-003",
                "description": "New description"
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(sku="PROD-003").exists())

    def test_product_update_success(self):
        """Test updating a product successfully."""
        response = self.client.post(
            reverse("product_update", args=[str(self.product.id)]),
            {
                "sku": "PROD-001-UPDATED",
                "name": "Updated Product",
                "description": "Updated description",
                "active": "off"
            }
        )
        self.assertEqual(response.status_code, 302)
        
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Updated Product")
        self.assertFalse(self.product.active)

    def test_product_update_not_found(self):
        """Test updating non-existent product returns 404."""
        import uuid
        fake_id = uuid.uuid4()
        response = self.client.post(
            reverse("product_update", args=[str(fake_id)]),
            {
                "sku": "PROD-001",
                "name": "Updated Product"
            }
        )
        self.assertEqual(response.status_code, 404)

    def test_product_delete_success(self):
        """Test deleting a product successfully."""
        product_id = self.product.id
        response = self.client.post(
            reverse("product_delete", args=[str(product_id)])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(id=product_id).exists())

    def test_product_bulk_delete(self):
        """Test bulk delete removes all products."""
        # Create a few more products
        Product.objects.create(sku="PROD-003", name="Product 3")
        Product.objects.create(sku="PROD-004", name="Product 4")
        
        self.assertEqual(Product.objects.count(), 4)
        
        response = self.client.post(reverse("product_bulk_delete"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Product.objects.count(), 0)
        
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("deleted" in str(m).lower() for m in messages))

    def test_product_bulk_delete_empty(self):
        """Test bulk delete works when no products exist."""
        Product.objects.all().delete()
        
        response = self.client.post(reverse("product_bulk_delete"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Product.objects.count(), 0)
