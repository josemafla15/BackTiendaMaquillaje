from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from apps.catalog.models import Brand, Product, Variant
from apps.inventory.models import Stock
from apps.orders.models import Order, OrderItem, Refund, RefundItem

from unittest.mock import patch


User = get_user_model()


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def make_user(**kwargs):
    defaults = dict(username="user", email="user@test.com", password="pass1234")
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def make_admin(**kwargs):
    defaults = dict(username="admin", email="admin@test.com", password="pass1234", is_staff=True)
    defaults.update(kwargs)
    return User.objects.create_superuser(**defaults)


def make_variant(sku="SKU-001", price="50000", qty=10):
    brand = Brand.objects.create(name="TestBrand", slug="testbrand")
    product = Product.objects.create(
        name="Labial Test", slug=f"labial-{sku}",
        brand=brand, description="desc"
    )
    variant = Variant.objects.create(
        product=product, sku=sku,
        name="Tono Test", price=Decimal(price)
    )
    Stock.objects.create(variant=variant, quantity=qty)
    return variant


def make_order(user=None, status=Order.Status.PAID, qty=2):
    variant = make_variant()
    order = Order.objects.create(
        user=user,
        status=status,
        subtotal=Decimal("100000"),
        total=Decimal("119000"),
        shipping_name="Test",
        shipping_address="Calle 1",
        shipping_city="Bogotá",
        shipping_department="Cundinamarca",
        shipping_phone="3001234567",
    )
    item = OrderItem.objects.create(
        order=order,
        variant=variant,
        product_name=variant.product.name,
        variant_name=variant.name,
        sku=variant.sku,
        unit_price=variant.price,
        quantity=qty,
        subtotal=variant.price * qty,
    )
    return order, item, variant


# ══════════════════════════════════════════════════════════════════════════════
# Stock Tests
# ══════════════════════════════════════════════════════════════════════════════

class StockReserveTest(TestCase):

    def setUp(self):
        self.variant = make_variant(qty=10)
        self.stock = self.variant.stock

    def test_available_property(self):
        self.assertEqual(self.stock.available, 10)

    def test_reserve_reduces_available(self):
        self.stock.reserve(3)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.available, 7)
        self.assertEqual(self.stock.reserved, 3)

    def test_reserve_insufficient_stock_raises(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.stock.reserve(99)

    def test_release_reservation(self):
        self.stock.reserve(4)
        self.stock.release_reservation(4)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.reserved, 0)

    def test_release_cannot_go_negative(self):
        self.stock.release_reservation(999)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.reserved, 0)

    def test_confirm_sale(self):
        self.stock.reserve(2)
        self.stock.confirm_sale(2)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 8)
        self.assertEqual(self.stock.reserved, 0)

    def test_restore_adds_stock(self):
        self.stock.confirm_sale(2)
        self.stock.restore(2)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 10)

    def test_is_low_stock(self):
        self.stock.quantity = 3
        self.stock.save()
        self.assertTrue(self.stock.is_low_stock)

    def test_is_out_of_stock(self):
        self.stock.quantity = 0
        self.stock.save()
        self.assertTrue(self.stock.is_out_of_stock)


# ══════════════════════════════════════════════════════════════════════════════
# Order Tests
# ══════════════════════════════════════════════════════════════════════════════

class OrderCancelTest(TestCase):

    def test_cancel_paid_order_releases_stock(self):
        order, item, variant = make_order(status=Order.Status.PAID)
        variant.stock.reserve(item.quantity)

        order.cancel()

        variant.stock.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(variant.stock.reserved, 0)

    def test_cancel_invalid_status_raises(self):
        order, _, _ = make_order(status=Order.Status.DELIVERED)
        with self.assertRaises(ValueError):
            order.cancel()

    def test_cancel_shipped_raises(self):
        order, _, _ = make_order(status=Order.Status.SHIPPED)
        with self.assertRaises(ValueError):
            order.cancel()

    def test_wompi_reference_auto_generated(self):
        order, _, _ = make_order()
        self.assertTrue(order.wompi_reference.startswith("ORD-"))
        self.assertEqual(len(order.wompi_reference), 16)  # ORD- + 12 hex


# ══════════════════════════════════════════════════════════════════════════════
# Refund Tests
# ══════════════════════════════════════════════════════════════════════════════

class RefundApproveTest(TestCase):

    def setUp(self):
        self.order, self.item, self.variant = make_order(status=Order.Status.PAID, qty=4)
        # Simula stock ya confirmado
        self.variant.stock.quantity = 6
        self.variant.stock.save()

    def _make_refund(self, qty=2):
        refund = Refund.objects.create(
            order=self.order,
            reason="Producto defectuoso",
            amount=Decimal("100000"),
        )
        RefundItem.objects.create(
            refund=refund,
            order_item=self.item,
            quantity=qty,
        )
        return refund

    def test_approve_restores_stock(self):
        refund = self._make_refund(qty=2)
        refund.approve()

        self.variant.stock.refresh_from_db()
        self.assertEqual(self.variant.stock.quantity, 8)  # 6 + 2

    def test_approve_updates_refunded_quantity(self):
        refund = self._make_refund(qty=2)
        refund.approve()

        self.item.refresh_from_db()
        self.assertEqual(self.item.refunded_quantity, 2)

    def test_partial_refund_sets_order_status(self):
        refund = self._make_refund(qty=2)  # 2 de 4 → parcial
        refund.approve()

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PARTIALLY_REFUNDED)

    def test_full_refund_sets_order_status(self):
        refund = self._make_refund(qty=4)  # todos → total
        refund.approve()

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.REFUNDED)

    def test_approve_already_approved_raises(self):
        refund = self._make_refund()
        refund.approve()
        with self.assertRaises(ValueError):
            refund.approve()

    def test_refundable_quantity_property(self):
        self.assertEqual(self.item.refundable_quantity, 4)
        self.item.refunded_quantity = 2
        self.item.save()
        self.assertEqual(self.item.refundable_quantity, 2)


# ══════════════════════════════════════════════════════════════════════════════
# Refund API Tests (Admin)
# ══════════════════════════════════════════════════════════════════════════════

class RefundAPITest(APITestCase):

    def setUp(self):
        self.admin = make_admin()
        self.client.force_authenticate(user=self.admin)
        self.order, self.item, self.variant = make_order(status=Order.Status.PAID, qty=4)
        self.variant.stock.quantity = 10
        self.variant.stock.save()

        self.refund = Refund.objects.create(
            order=self.order,
            reason="Devolución",
            amount=Decimal("50000"),
        )
        RefundItem.objects.create(
            refund=self.refund,
            order_item=self.item,
            quantity=2,
        )

    def test_list_refunds(self):
        res = self.client.get("/api/orders/refunds/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_approve_refund(self):
        res = self.client.post(f"/api/orders/refunds/{self.refund.id}/approve/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.refund.refresh_from_db()
        self.assertEqual(self.refund.status, Refund.Status.APPROVED)

    def test_reject_refund(self):
        res = self.client.post(f"/api/orders/refunds/{self.refund.id}/reject/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.refund.refresh_from_db()
        self.assertEqual(self.refund.status, Refund.Status.REJECTED)

    def test_reject_already_approved_fails(self):
        self.refund.approve()
        res = self.client.post(f"/api/orders/refunds/{self.refund.id}/reject/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_admin_cannot_access(self):
        user = make_user(email="otro@test.com")
        self.client.force_authenticate(user=user)
        res = self.client.get("/api/orders/refunds/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_refund_with_items(self):
        res = self.client.post("/api/orders/refunds/", {
            "order": self.order.id,
            "reason": "Talla incorrecta",
            "amount": "25000",
            "items_write": [
                {"order_item": self.item.id, "quantity": 1, "reason": ""}
            ]
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_create_refund_exceeds_quantity_fails(self):
        res = self.client.post("/api/orders/refunds/", {
            "order": self.order.id,
            "reason": "Error",
            "amount": "99999",
            "items_write": [
                {"order_item": self.item.id, "quantity": 999, "reason": ""}
            ]
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


# ══════════════════════════════════════════════════════════════════════════════
# Webhook Tests
# ══════════════════════════════════════════════════════════════════════════════

class WompiWebhookTest(APITestCase):

    def setUp(self):
        self.order, self.item, self.variant = make_order(
            status=Order.Status.PENDING_PAYMENT, qty=2
        )
        self.variant.stock.reserve(2)
        self.url = "/api/payments/webhook/"

    def _build_payload(self, wompi_status: str, sign_valid: bool = True):
        return {
            "event": "transaction.updated",
            "data": {
                "transaction": {
                    "id": "wompi-txn-001",
                    "reference": self.order.wompi_reference,
                    "status": wompi_status,
                }
            },
            "signature": {
                "properties": {"transaction.id": "wompi-txn-001"},
                "checksum": "valid" if sign_valid else "invalid",
            },
            "timestamp": "1234567890",
        }

    @patch("apps.payments.views.WompiService.validate_webhook_signature", return_value=True)
    def test_approved_sets_paid_and_confirms_stock(self, _mock):
        payload = self._build_payload("APPROVED")
        res = self.client.post(self.url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)

        self.variant.stock.refresh_from_db()
        self.assertEqual(self.variant.stock.quantity, 8)   # 10 - 2
        self.assertEqual(self.variant.stock.reserved, 0)

    @patch("apps.payments.views.WompiService.validate_webhook_signature", return_value=True)
    def test_declined_sets_cancelled_and_releases_stock(self, _mock):
        payload = self._build_payload("DECLINED")
        self.client.post(self.url, payload, format="json")

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)

        self.variant.stock.refresh_from_db()
        self.assertEqual(self.variant.stock.reserved, 0)

    @patch("apps.payments.views.WompiService.validate_webhook_signature", return_value=False)
    def test_invalid_signature_returns_401(self, _mock):
        payload = self._build_payload("APPROVED", sign_valid=False)
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("apps.payments.views.WompiService.validate_webhook_signature", return_value=True)
    def test_unknown_reference_does_not_crash(self, _mock):
        payload = self._build_payload("APPROVED")
        payload["data"]["transaction"]["reference"] = "ORD-NOEXISTE"
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @patch("apps.payments.views.WompiService.validate_webhook_signature", return_value=True)
    def test_pending_sets_payment_processing(self, _mock):
        payload = self._build_payload("PENDING")
        self.client.post(self.url, payload, format="json")

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAYMENT_PROCESSING)

    def test_missing_payload_fields_returns_400(self):
        res = self.client.post(self.url, {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)



class RefundWompiIntegrationTest(TestCase):

    def setUp(self):
        self.order, self.item, self.variant = make_order(status=Order.Status.PAID, qty=4)
        self.order.wompi_transaction_id = "wompi-txn-123"
        self.order.save(update_fields=["wompi_transaction_id"])
        self.variant.stock.quantity = 10
        self.variant.stock.save()

    def _make_refund(self, qty=2):
        refund = Refund.objects.create(
            order=self.order,
            reason="Devolución",
            amount=Decimal("50000"),
        )
        RefundItem.objects.create(
            refund=refund,
            order_item=self.item,
            quantity=qty,
        )
        return refund

    @patch("apps.payments.wompi.WompiService.refund_transaction")
    def test_approve_calls_wompi(self, mock_refund):
        mock_refund.return_value = {"id": "wompi-refund-001"}
        refund = self._make_refund()
        refund.approve()

        mock_refund.assert_called_once_with("wompi-txn-123", 5000000)  # 50000 * 100

    @patch("apps.payments.wompi.WompiService.refund_transaction")
    def test_approve_saves_wompi_refund_id(self, mock_refund):
        mock_refund.return_value = {"id": "wompi-refund-001"}
        refund = self._make_refund()
        refund.approve()

        refund.refresh_from_db()
        self.assertEqual(refund.wompi_refund_id, "wompi-refund-001")

    @patch("apps.payments.wompi.WompiService.refund_transaction")
    def test_approve_fails_if_wompi_returns_none(self, mock_refund):
        mock_refund.return_value = None
        refund = self._make_refund()

        with self.assertRaises(ValueError) as ctx:
            refund.approve()

        self.assertIn("Wompi", str(ctx.exception))
        # Stock no debe haberse restaurado
        self.variant.stock.refresh_from_db()
        self.assertEqual(self.variant.stock.quantity, 10)

    @patch("apps.payments.wompi.WompiService.refund_transaction")
    def test_approve_without_transaction_id_skips_wompi(self, mock_refund):
        """Si la orden no tiene wompi_transaction_id (ej: sandbox), aprueba sin llamar Wompi."""
        self.order.wompi_transaction_id = ""
        self.order.save(update_fields=["wompi_transaction_id"])

        refund = self._make_refund()
        refund.approve()

        mock_refund.assert_not_called()
        refund.refresh_from_db()
        self.assertEqual(refund.status, Refund.Status.APPROVED)