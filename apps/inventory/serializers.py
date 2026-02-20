from rest_framework import serializers
from .models import Stock


class StockSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(source="variant.sku", read_only=True)
    product_name = serializers.CharField(source="variant.product.name", read_only=True)
    available = serializers.IntegerField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Stock
        fields = [
            "id", "variant", "variant_sku", "product_name",
            "quantity", "reserved", "available",
            "is_out_of_stock", "is_low_stock", "low_stock_threshold",
        ]
        read_only_fields = ["reserved"]