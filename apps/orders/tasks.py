from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)

# Tiempo máximo que una orden puede estar en PENDING_PAYMENT (minutos)
RESERVATION_EXPIRY_MINUTES = 2


@shared_task(name="orders.release_expired_reservations")
def release_expired_reservations():
    """
    Libera reservas de stock de órdenes que llevan más de
    RESERVATION_EXPIRY_MINUTES minutos en estado PENDING_PAYMENT.

    Se ejecuta periódicamente via Celery Beat.
    """
    from apps.orders.models import Order

    expiry_threshold = timezone.now() - timedelta(minutes=RESERVATION_EXPIRY_MINUTES)

    expired_orders = Order.objects.filter(
        status=Order.Status.PENDING_PAYMENT,
        created_at__lte=expiry_threshold,
    ).prefetch_related("items__variant__stock")

    count = 0
    for order in expired_orders:
        try:
            with transaction.atomic():
                for item in order.items.all():
                    item.variant.stock.release_reservation(item.quantity)
                order.status = Order.Status.CANCELLED
                order.save(update_fields=["status", "updated_at"])
                count += 1
                logger.info(
                    "Reserva liberada — Order %s expiró tras %d minutos",
                    order.wompi_reference,
                    RESERVATION_EXPIRY_MINUTES,
                )
        except Exception as e:
            logger.error(
                "Error liberando reserva de Order %s: %s",
                order.wompi_reference, e
            )

    logger.info("release_expired_reservations: %d órdenes expiradas procesadas.", count)
    return f"{count} reservas liberadas"