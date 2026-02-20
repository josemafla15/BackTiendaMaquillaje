from rest_framework import viewsets, mixins
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Order, Refund
from .serializers import OrderSerializer, RefundSerializer


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        # Cada usuario solo ve sus propios pedidos
        return Order.objects.filter(
            user=self.request.user
        ).prefetch_related("items__variant").order_by("-created_at")

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def cancel(self, request, pk=None):
        order = self.get_object()
        order.cancel()
        return Response({"status": "cancelado"})


class RefundViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAdminUser]
    serializer_class = RefundSerializer
    queryset = Refund.objects.select_related("order").all()

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        refund = self.get_object()
        refund.approve()
        return Response({"status": "aprobado"})