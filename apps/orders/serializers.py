from rest_framework import serializers
from .models import Order, OrderItem, Refund, RefundItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id", "variant", "product_name", "variant_name",
            "sku", "unit_price", "quantity", "subtotal", "refunded_quantity",
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id", "status", "subtotal", "discount_amount",
            "shipping_amount", "total", "items",
            "shipping_name", "shipping_address", "shipping_city",
            "shipping_department", "shipping_phone",
            "wompi_transaction_id", "created_at",
        ]
        read_only_fields = ["status", "subtotal", "total"]


class RefundItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundItem
        fields = ["id", "order_item", "quantity", "reason"]


class RefundSerializer(serializers.ModelSerializer):
    items = RefundItemSerializer(many=True, read_only=True)

    class Meta:
        model = Refund
        fields = [
            "id", "order", "status", "reason",
            "amount", "items", "processed_at",
        ]
        read_only_fields = ["status", "processed_at"]