from rest_framework import serializers
from .models import Coupon


class CouponSerializer(serializers.ModelSerializer):
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = Coupon
        fields = [
            "id", "code", "description", "discount_type", "discount_value",
            "max_discount_amount", "minimum_order_amount", "max_uses",
            "used_count", "valid_from", "valid_until", "is_active", "is_valid",
        ]
        read_only_fields = ["used_count"]