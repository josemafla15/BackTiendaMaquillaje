from __future__ import annotations

from django.db import models, transaction
from django.conf import settings
from django.core.validators import MinValueValidator

from common.models import TimeStampedModel
from apps.catalog.models import Variant
from apps.promotions.models import Coupon

import uuid

class Order(TimeStampedModel):
    """
    Pedido principal.

    Relaciones clave:
      Order → OrderItem (1:N): Cada item guarda referencia a la Variant
              y una copia inmutable del precio al momento de compra.
      Order → Refund (1:N): Un pedido puede tener múltiples reembolsos
              parciales o un reembolso total.
    """

    def save(self, *args, **kwargs):
        # Genera wompi_reference automáticamente si está vacío
        if not self.wompi_reference:
            self.wompi_reference = f"ORD-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    class Status(models.TextChoices):
        PENDING_PAYMENT = "PENDING_PAYMENT", "Pendiente de pago"
        PAYMENT_PROCESSING = "PAYMENT_PROCESSING", "Procesando pago"
        PAID = "PAID", "Pagado"
        PREPARING = "PREPARING", "Preparando"
        SHIPPED = "SHIPPED", "Enviado"
        DELIVERED = "DELIVERED", "Entregado"
        CANCELLED = "CANCELLED", "Cancelado"
        REFUNDED = "REFUNDED", "Reembolsado"
        PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED", "Reembolso parcial"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
        db_index=True,
    )

    # Datos del cliente anónimo
    guest_email = models.EmailField(blank=True)
    guest_name = models.CharField(max_length=255, blank=True)

    # Snapshot de montos (inmutables después del pago)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    coupon = models.ForeignKey(
        Coupon, null=True, blank=True, on_delete=models.SET_NULL
    )

    # Dirección de envío (snapshot al momento del pedido)
    shipping_name = models.CharField(max_length=255)
    shipping_address = models.TextField()
    shipping_city = models.CharField(max_length=100)
    shipping_department = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20, blank=True)
    shipping_phone = models.CharField(max_length=20)

    # Integración Wompi
    wompi_transaction_id = models.CharField(max_length=100, blank=True, db_index=True)
    wompi_reference = models.CharField(max_length=100, unique=True, blank=True)

    notes = models.TextField(blank=True)

    class Meta:
        db_table = "orders_orders"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order #{self.id} — {self.user.email} — {self.status}"

    @transaction.atomic
    def cancel(self) -> None:
        """Cancela el pedido y libera el stock."""
        cancellable_statuses = {
            self.Status.PENDING_PAYMENT,
            self.Status.PAYMENT_PROCESSING,
            self.Status.PAID,
            self.Status.PREPARING,
        }
        if self.status not in cancellable_statuses:
            raise ValueError(f"No se puede cancelar un pedido en estado '{self.status}'.")
        for item in self.items.select_related("variant__stock").all():
            item.variant.stock.restore(item.quantity)
        self.status = self.Status.CANCELLED
        self.save(update_fields=["status", "updated_at"])


class OrderItem(TimeStampedModel):
    """
    Línea de un pedido. Guarda el precio como snapshot
    para que cambios futuros en el catálogo no alteren el historial.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        Variant,
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    # Snapshot del producto al momento de la compra
    product_name = models.CharField(max_length=255)
    variant_name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    # Reembolso por ítem
    refunded_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "orders_order_items"

    @property
    def refundable_quantity(self) -> int:
        return self.quantity - self.refunded_quantity

    def __str__(self) -> str:
        return f"{self.sku} x{self.quantity} — Order #{self.order_id}"


class Refund(TimeStampedModel):
    """
    Reembolso asociado a un pedido.

    Flujo:
      1. Se crea Refund con estado PENDING.
      2. Se procesa el reembolso en Wompi.
      3. Si exitoso → status=APPROVED → se llama approve().
      4. Se actualiza el estado del Order (REFUNDED o PARTIALLY_REFUNDED).
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        APPROVED = "APPROVED", "Aprobado"
        REJECTED = "REJECTED", "Rechazado"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="refunds")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    reason = models.TextField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    wompi_refund_id = models.CharField(max_length=100, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,          # ← corregido: era User
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="processed_refunds",
    )

    class Meta:
        db_table = "orders_refunds"

    @transaction.atomic
    def approve(self) -> None:
        """
        Aprueba el reembolso:
          1. Marca como APPROVED.
          2. Restaura stock en cada variante afectada.
          3. Actualiza el estado del pedido.
        """
        from django.utils import timezone

        if self.status != self.Status.PENDING:
            raise ValueError("Solo se pueden aprobar reembolsos en estado PENDING.")

        for refund_item in self.items.select_related(
            "order_item__variant__stock"
        ).all():
            refund_item.order_item.variant.stock.restore(refund_item.quantity)
            refund_item.order_item.refunded_quantity += refund_item.quantity
            refund_item.order_item.save(update_fields=["refunded_quantity"])

        self.status = self.Status.APPROVED
        self.processed_at = timezone.now()
        self.save(update_fields=["status", "processed_at", "updated_at"])
        self._update_order_status()

    def _update_order_status(self) -> None:
        order = self.order
        total_items = sum(i.quantity for i in order.items.all())
        total_refunded_qty = sum(i.refunded_quantity for i in order.items.all())
        if total_refunded_qty >= total_items:
            order.status = Order.Status.REFUNDED
        else:
            order.status = Order.Status.PARTIALLY_REFUNDED
        order.save(update_fields=["status", "updated_at"])


class RefundItem(models.Model):
    """Detalle de qué items y cuántas unidades se reembolsan."""
    refund = models.ForeignKey(Refund, on_delete=models.CASCADE, related_name="items")
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.PROTECT, related_name="refund_items"
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "orders_refund_items"