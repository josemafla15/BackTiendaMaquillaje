from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from .models import Coupon
from .serializers import CouponSerializer


class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        return [IsAuthenticatedOrReadOnly()]

    @action(detail=False, methods=["post"], url_path="validate")
    def validate_coupon(self, request):
        """Valida un cupón antes de aplicarlo al carrito."""
        code = request.data.get("code")
        try:
            coupon = Coupon.objects.get(code=code)
            if not coupon.is_valid:
                return Response(
                    {"valid": False, "message": "Cupón inválido o expirado."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response({
                "valid": True,
                "discount_type": coupon.discount_type,
                "discount_value": str(coupon.discount_value),
            })
        except Coupon.DoesNotExist:
            return Response(
                {"valid": False, "message": "Cupón no encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )