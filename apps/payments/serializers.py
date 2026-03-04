from rest_framework import serializers
from apps.orders.models import Order


class CheckoutItemSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    quantity   = serializers.IntegerField(min_value=1)


class CheckoutSerializer(serializers.Serializer):
    items                = CheckoutItemSerializer(many=True, min_length=1)
    shipping_name        = serializers.CharField(max_length=255)
    shipping_address     = serializers.CharField()
    shipping_city        = serializers.CharField(max_length=100)
    shipping_department  = serializers.CharField(max_length=100)
    shipping_phone       = serializers.CharField(max_length=20)
    shipping_postal_code = serializers.CharField(max_length=20, required=False, default="")
    coupon_code          = serializers.CharField(max_length=50, required=False, allow_blank=True)
    guest_email          = serializers.EmailField(required=False, allow_blank=True)
    guest_name           = serializers.CharField(max_length=255, required=False, allow_blank=True)
    notes                = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            if not attrs.get("guest_email"):
                raise serializers.ValidationError(
                    {"guest_email": "Requerido para compras como invitado."}
                )
            if not attrs.get("guest_name"):
                raise serializers.ValidationError(
                    {"guest_name": "Requerido para compras como invitado."}
                )
        return attrs


class CheckoutResponseSerializer(serializers.Serializer):
    order_id         = serializers.CharField()
    reference        = serializers.CharField()
    amount_in_cents  = serializers.IntegerField()
    currency         = serializers.CharField()
    public_key       = serializers.CharField()
    integrity_hash   = serializers.CharField()
    acceptance_token = serializers.CharField()
    subtotal         = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount_amount  = serializers.DecimalField(max_digits=12, decimal_places=2)
    iva_amount       = serializers.DecimalField(max_digits=12, decimal_places=2)   # ← nuevo
    shipping_amount  = serializers.DecimalField(max_digits=12, decimal_places=2)
    total            = serializers.DecimalField(max_digits=12, decimal_places=2)


class TransactionStatusSerializer(serializers.Serializer):
    order_id     = serializers.CharField()
    reference    = serializers.CharField()
    order_status = serializers.CharField()
    wompi_status = serializers.CharField(allow_null=True)
    total        = serializers.DecimalField(max_digits=12, decimal_places=2)