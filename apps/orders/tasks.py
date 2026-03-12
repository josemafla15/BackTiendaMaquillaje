from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)

RESERVATION_EXPIRY_MINUTES = 2


@shared_task(name="orders.release_expired_reservations")
def release_expired_reservations():
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
                logger.info("Reserva liberada — Order %s expiró tras %d minutos", order.wompi_reference, RESERVATION_EXPIRY_MINUTES)
        except Exception as e:
            logger.error("Error liberando reserva de Order %s: %s", order.wompi_reference, e)

    logger.info("release_expired_reservations: %d órdenes expiradas procesadas.", count)
    return f"{count} reservas liberadas"


# ─── Helpers email ────────────────────────────────────────────────────────────

def _get_name(order) -> str:
    return order.guest_name or order.guest_email

def _get_email(order) -> str:
    return order.user.email if order.user else order.guest_email

def _send(subject: str, template: str, context: dict, to: str) -> None:
    try:
        html = render_to_string(template, context)
        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
            html_message=html,
            fail_silently=False,
        )
        logger.info("Email '%s' enviado a %s", subject, to)
    except Exception as e:
        logger.error("Error enviando email '%s' a %s: %s", subject, to, e)


# ─── Tareas email ─────────────────────────────────────────────────────────────

@shared_task(name="orders.send_order_paid_email")
def send_order_paid_email(order_id: str) -> None:
    from apps.orders.models import Order
    try:
        order = Order.objects.prefetch_related('items').get(id=order_id)
        _send(
            subject="✅ Pago confirmado — Tienda Maquillaje",
            template="emails/order_paid.html",
            context={
                "name": _get_name(order),
                "reference": order.wompi_reference,
                "total": f"${order.total:,.0f} COP",
                "date": order.created_at.strftime("%d/%m/%Y %H:%M"),
                "items": order.items.all(),
            },
            to=_get_email(order),
        )
    except Exception as e:
        logger.error("send_order_paid_email error: %s", e)


@shared_task(name="orders.send_order_status_email")
def send_order_status_email(order_id: str, new_status: str) -> None:
    from apps.orders.models import Order
    TEMPLATE_MAP = {
        'PREPARING': ('emails/order_preparing.html', '🔧 Preparando tu pedido — Tienda Maquillaje'),
        'SHIPPED':   ('emails/order_shipped.html',   '🚚 Tu pedido fue enviado — Tienda Maquillaje'),
        'DELIVERED': ('emails/order_delivered.html', '📦 Pedido entregado — Tienda Maquillaje'),
        'CANCELLED': ('emails/order_cancelled.html', '❌ Pedido cancelado — Tienda Maquillaje'),
    }
    if new_status not in TEMPLATE_MAP:
        return
    template, subject = TEMPLATE_MAP[new_status]
    try:
        order = Order.objects.get(id=order_id)
        _send(
            subject=subject,
            template=template,
            context={
                "name": _get_name(order),
                "reference": order.wompi_reference,
                "total": f"${order.total:,.0f} COP",
                "address": order.shipping_address,
                "city": order.shipping_city,
            },
            to=_get_email(order),
        )
    except Exception as e:
        logger.error("send_order_status_email error: %s", e)


@shared_task(name="orders.send_refund_email")
def send_refund_email(order_id: str, refund_amount: str, reason: str, is_partial: bool) -> None:
    from apps.orders.models import Order
    try:
        order = Order.objects.get(id=order_id)
        subject = "💰 Reembolso parcial aprobado" if is_partial else "💰 Reembolso aprobado"
        _send(
            subject=f"{subject} — Tienda Maquillaje",
            template="emails/order_refunded.html",
            context={
                "name": _get_name(order),
                "reference": order.wompi_reference,
                "refund_amount": f"${float(refund_amount):,.0f} COP",
                "reason": reason,
                "is_partial": is_partial,
            },
            to=_get_email(order),
        )
    except Exception as e:
        logger.error("send_refund_email error: %s", e)