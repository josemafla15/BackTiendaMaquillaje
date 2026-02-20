from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAdminUser

from .models import Stock
from .serializers import StockSerializer


class StockViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Gestión de stock. Solo Admin puede modificarlo.
    GET  /api/inventory/stock/          → Lista todo el stock
    GET  /api/inventory/stock/{id}/     → Stock de una variante
    PATCH /api/inventory/stock/{id}/    → Ajustar stock manualmente
    """
    queryset = Stock.objects.select_related("variant__product").all()
    serializer_class = StockSerializer
    permission_classes = [IsAdminUser]