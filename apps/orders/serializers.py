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
            "guest_email", "guest_name",
            "shipping_name", "shipping_address", "shipping_city",
            "shipping_department", "shipping_phone",
            "wompi_transaction_id", "wompi_reference", "created_at",
        ]
        read_only_fields = ["status", "subtotal", "total"]


class OrderStatusSerializer(serializers.ModelSerializer):
    """Solo para cambiar el estado del pedido."""
    class Meta:
        model = Order
        fields = ["id", "status"]

    def validate_status(self, value):
        valid_statuses = [s.value for s in Order.Status]
        if value not in valid_statuses:
            raise serializers.ValidationError(
                f"Estado inválido. Opciones: {valid_statuses}"
            )
        return value


class RefundItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundItem
        fields = ["id", "order_item", "quantity", "reason"]




class RefundItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundItem
        fields = ["order_item", "quantity", "reason"]

    def validate(self, attrs):
        order_item = attrs["order_item"]
        quantity = attrs["quantity"]
        if quantity > order_item.refundable_quantity:
            raise serializers.ValidationError(
                f"Cantidad ({quantity}) supera la disponible ({order_item.refundable_quantity})."
            )
        return attrs


class RefundSerializer(serializers.ModelSerializer):
    items = RefundItemSerializer(many=True, read_only=True)
    items_write = RefundItemWriteSerializer(many=True, write_only=True, source="items")

    class Meta:
        model = Refund
        fields = [
            "id", "order", "status", "reason",
            "amount", "items", "items_write", "processed_at",
        ]
        read_only_fields = ["status", "processed_at"]

    def validate(self, attrs):
        order = attrs.get("order")
        allowed = [Order.Status.DELIVERED, Order.Status.PARTIALLY_REFUNDED]
        if order.status not in allowed:
            raise serializers.ValidationError(
                f"Solo se pueden crear reembolsos para órdenes entregadas. "
                f"Estado actual: {order.status}"
            )
        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        refund = Refund.objects.create(**validated_data)
        for item_data in items_data:
            RefundItem.objects.create(refund=refund, **item_data)
        return refund