from rest_framework import viewsets, mixins, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models as db_models
from .models import Review
from .serializers import ReviewSerializer
from apps.orders.models import Order


class ReviewViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ReviewSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["product", "rating", "is_approved"]

    def get_permissions(self):
        if self.action == "destroy":
            return [permissions.IsAdminUser()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        qs = Review.objects.select_related("user").prefetch_related("images")
        if not (self.request.user and self.request.user.is_staff):
            qs = qs.filter(is_approved=True)
        return qs

    @action(detail=False, methods=["post"], url_path="verify-email")
    def verify_email(self, request):
        email = request.data.get("reviewer_email", "").strip()
        product_id = request.data.get("product", "").strip()

        if not email or not product_id:
            return Response(
                {"valid": False, "detail": "Email y producto son requeridos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        has_purchase = Order.objects.filter(
            status__in=["SHIPPED", "DELIVERED", "PARTIALLY_REFUNDED"],
            items__variant__product_id=product_id,
        ).filter(
            db_models.Q(user__email=email) | db_models.Q(guest_email=email)
        ).exists()

        if not has_purchase:
            return Response(
                {"valid": False, "detail": "No encontramos una compra con este email para este producto."},
                status=status.HTTP_200_OK,
            )

        already_reviewed = Review.objects.filter(
            product_id=product_id, reviewer_email=email
        ).exists()

        if already_reviewed:
            return Response(
                {"valid": False, "detail": "Ya enviaste una reseña para este producto."},
                status=status.HTTP_200_OK,
            )

        return Response({"valid": True}, status=status.HTTP_200_OK)