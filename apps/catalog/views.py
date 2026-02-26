from __future__ import annotations

from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Product, Variant, Brand, Category
from .serializers import (
    ProductListSerializer, ProductDetailSerializer, ProductWriteSerializer,
    VariantReadSerializer, VariantWriteSerializer,
    BrandSerializer, CategorySerializer,
)
from .filters import ProductFilter
from apps.inventory.models import Stock


class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.filter(is_active=True)
    serializer_class = BrandSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = "slug"

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        return [AllowAny()]


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True, parent=None)
    serializer_class = CategorySerializer
    lookup_field = "slug"

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        return [AllowAny()]


class ProductViewSet(viewsets.ModelViewSet):
    """
    CRUD de Productos con soporte de variantes embebidas en creación.

    GET    /api/products/          → Lista paginada (ProductListSerializer)
    GET    /api/products/{slug}/   → Detalle completo (ProductDetailSerializer)
    POST   /api/products/          → Crear producto + variantes (Admin)
    PATCH  /api/products/{slug}/   → Actualizar producto (Admin)
    DELETE /api/products/{slug}/   → Eliminar (Admin)

    POST /api/products/{slug}/add_variant/   → Agregar variante suelta
    GET  /api/products/{slug}/check_stock/   → Verificar stock de variantes
    """

    queryset = (
        Product.objects.filter(is_active=True)
        .select_related("brand")
        .prefetch_related(
            "variants__stock",
            "variants__attribute_values__attribute_type",
            "gallery",
            "categories",
        )
        .distinct()  # ← agregar esta línea
)
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ["name", "description", "brand__name", "variants__sku"]
    ordering_fields = ["name", "created_at", "variants__price"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        if self.action in ["create", "update", "partial_update"]:
            return ProductWriteSerializer
        return ProductDetailSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy", "add_variant"]:
            return [IsAdminUser()]
        return [AllowAny()]


    @action(detail=True, methods=["post"], url_path="add-variant")
    def add_variant(self, request, slug: str | None = None):
        """Agrega una variante a un producto existente."""
        product = self.get_object()
        data = request.data.copy()
        data["product"] = product.id
        serializer = VariantWriteSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        variant = serializer.save(product=product)
        return Response(
            VariantReadSerializer(variant).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="check-stock")
    def check_stock(self, request, slug: str | None = None):
        """
        Verifica stock disponible de todas las variantes.
        Útil para el frontend antes de mostrar el carrito.
        """
        product = self.get_object()
        variants = product.variants.filter(is_active=True).select_related("stock")
        data = [
            {
                "variant_id": str(v.id),
                "sku": v.sku,
                "available": v.stock.available if hasattr(v, "stock") else 0,
                "is_out_of_stock": v.stock.is_out_of_stock if hasattr(v, "stock") else True,
            }
            for v in variants
        ]
        return Response(data)

    @action(detail=True, methods=["patch"], url_path="upload-image")
    def upload_image(self, request, slug: str | None = None):
        """Sube o reemplaza la imagen principal del producto."""
        product = self.get_object()
        image = request.FILES.get("cover_image")
        if not image:
            return Response(
                {"error": "No se proporcionó ninguna imagen."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        product.cover_image = image
        product.save(update_fields=["cover_image"])
        return Response({"cover_image": product.cover_image.url})


class VariantViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Endpoint para gestionar variantes individuales.
    La creación se hace desde /products/{slug}/add-variant/
    """
    queryset = Variant.objects.select_related("stock", "product")

    def get_serializer_class(self):
        if self.action in ["update", "partial_update"]:
            return VariantWriteSerializer
        return VariantReadSerializer

    def get_permissions(self):
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        return [IsAuthenticatedOrReadOnly()]