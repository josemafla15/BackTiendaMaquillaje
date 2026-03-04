from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status

from apps.catalog.models import Variant
from apps.orders.models import Order, OrderItem
from apps.promotions.models import Coupon
from apps.shipping.services import calculate_shipping

from .serializers import (
    CheckoutSerializer,
    CheckoutResponseSerializer,
    TransactionStatusSerializer,
)
from .wompi import WompiService

logger = logging.getLogger(__name__)

IVA_RATE = Decimal("0.19")


class CheckoutView(APIView):
    """
    POST /api/payments/checkout/

    Crea el pedido y retorna los datos para inicializar el Widget Wompi.
    Funciona para usuarios autenticados e invitados.

    Total = subtotal - descuento + IVA(19% sobre subtotal con descuento) + envío
    """
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = CheckoutSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # ── 1. Validar items y calcular subtotal ───────────────────────────
        items_data = []
        subtotal = Decimal("0")

        for item in data["items"]:
            try:
                variant = Variant.objects.select_related(
                    "product", "stock"
                ).get(id=item["variant_id"], is_active=True)
            except Variant.DoesNotExist:
                return Response(
                    {"detail": f"Variante {item['variant_id']} no encontrada."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if variant.stock.available < item["quantity"]:
                return Response(
                    {
                        "detail": f"Stock insuficiente para '{variant.product.name} - {variant.name}'. "
                                  f"Disponible: {variant.stock.available}."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            line_subtotal = Decimal(str(variant.effective_price)) * item["quantity"]
            subtotal += line_subtotal
            items_data.append({
                "variant": variant,
                "quantity": item["quantity"],
                "unit_price": Decimal(str(variant.effective_price)),
                "subtotal": line_subtotal,
            })

        # ── 2. Calcular envío ──────────────────────────────────────────────
        shipping_result = calculate_shipping(
            city=data["shipping_city"],
            department=data["shipping_department"],
            subtotal=subtotal,
        )
        shipping_amount = shipping_result.price

        # ── 3. Aplicar cupón ───────────────────────────────────────────────
        discount_amount = Decimal("0")
        coupon = None

        coupon_code = data.get("coupon_code", "").strip()
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code)
                if not coupon.is_valid:
                    return Response(
                        {"detail": "El cupón no es válido o ha expirado."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if subtotal < coupon.minimum_order_amount:
                    return Response(
                        {
                            "detail": f"El cupón requiere un monto mínimo de "
                                      f"${coupon.minimum_order_amount:,.0f} COP."
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                discount_amount = coupon.calculate_discount(subtotal)
            except Coupon.DoesNotExist:
                return Response(
                    {"detail": "Cupón no encontrado."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ── 4. Calcular IVA (19% sobre subtotal neto después de descuento) ─
        subtotal_neto = subtotal - discount_amount
        iva_amount = (subtotal_neto * IVA_RATE).quantize(Decimal("0.01"))

        # ── 5. Total final ─────────────────────────────────────────────────
        total = subtotal_neto + iva_amount + shipping_amount
        amount_in_cents = int(total * 100)

        # ── 6. Crear Order ─────────────────────────────────────────────────
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            guest_email=data.get("guest_email", "") or (request.user.email if request.user.is_authenticated else ""),
            guest_name=data.get("guest_name", "") or (f"{request.user.first_name} {request.user.last_name}".strip() if request.user.is_authenticated else ""),
            subtotal=subtotal,
            discount_amount=discount_amount,
            shipping_amount=shipping_amount,
            total=total,
            coupon=coupon,
            shipping_name=data["shipping_name"],
            shipping_address=data["shipping_address"],
            shipping_city=data["shipping_city"],
            shipping_department=data["shipping_department"],
            shipping_phone=data["shipping_phone"],
            shipping_postal_code=data.get("shipping_postal_code", ""),
            notes=data.get("notes", ""),
            status=Order.Status.PENDING_PAYMENT,
        )

        # ── 7. Crear OrderItems y reservar stock ───────────────────────────
        for item in items_data:
            variant = item["variant"]
            OrderItem.objects.create(
                order=order,
                variant=variant,
                product_name=variant.product.name,
                variant_name=variant.name,
                sku=variant.sku,
                unit_price=item["unit_price"],
                quantity=item["quantity"],
                subtotal=item["subtotal"],
            )
            variant.stock.reserve(item["quantity"])

        # ── 8. Incrementar uso del cupón ───────────────────────────────────
        if coupon:
            Coupon.objects.filter(pk=coupon.pk).update(
                used_count=coupon.used_count + 1
            )

        # ── 9. Generar datos para Widget Wompi ─────────────────────────────
        wompi = WompiService()
        integrity_hash = wompi.generate_integrity_hash(
            reference=order.wompi_reference,
            amount_in_cents=amount_in_cents,
        )
        acceptance_token = wompi.get_acceptance_token()

        response_data = {
            "order_id":        order.id,
            "reference":       order.wompi_reference,
            "amount_in_cents": amount_in_cents,
            "currency":        "COP",
            "public_key":      settings.WOMPI_PUBLIC_KEY,
            "integrity_hash":  integrity_hash,
            "acceptance_token": acceptance_token,
            "subtotal":        subtotal,
            "discount_amount": discount_amount,
            "iva_amount":      iva_amount,
            "shipping_amount": shipping_amount,
            "total":           total,
        }

        return Response(
            CheckoutResponseSerializer(response_data).data,
            status=status.HTTP_201_CREATED,
        )


class WompiWebhookView(APIView):
    """
    POST /api/payments/webhook/
    """
    permission_classes = [AllowAny]

    def post(self, request):
        wompi = WompiService()
        payload = request.data

        event     = payload.get("event")
        data      = payload.get("data", {})
        signature = payload.get("signature", {})

        if not all([event, data, signature]):
            return Response({"detail": "Payload inválido."}, status=status.HTTP_400_BAD_REQUEST)

        properties = signature.get("properties", {})
        checksum   = signature.get("checksum", "")
        timestamp  = str(payload.get("timestamp", ""))

        props_values     = {}
        transaction_data = data.get("transaction", {})
        for prop in properties:
            # prop es "transaction.id" → clave real es "id"
            key = prop.split(".")[-1]
            props_values[prop] = transaction_data.get(key, "")

        if not wompi.validate_webhook_signature(props_values, checksum, timestamp):
            logger.warning("Firma de webhook inválida. Payload: %s", payload)
            return Response({"detail": "Firma inválida."}, status=status.HTTP_401_UNAUTHORIZED)

        if event == "transaction.updated":
            self._handle_transaction_updated(transaction_data)

        return Response({"status": "ok"}, status=status.HTTP_200_OK)

    def _handle_transaction_updated(self, transaction_data: dict) -> None:
        reference      = transaction_data.get("reference")
        wompi_status   = transaction_data.get("status")
        transaction_id = transaction_data.get("id")

        if not reference:
            return

        try:
            order = Order.objects.get(wompi_reference=reference)
        except Order.DoesNotExist:
            logger.error("Webhook: Order con referencia '%s' no encontrada.", reference)
            return

        if transaction_id and not order.wompi_transaction_id:
            order.wompi_transaction_id = transaction_id

        STATUS_MAP = {
            "APPROVED": Order.Status.PAID,
            "DECLINED": Order.Status.CANCELLED,
            "VOIDED":   Order.Status.CANCELLED,
            "ERROR":    Order.Status.CANCELLED,
            "PENDING":  Order.Status.PAYMENT_PROCESSING,
        }

        new_status = STATUS_MAP.get(wompi_status)
        if new_status and order.status != new_status:
            if new_status == Order.Status.PAID:
                for item in order.items.select_related("variant__stock").all():
                    item.variant.stock.confirm_sale(item.quantity)
            elif new_status == Order.Status.CANCELLED:
                for item in order.items.select_related("variant__stock").all():
                    item.variant.stock.release_reservation(item.quantity)

            order.status = new_status
            order.save(update_fields=["status", "wompi_transaction_id", "updated_at"])
            logger.info("Order %s → %s (Wompi: %s)", order.wompi_reference, new_status, wompi_status)


class TransactionStatusView(APIView):
    """
    GET /api/payments/transaction/{reference}/
    """
    permission_classes = [AllowAny]

    def get(self, request, reference):
        wompi = WompiService()
        try:
            order = Order.objects.get(wompi_reference=reference)
        except Order.DoesNotExist:
            return Response({"detail": "Pedido no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        wompi_status = None
        if order.wompi_transaction_id:
            transaction = wompi.get_transaction(order.wompi_transaction_id)
            if transaction:
                wompi_status = transaction.get("status")

        response_data = {
            "order_id":     order.id,
            "reference":    order.wompi_reference,
            "order_status": order.status,
            "wompi_status": wompi_status,
            "total":        order.total,
        }

        return Response(TransactionStatusSerializer(response_data).data, status=status.HTTP_200_OK)