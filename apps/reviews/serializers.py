from rest_framework import serializers
from .models import Review, ReviewImage
from apps.orders.models import Order
from django.db import models

class ReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewImage
        fields = ["id", "image", "order"]


class ReviewSerializer(serializers.ModelSerializer):
    images = ReviewImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    reviewer_email = serializers.EmailField()

    class Meta:
        model = Review
        fields = [
            "id", "product", "rating", "title", "body",
            "is_verified_purchase", "is_approved",
            "images", "uploaded_images", "reviewer_email", "created_at",
        ]
        read_only_fields = ["is_verified_purchase", "is_approved"]
        validators = []  # desactiva el unique_together automático de DR


    def validate(self, attrs):
        email = attrs["reviewer_email"]
        product = attrs["product"]

        # Verificar que ya no existe una reseña con este email para este producto
        if Review.objects.filter(product=product, reviewer_email=email).exists():
            raise serializers.ValidationError(
                "Ya existe una reseña para este producto con este email."
            )

        # Verificar compra — busca en órdenes de usuario registrado o invitado
        verified = Order.objects.filter(
            status__in=["SHIPPED", "DELIVERED", "PARTIALLY_REFUNDED"],
            items__variant__product=product,
        ).filter(
            models.Q(user__email=email) | models.Q(guest_email=email)
        ).exists()

        if not verified:
            raise serializers.ValidationError(
                "No encontramos una compra con este email para este producto."
            )

        attrs["is_verified_purchase"] = True
        return attrs

    def create(self, validated_data):
        images_data = validated_data.pop("uploaded_images", [])
        # Asociar usuario si está autenticado
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["user"] = request.user
        review = Review.objects.create(**validated_data)
        for i, img in enumerate(images_data):
            ReviewImage.objects.create(review=review, image=img, order=i)
        return review