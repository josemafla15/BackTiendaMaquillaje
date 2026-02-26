from django.contrib import admin
from apps.inventory.models import Stock
from django.utils.html import format_html

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = [
        "variant_sku", "product_name", "quantity",
        "reserved", "available_display", "stock_status"
    ]
    list_filter = ["variant__product__brand"]
    search_fields = ["variant__sku", "variant__product__name"]
    readonly_fields = ["reserved"]
    ordering = ["quantity"]

    def variant_sku(self, obj):
        return obj.variant.sku
    variant_sku.short_description = "SKU"

    def product_name(self, obj):
        return obj.variant.product.name
    product_name.short_description = "Producto"

    def available_display(self, obj):
        return obj.available
    available_display.short_description = "Disponible"

    def stock_status(self, obj):
        if obj.is_out_of_stock:
            return format_html(
                '<span style="color:#ef4444;font-weight:bold">{}</span>',
                '● Agotado'
            )
        if obj.is_low_stock:
            return format_html(
                '<span style="color:#f59e0b;font-weight:bold">{}</span>',
                '● Stock bajo'
            )
        return format_html(
            '<span style="color:#22c55e">{}</span>',
            '● OK'
        )
    stock_status.short_description = "Estado"