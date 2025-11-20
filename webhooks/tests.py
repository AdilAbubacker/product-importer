from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.messages import get_messages
from django.utils import timezone
from unittest.mock import patch, Mock
import json

from .models import Webhook


class WebhookModelTests(TestCase):
    """Test Webhook model functionality."""

    def test_webhook_creation(self):
        """Test creating a webhook."""
        webhook = Webhook.objects.create(
            name="Test Webhook",
            target_url="https://example.com/webhook",
            event_type=Webhook.EVENT_PRODUCT_CREATED,
            is_enabled=True
        )
        self.assertEqual(webhook.name, "Test Webhook")
        self.assertTrue(webhook.is_enabled)
        self.assertIsNone(webhook.last_status_code)

    def test_webhook_mark_result_success(self):
        """Test marking webhook result as successful."""
        webhook = Webhook.objects.create(
            name="Test Webhook",
            target_url="https://example.com/webhook",
            event_type=Webhook.EVENT_PRODUCT_CREATED
        )
        
        webhook.mark_result(status_code=200, elapsed_ms=150.5, error=None)
        
        webhook.refresh_from_db()
        self.assertEqual(webhook.last_status_code, 200)
        self.assertEqual(webhook.last_response_ms, 150.5)
        self.assertEqual(webhook.last_error, "")
        self.assertIsNotNone(webhook.last_triggered_at)

    def test_webhook_mark_result_failure(self):
        """Test marking webhook result as failed."""
        webhook = Webhook.objects.create(
            name="Test Webhook",
            target_url="https://example.com/webhook",
            event_type=Webhook.EVENT_PRODUCT_CREATED
        )
        
        webhook.mark_result(
            status_code=None,
            elapsed_ms=100.0,
            error="Connection timeout"
        )
        
        webhook.refresh_from_db()
        self.assertIsNone(webhook.last_status_code)
        self.assertEqual(webhook.last_response_ms, 100.0)
        self.assertEqual(webhook.last_error, "Connection timeout")

    def test_webhook_str_representation(self):
        """Test webhook string representation."""
        webhook = Webhook.objects.create(
            name="Test Webhook",
            target_url="https://example.com/webhook",
            event_type=Webhook.EVENT_PRODUCT_CREATED
        )
        self.assertIn("Test Webhook", str(webhook))
        self.assertIn(Webhook.EVENT_PRODUCT_CREATED, str(webhook))


class WebhookViewTests(TestCase):
    """Test Webhook views."""

    def setUp(self):
        """Set up test client and sample data."""
        self.client = Client()
        self.webhook = Webhook.objects.create(
            name="Test Webhook",
            target_url="https://example.com/webhook",
            event_type=Webhook.EVENT_PRODUCT_CREATED,
            is_enabled=True
        )

    def test_webhook_list_view(self):
        """Test webhook list page loads."""
        response = self.client.get(reverse("webhook_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Webhook")

    def test_webhook_create_success(self):
        """Test creating a webhook successfully."""
        response = self.client.post(
            reverse("webhook_create"),
            {
                "name": "New Webhook",
                "target_url": "https://example.com/new-webhook",
                "event_type": Webhook.EVENT_IMPORT_COMPLETED,
                "is_enabled": "on"
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirect
        
        self.assertTrue(
            Webhook.objects.filter(name="New Webhook").exists()
        )
        
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("created" in str(m).lower() for m in messages))

    def test_webhook_create_missing_fields(self):
        """Test creating webhook with missing required fields fails."""
        response = self.client.post(
            reverse("webhook_create"),
            {
                "name": "New Webhook"
                # Missing target_url and event_type
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            Webhook.objects.filter(name="New Webhook").exists()
        )

    def test_webhook_update_success(self):
        """Test updating a webhook successfully."""
        response = self.client.post(
            reverse("webhook_update", args=[self.webhook.id]),
            {
                "name": "Updated Webhook",
                "target_url": "https://example.com/updated-webhook",
                "event_type": Webhook.EVENT_PRODUCT_UPDATED,
                "is_enabled": "off"
            }
        )
        self.assertEqual(response.status_code, 302)
        
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.name, "Updated Webhook")
        self.assertFalse(self.webhook.is_enabled)

    def test_webhook_delete_success(self):
        """Test deleting a webhook successfully."""
        webhook_id = self.webhook.id
        response = self.client.post(
            reverse("webhook_delete", args=[webhook_id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Webhook.objects.filter(id=webhook_id).exists())

    def test_webhook_toggle_enabled(self):
        """Test toggling webhook enabled status."""
        initial_state = self.webhook.is_enabled
        self.assertTrue(initial_state)
        
        response = self.client.post(
            reverse("webhook_toggle_enabled", args=[self.webhook.id])
        )
        self.assertEqual(response.status_code, 302)
        
        self.webhook.refresh_from_db()
        self.assertFalse(self.webhook.is_enabled)
        
        # Toggle again
        response = self.client.post(
            reverse("webhook_toggle_enabled", args=[self.webhook.id])
        )
        self.webhook.refresh_from_db()
        self.assertTrue(self.webhook.is_enabled)

    @patch('webhooks.views.requests.post')
    def test_webhook_test_success(self, mock_post):
        """Test webhook test succeeds with successful response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        response = self.client.post(
            reverse("webhook_test", args=[self.webhook.id])
        )
        self.assertEqual(response.status_code, 302)
        
        # Verify webhook was called
        mock_post.assert_called_once()
        
        # Verify result was recorded
        self.webhook.refresh_from_db()
        self.assertEqual(self.webhook.last_status_code, 200)
        self.assertIsNotNone(self.webhook.last_response_ms)

    @patch('webhooks.views.requests.post')
    def test_webhook_test_failure(self, mock_post):
        """Test webhook test handles failure."""
        mock_post.side_effect = Exception("Connection error")
        
        response = self.client.post(
            reverse("webhook_test", args=[self.webhook.id])
        )
        self.assertEqual(response.status_code, 302)
        
        # Verify error was recorded
        self.webhook.refresh_from_db()
        self.assertIsNone(self.webhook.last_status_code)
        self.assertIn("error", self.webhook.last_error.lower())

    def test_webhook_test_disabled_webhook(self):
        """Test testing disabled webhook fails."""
        self.webhook.is_enabled = False
        self.webhook.save()
        
        response = self.client.post(
            reverse("webhook_test", args=[self.webhook.id])
        )
        self.assertEqual(response.status_code, 302)
        
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("disabled" in str(m).lower() for m in messages))

    def test_webhook_test_not_found(self):
        """Test testing non-existent webhook returns 404."""
        response = self.client.post(
            reverse("webhook_test", args=[999])
        )
        self.assertEqual(response.status_code, 404)


class WebhookTaskTests(TestCase):
    """Test Webhook dispatch tasks (with mocking)."""

    @patch('webhooks.tasks.requests.post')
    def test_dispatch_webhooks_for_event_success(self, mock_post):
        """Test dispatching webhooks successfully."""
        # Create enabled webhook
        webhook = Webhook.objects.create(
            name="Test Webhook",
            target_url="https://example.com/webhook",
            event_type=Webhook.EVENT_PRODUCT_CREATED,
            is_enabled=True
        )
        
        # Create disabled webhook (should not be called)
        Webhook.objects.create(
            name="Disabled Webhook",
            target_url="https://example.com/disabled",
            event_type=Webhook.EVENT_PRODUCT_CREATED,
            is_enabled=False
        )
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Import and call task directly (using apply() for testing)
        from webhooks.tasks import dispatch_webhooks_for_event
        payload = {"type": "product.created", "product": {"id": "123"}}
        
        # Call task synchronously for testing
        dispatch_webhooks_for_event.apply(
            args=[Webhook.EVENT_PRODUCT_CREATED, payload]
        )
        
        # Verify only enabled webhook was called
        self.assertEqual(mock_post.call_count, 1)
        mock_post.assert_called_once_with(
            webhook.target_url,
            json=payload,
            timeout=5
        )
        
        # Verify result was recorded
        webhook.refresh_from_db()
        self.assertEqual(webhook.last_status_code, 200)

    @patch('webhooks.tasks.requests.post')
    def test_dispatch_webhooks_handles_errors(self, mock_post):
        """Test webhook dispatch handles errors gracefully."""
        webhook = Webhook.objects.create(
            name="Test Webhook",
            target_url="https://example.com/webhook",
            event_type=Webhook.EVENT_PRODUCT_CREATED,
            is_enabled=True
        )
        
        # Mock failure
        mock_post.side_effect = Exception("Connection timeout")
        
        from webhooks.tasks import dispatch_webhooks_for_event
        payload = {"type": "product.created"}
        
        # Call task synchronously for testing
        dispatch_webhooks_for_event.apply(
            args=[Webhook.EVENT_PRODUCT_CREATED, payload]
        )
        
        # Verify error was recorded
        webhook.refresh_from_db()
        self.assertIsNone(webhook.last_status_code)
        self.assertIn("error", webhook.last_error.lower())

    def test_dispatch_webhooks_only_for_event_type(self):
        """Test webhooks only dispatch for matching event types."""
        # Create webhook for product.created
        webhook1 = Webhook.objects.create(
            name="Product Created Webhook",
            target_url="https://example.com/product-created",
            event_type=Webhook.EVENT_PRODUCT_CREATED,
            is_enabled=True
        )
        
        # Create webhook for import.completed
        Webhook.objects.create(
            name="Import Completed Webhook",
            target_url="https://example.com/import-completed",
            event_type=Webhook.EVENT_IMPORT_COMPLETED,
            is_enabled=True
        )
        
        with patch('webhooks.tasks.requests.post') as mock_post:
            from webhooks.tasks import dispatch_webhooks_for_event
            payload = {"type": "product.created"}
            
            # Call task synchronously for testing
            dispatch_webhooks_for_event.apply(
                args=[Webhook.EVENT_PRODUCT_CREATED, payload]
            )
            
            # Only product.created webhook should be called
            self.assertEqual(mock_post.call_count, 1)
            mock_post.assert_called_once_with(
                webhook1.target_url,
                json=payload,
                timeout=5
            )
