from __future__ import annotations

from typing import Any
from rest_framework import serializers

from .models import (
    Brand, Category, Product, Variant,
    ProductImage, VariantAttribute, AttributeType, ProductCategory
)
from apps.inventory.models import Stock


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "slug", "logo", "description", "is_active"]


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "parent", "image", "is_active", "children"]

    def get_children(self, obj: Category) -> list[dict]:
        return CategorySerializer(
            obj.children.filter(is_active=True), many=True
        ).data


# ── Inventory ──────────────────────────────────────────────────────────────

class StockSerializer(serializers.ModelSerializer):
    available = serializers.IntegerField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Stock
        fields = ["quantity", "reserved", "available", "is_out_of_stock", "is_low_stock"]


# ── Variants ───────────────────────────────────────────────────────────────

class VariantAttributeSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source="attribute_type.name", read_only=True)

    class Meta:
        model = VariantAttribute
        fields = ["attribute_name", "value"]


class VariantWriteSerializer(serializers.ModelSerializer):
    """Para crear/actualizar variantes. Acepta quantity para el Stock."""
    quantity = serializers.IntegerField(write_only=True, required=False, default=0)

    class Meta:
        model = Variant
        fields = [
            "id", "sku", "name", "price", "sale_price",
            "color_code", "swatch_image", "image",
            "weight_grams", "is_active", "quantity",
        ]

    def create(self, validated_data: dict[str, Any]) -> Variant:
        quantity = validated_data.pop("quantity", 0)
        variant = super().create(validated_data)
        Stock.objects.create(variant=variant, quantity=quantity)
        return variant

    def update(self, instance: Variant, validated_data: dict[str, Any]) -> Variant:
        quantity = validated_data.pop("quantity", None)
        variant = super().update(instance, validated_data)
        if quantity is not None:
            stock, _ = Stock.objects.get_or_create(variant=variant)
            stock.quantity = quantity
            stock.save(update_fields=["quantity"])
        return variant


class VariantReadSerializer(serializers.ModelSerializer):
    stock = StockSerializer(read_only=True)
    attribute_values = VariantAttributeSerializer(many=True, read_only=True)
    effective_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = Variant
        fields = [
            "id", "sku", "name", "price", "sale_price", "effective_price",
            "color_code", "swatch_image", "image",
            "weight_grams", "is_active", "stock", "attribute_values",
        ]


# ── Products ───────────────────────────────────────────────────────────────

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "alt_text", "order"]


class ProductListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listados y búsqueda."""
    brand_name = serializers.CharField(source="brand.name", read_only=True)
    base_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    variant_count = serializers.IntegerField(
        source="variants.count", read_only=True
    )

    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "brand_name", "cover_image",
            "short_description", "base_price", "variant_count",
            "is_active", "is_featured",
        ]


class ProductDetailSerializer(serializers.ModelSerializer):
    """Serializer completo para el detalle del producto."""
    brand = BrandSerializer(read_only=True)
    variants = VariantReadSerializer(many=True, read_only=True)
    gallery = ProductImageSerializer(many=True, read_only=True)
    categories = CategorySerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "brand", "categories",
            "description", "short_description", "cover_image",
            "gallery", "variants", "is_active", "is_featured",
            "meta_title", "meta_description",
        ]


class ProductWriteSerializer(serializers.ModelSerializer):
    """
    Permite crear un Producto con sus Variantes en una sola operación.
    Payload esperado:
    {
      "name": "Labial Matte Velvet",
      "brand": "<uuid>",
      "category_ids": ["<uuid1>", "<uuid2>"],
      "variants": [
        {"sku": "LMV-001-MOR", "name": "Morado", "price": 35000,
         "color_code": "#6A0DAD", "quantity": 50},
        {"sku": "LMV-001-ROS", "name": "Rosado", "price": 35000,
         "color_code": "#FF69B4", "quantity": 30}
      ],
      ...
    }
    """
    variants = VariantWriteSerializer(many=True, required=False)
    category_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False
    )

    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "brand", "description", "short_description",
            "cover_image", "is_active", "is_featured",
            "meta_title", "meta_description",
            "variants", "category_ids",
        ]

    def create(self, validated_data: dict[str, Any]) -> Product:
        variants_data = validated_data.pop("variants", [])
        category_ids = validated_data.pop("category_ids", [])

        product = Product.objects.create(**validated_data)

        for idx, cat_id in enumerate(category_ids):
            ProductCategory.objects.create(
                product=product, category_id=cat_id, order=idx
            )

        for variant_data in variants_data:
            variant_serializer = VariantWriteSerializer(data={
                **variant_data, "product": product.id
            })
            # Usar el serializer interno para que gestione el Stock
            quantity = variant_data.pop("quantity", 0)
            variant = Variant.objects.create(product=product, **variant_data)
            Stock.objects.create(variant=variant, quantity=quantity)

        return product

    def update(self, instance: Product, validated_data: dict[str, Any]) -> Product:
        validated_data.pop("variants", None)  # Variantes se actualizan por endpoint propio
        category_ids = validated_data.pop("category_ids", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if category_ids is not None:
            ProductCategory.objects.filter(product=instance).delete()
            for idx, cat_id in enumerate(category_ids):
                ProductCategory.objects.create(
                    product=instance, category_id=cat_id, order=idx
                )

        return instance