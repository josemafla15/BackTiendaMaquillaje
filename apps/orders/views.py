from rest_framework import viewsets, mixins, filters
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend

from .models import Order, Refund
from .serializers import OrderSerializer, RefundSerializer, OrderStatusSerializer


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["guest_email", "guest_name", "shipping_name", "wompi_reference"]
    ordering_fields = ["created_at", "total"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in ["list_all", "update_status", "cancel"]:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        # Admin ve todos los pedidos
        if user.is_staff:
            return Order.objects.prefetch_related(
                "items__variant__product"
            ).order_by("-created_at")
        # Usuario normal solo ve los suyos
        return Order.objects.filter(
            user=user
        ).prefetch_related("items__variant").order_by("-created_at")

    @action(detail=True, methods=["patch"], url_path="status", permission_classes=[IsAdminUser])
    def update_status(self, request, pk=None):
        """
        PATCH /api/orders/{id}/status/
        Body: { "status": "SHIPPED" }
        """
        order = self.get_object()
        serializer = OrderStatusSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def cancel(self, request, pk=None):
        order = self.get_object()
        try:
            order.cancel()
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
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
        try:
            refund.approve()
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": "aprobado"})