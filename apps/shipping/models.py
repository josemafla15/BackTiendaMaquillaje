from django.db import models
from django.core.validators import MinValueValidator
from common.models import TimeStampedModel


class ShippingRate(TimeStampedModel):
    """
    Tarifa de envío por ciudad o departamento.

    Lógica de resolución (orden de prioridad):
      1. Coincidencia exacta por ciudad (city != "")
      2. Coincidencia por departamento (city == "")
      3. Tarifa por defecto (is_default=True)

    Si el subtotal >= free_shipping_from, el envío es gratis.
    """

    name = models.CharField(
        max_length=100,
        help_text="Nombre descriptivo. Ej: 'Bogotá', 'Antioquia', 'Resto del país'",
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Nombre exacto de la ciudad. Vacío = aplica a todo el departamento.",
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Departamento. Vacío = aplica a todo el país (default).",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Costo del envío en COP.",
    )
    free_shipping_from = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Monto mínimo de compra para envío gratis. Null = nunca gratis.",
    )
    estimated_days_min = models.PositiveSmallIntegerField(
        default=1,
        help_text="Días hábiles mínimos de entrega.",
    )
    estimated_days_max = models.PositiveSmallIntegerField(
        default=3,
        help_text="Días hábiles máximos de entrega.",
    )
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Tarifa de respaldo cuando no hay coincidencia por ciudad/departamento.",
    )

    class Meta:
        db_table = "shipping_rates"
        ordering = ["department", "city"]
        constraints = [
            # Solo puede haber una tarifa default activa
            models.UniqueConstraint(
                fields=["is_default"],
                condition=models.Q(is_default=True, is_active=True),
                name="unique_active_default_shipping_rate",
            )
        ]

    def __str__(self) -> str:
        location = self.city or self.department or "Todo el país"
        return f"{self.name} — {location} — ${self.price:,.0f} COP"

    def is_free_for(self, subtotal: float) -> bool:
        """Retorna True si el subtotal califica para envío gratis."""
        if self.free_shipping_from is None:
            return False
        return subtotal >= float(self.free_shipping_from)

    def effective_price(self, subtotal: float) -> float:
        """Retorna 0 si aplica envío gratis, o el precio normal."""
        return 0.0 if self.is_free_for(subtotal) else float(self.price)