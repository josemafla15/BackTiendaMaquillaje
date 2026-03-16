from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly, AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from decimal import Decimal
from .models import Coupon
from .serializers import CouponSerializer


class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        return [AllowAny()]  # validate_coupon debe ser público para invitados

    @action(detail=False, methods=["post"], url_path="validate")
    def validate_coupon(self, request):
        """
        Valida un cupón y calcula el descuento real según el subtotal.
        Body: { "code": "VERANO20", "subtotal": "150000" }
        """
        code = request.data.get("code", "").strip().upper()
        subtotal_raw = request.data.get("subtotal", "0")

        if not code:
            return Response(
                {"valid": False, "message": "Ingresa un código de cupón."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            subtotal = Decimal(str(subtotal_raw))
        except Exception:
            return Response(
                {"valid": False, "message": "Subtotal inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            coupon = Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            return Response(
                {"valid": False, "message": "Cupón no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not coupon.is_valid:
            return Response(
                {"valid": False, "message": "Cupón inválido o expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if subtotal < coupon.minimum_order_amount:
            return Response(
                {
                    "valid": False,
                    "message": (
                        f"El cupón requiere un pedido mínimo de "
                        f"${coupon.minimum_order_amount:,.0f}."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        discount = coupon.calculate_discount(subtotal)

        return Response({
            "valid": True,
            "code": coupon.code,
            "discount_type": coupon.discount_type,
            "discount_value": str(coupon.discount_value),
            "discount_amount": str(discount),
            "message": coupon.description or f"Descuento de ${discount:,.0f} aplicado.",
        })