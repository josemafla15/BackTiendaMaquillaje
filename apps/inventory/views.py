from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAdminUser
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Stock
from .serializers import StockSerializer


class StockViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    GET  /api/inventory/stock/              → Lista todo el stock
    GET  /api/inventory/stock/{id}/         → Stock de una variante
    PATCH /api/inventory/stock/{id}/        → Ajustar stock manualmente
    GET  /api/inventory/stock/low-stock/    → Variantes con stock bajo
    """
    queryset = Stock.objects.select_related(
        "variant__product"
    ).order_by("quantity")
    serializer_class = StockSerializer
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=["get"], url_path="low-stock")
    def low_stock(self, request):
        """
        Retorna variantes cuyo stock disponible está por debajo
        del low_stock_threshold o agotadas.
        """
        qs = self.get_queryset()
        # Filtramos en Python usando las properties del modelo
        low = [s for s in qs if s.is_low_stock or s.is_out_of_stock]
        serializer = self.get_serializer(low, many=True)
        return Response({
            "count": len(low),
            "results": serializer.data
        })