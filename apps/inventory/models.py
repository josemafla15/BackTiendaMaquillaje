from __future__ import annotations

from django.db import models
from django.db import transaction
from django.core.exceptions import ValidationError

from common.models import TimeStampedModel
from apps.catalog.models import Variant


class Stock(TimeStampedModel):
    """
    Stock disponible por variante.
    Separado del catálogo para poder escalar a múltiples bodegas.

    Lógica de bloqueo:
      available = quantity - reserved
    """
    variant = models.OneToOneField(
        Variant, on_delete=models.CASCADE, related_name="stock"
    )
    quantity = models.PositiveIntegerField(default=0)
    reserved = models.PositiveIntegerField(
        default=0,
        help_text="Unidades reservadas en carritos activos o en proceso de pago.",
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=5,
        help_text="Alerta cuando el stock disponible baje de este número.",
    )

    class Meta:
        db_table = "inventory_stock"

    @property
    def available(self) -> int:
        return max(0, self.quantity - self.reserved)

    @property
    def is_low_stock(self) -> bool:
        return 0 < self.available <= self.low_stock_threshold

    @property
    def is_out_of_stock(self) -> bool:
        return self.available == 0

    def check_availability(self, requested_qty: int) -> bool:
        return self.available >= requested_qty

    @transaction.atomic
    def reserve(self, qty: int) -> None:
        """Bloquea stock durante el proceso de checkout."""
        stock = Stock.objects.select_for_update().get(pk=self.pk)
        if not stock.check_availability(qty):
            raise ValidationError(
                f"Stock insuficiente para '{self.variant.sku}'. "
                f"Disponible: {stock.available}, solicitado: {qty}."
            )
        stock.reserved += qty
        stock.save(update_fields=["reserved", "updated_at"])

    @transaction.atomic
    def release_reservation(self, qty: int) -> None:
        """Libera reserva (carrito abandonado, pago fallido)."""
        stock = Stock.objects.select_for_update().get(pk=self.pk)
        stock.reserved = max(0, stock.reserved - qty)
        stock.save(update_fields=["reserved", "updated_at"])

    @transaction.atomic
    def confirm_sale(self, qty: int) -> None:
        """Descuenta stock real tras pago exitoso."""
        stock = Stock.objects.select_for_update().get(pk=self.pk)
        stock.quantity = max(0, stock.quantity - qty)
        stock.reserved = max(0, stock.reserved - qty)
        stock.save(update_fields=["quantity", "reserved", "updated_at"])

    @transaction.atomic
    def restore(self, qty: int) -> None:
        """Devuelve stock tras reembolso/devolución."""
        stock = Stock.objects.select_for_update().get(pk=self.pk)
        stock.quantity += qty
        stock.save(update_fields=["quantity", "updated_at"])

    def __str__(self) -> str:
        return f"{self.variant.sku} | qty={self.quantity} | reserved={self.reserved}"