from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from .models import ShippingRate

logger = logging.getLogger(__name__)


@dataclass
class ShippingResult:
    rate: ShippingRate | None
    price: Decimal
    is_free: bool
    free_shipping_from: Decimal | None
    estimated_days_min: int
    estimated_days_max: int
    message: str

    @property
    def estimated_delivery(self) -> str:
        if self.estimated_days_min == self.estimated_days_max:
            return f"{self.estimated_days_min} día(s) hábil(es)"
        return f"{self.estimated_days_min} a {self.estimated_days_max} días hábiles"


def calculate_shipping(
    city: str,
    department: str,
    subtotal: Decimal,
) -> ShippingResult:
    """
    Calcula el costo de envío según ciudad, departamento y subtotal.

    Prioridad de resolución:
      1. Coincidencia exacta por ciudad (normalizada a minúsculas)
      2. Coincidencia por departamento
      3. Tarifa por defecto (is_default=True)
      4. Sin cobertura → precio 0 con mensaje de advertencia

    Args:
        city: Nombre de la ciudad del destinatario.
        department: Departamento del destinatario.
        subtotal: Subtotal del carrito en COP (sin IVA).

    Returns:
        ShippingResult con precio efectivo y metadata de entrega.
    """
    city_normalized = city.strip().lower()
    dept_normalized = department.strip().lower()

    active_rates = ShippingRate.objects.filter(is_active=True)

    # 1. Coincidencia exacta por ciudad
    rate = active_rates.filter(
        city__iexact=city_normalized
    ).first()

    # 2. Coincidencia por departamento
    if not rate:
        rate = active_rates.filter(
            department__iexact=dept_normalized,
            city=""
        ).first()

    # 3. Tarifa por defecto
    if not rate:
        rate = active_rates.filter(is_default=True).first()

    if not rate:
        logger.warning(
            "No se encontró tarifa de envío para ciudad='%s', departamento='%s'",
            city,
            department,
        )
        return ShippingResult(
            rate=None,
            price=Decimal("0"),
            is_free=False,
            free_shipping_from=None,
            estimated_days_min=5,
            estimated_days_max=10,
            message="No hay cobertura de envío para esta ubicación. Nos contactaremos contigo.",
        )

    is_free = rate.is_free_for(subtotal)
    effective_price = Decimal("0") if is_free else rate.price

    if is_free:
        message = "¡Envío gratis!"
    elif rate.free_shipping_from:
        remaining = rate.free_shipping_from - subtotal
        message = f"Agrega ${remaining:,.0f} más para envío gratis"
    else:
        message = f"Envío a {rate.city or rate.department or 'tu ubicación'}"

    return ShippingResult(
        rate=rate,
        price=effective_price,
        is_free=is_free,
        free_shipping_from=rate.free_shipping_from,
        estimated_days_min=rate.estimated_days_min,
        estimated_days_max=rate.estimated_days_max,
        message=message,
    )