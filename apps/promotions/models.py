from __future__ import annotations

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from common.models import TimeStampedModel

from decimal import Decimal



class Coupon(TimeStampedModel):
    """
    Cupón de descuento.
    Soporta:
      - Porcentaje o monto fijo
      - Uso único (max_uses=1) o múltiple
      - Fecha de expiración
      - Monto mínimo de compra
      - Restricción a productos/categorías específicas (extensible)
    """

    class DiscountType(models.TextChoices):
        PERCENTAGE = "PERCENTAGE", "Porcentaje"
        FIXED = "FIXED", "Monto fijo"

    code = models.CharField(max_length=50, unique=True, db_index=True)
    description = models.CharField(max_length=255, blank=True)
    discount_type = models.CharField(
        max_length=20, choices=DiscountType.choices, default=DiscountType.PERCENTAGE
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    max_discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Tope máximo del descuento para cupones por porcentaje.",
    )
    minimum_order_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    max_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Null = ilimitado.",
    )
    used_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Restricciones opcionales
    applicable_products = models.ManyToManyField(
        "catalog.Product", blank=True, related_name="coupons"
    )
    applicable_categories = models.ManyToManyField(
        "catalog.Category", blank=True, related_name="coupons"
    )

    class Meta:
        db_table = "promotions_coupons"

    @property
    def is_valid(self) -> bool:
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if now < self.valid_from:
            return False
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False
        return True

    def calculate_discount(self, subtotal: Decimal) -> Decimal:
        from decimal import Decimal
        if self.discount_type == self.DiscountType.PERCENTAGE:
            discount = subtotal * (self.discount_value / Decimal("100"))
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
        else:
            discount = min(self.discount_value, subtotal)
        return discount

    def __str__(self) -> str:
        return f"{self.code} ({self.discount_type}: {self.discount_value})"