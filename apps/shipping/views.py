from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework import status

from .models import ShippingRate
from .serializers import (
    ShippingCalculateSerializer,
    ShippingResultSerializer,
    ShippingRateSerializer,
)
from .services import calculate_shipping


class ShippingCalculateView(APIView):
    """
    POST /api/shipping/calculate/

    Calcula el costo de envío para una ciudad/departamento y subtotal.
    Público — no requiere autenticación (se usa antes del checkout).

    Body:
        {
            "city": "Bogotá",
            "department": "Cundinamarca",
            "subtotal": 150000
        }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        input_serializer = ShippingCalculateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        result = calculate_shipping(
            city=input_serializer.validated_data["city"],
            department=input_serializer.validated_data["department"],
            subtotal=input_serializer.validated_data["subtotal"],
        )

        output_serializer = ShippingResultSerializer(result)
        return Response(output_serializer.data, status=status.HTTP_200_OK)


class ShippingRateViewSet(ModelViewSet):
    """
    CRUD de tarifas de envío — solo admin.

    GET    /api/shipping/rates/
    POST   /api/shipping/rates/
    PATCH  /api/shipping/rates/{id}/
    DELETE /api/shipping/rates/{id}/
    """
    permission_classes = [IsAdminUser]
    serializer_class = ShippingRateSerializer
    queryset = ShippingRate.objects.filter(is_active=True).order_by("department", "city")