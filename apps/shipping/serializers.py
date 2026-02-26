from rest_framework import serializers
from .models import ShippingRate


class ShippingRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingRate
        fields = [
            "id", "name", "city", "department", "price",
            "free_shipping_from", "estimated_days_min",
            "estimated_days_max", "is_default",
        ]


class ShippingCalculateSerializer(serializers.Serializer):
    """Input para calcular el costo de envío."""
    city = serializers.CharField(max_length=100)
    department = serializers.CharField(max_length=100)
    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
    )


class ShippingResultSerializer(serializers.Serializer):
    """Output del cálculo de envío."""
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_free = serializers.BooleanField()
    free_shipping_from = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True
    )
    estimated_days_min = serializers.IntegerField()
    estimated_days_max = serializers.IntegerField()
    estimated_delivery = serializers.CharField()
    message = serializers.CharField()