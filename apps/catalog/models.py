from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models
from cloudinary.models import CloudinaryField

from common.models import TimeStampedModel

from decimal import Decimal


class Brand(TimeStampedModel):
    """Marca del producto (e.g. MAC, NYX, Maybelline)."""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    logo = CloudinaryField("brands/logos", blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "catalog_brands"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Category(TimeStampedModel):
    """
    Categoría con soporte jerárquico (parent → child).
    Ejemplo: Labios > Labiales > Mate
    """
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    image = CloudinaryField("categories", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "catalog_categories"
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class Product(TimeStampedModel):
    """
    Producto base (e.g. 'Labial Matte Velvet').
    El precio, stock y SKU se manejan a nivel de Variant.
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True)
    brand = models.ForeignKey(
        Brand, on_delete=models.PROTECT, related_name="products"
    )
    categories = models.ManyToManyField(
        Category,
        through="ProductCategory",
        related_name="products",
        blank=True,
    )
    description = models.TextField()
    short_description = models.CharField(max_length=500, blank=True)
    cover_image = CloudinaryField("products/covers", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = "catalog_products"

    def __str__(self) -> str:
        return self.name

    @property
    def base_price(self) -> Decimal | None:
        """Retorna el precio de la primera variante activa."""
        variant = self.variants.filter(is_active=True).order_by("price").first()
        return variant.price if variant else None


class ProductCategory(models.Model):
    """
    Tabla intermedia explícita para la relación M2M Producto-Categoría.
    Permite categorización múltiple.
    Ejemplo: 'Labial X' → ['Labios', 'Mate', 'Oferta']
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "catalog_product_categories"
        unique_together = ("product", "category")
        ordering = ["order"]


class AttributeType(TimeStampedModel):
    """
    Tipo de atributo (e.g. 'Tono', 'Tamaño', 'Acabado').
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    class Meta:
        db_table = "catalog_attribute_types"

    def __str__(self) -> str:
        return self.name


class Variant(TimeStampedModel):
    """
    Variante de producto. Aquí vive el inventario real.

    Ejemplo:
      Product: "Labial Matte Velvet"
      Variant 1: SKU=LMV-001-MOR, tono=Morado, price=35000
      Variant 2: SKU=LMV-001-ROS, tono=Rosado, price=35000

    Cada variante se puede agotar independientemente.
    """

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="variants"
    )
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=255, help_text="e.g. 'Tono Morado 3.5g'")

    # Precio y descuento directo al producto
    price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    sale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Precio de oferta. Si tiene valor, prevalece sobre 'price'.",
    )

    # Visual del tono — CRÍTICO para el selector de colores en Angular
    color_code = models.CharField(
        max_length=7,
        blank=True,
        help_text="Hex color e.g. #C2185B",
    )
    swatch_image = CloudinaryField(
        "products/swatches",
        blank=True,
        null=True,
        help_text="Thumbnail del tono (50x50px) para el selector visual.",
    )
    image = CloudinaryField(
        "products/variants",
        blank=True,
        null=True,
        help_text="Foto principal de esta variante específica.",
    )

    # Atributos dinámicos de la variante (tono, acabado, tamaño, etc.)
    attributes = models.ManyToManyField(
        AttributeType,
        through="VariantAttribute",
        blank=True,
    )

    weight_grams = models.PositiveIntegerField(
        default=0, help_text="Peso en gramos para cálculo de envío."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "catalog_variants"

    def __str__(self) -> str:
        return f"{self.product.name} — {self.name} ({self.sku})"

    @property
    def effective_price(self) -> Decimal:
        """Precio final considerando oferta."""
        return self.sale_price if self.sale_price is not None else self.price


class VariantAttribute(models.Model):
    """
    Valor de un atributo para una variante específica.
    Ejemplo: variant=Labial Morado, attribute_type=Tono, value='Orchid 104'
    """
    variant = models.ForeignKey(
        Variant, on_delete=models.CASCADE, related_name="attribute_values"
    )
    attribute_type = models.ForeignKey(AttributeType, on_delete=models.PROTECT)
    value = models.CharField(max_length=255)

    class Meta:
        db_table = "catalog_variant_attributes"
        unique_together = ("variant", "attribute_type")


class ProductImage(TimeStampedModel):
    """Galería de imágenes del producto base."""
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="gallery"
    )
    image = CloudinaryField("products/gallery")
    alt_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "catalog_product_images"
        ordering = ["order"]