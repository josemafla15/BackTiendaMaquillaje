from django.contrib import admin
from apps.promotions.models import Coupon
from django.utils.html import format_html

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        "code", "discount_type", "discount_value",
        "used_count", "max_uses", "is_active", "valid_until", "validity_badge"
    ]
    list_filter = ["discount_type", "is_active"]
    search_fields = ["code", "description"]
    readonly_fields = ["used_count"]
    ordering = ["-created_at"]

    fieldsets = (
        ("Código", {
            "fields": ("code", "description", "is_active")
        }),
        ("Descuento", {
            "fields": ("discount_type", "discount_value", "max_discount_amount", "minimum_order_amount")
        }),
        ("Vigencia", {
            "fields": ("valid_from", "valid_until")
        }),
        ("Uso", {
            "fields": ("max_uses", "used_count")
        }),
        ("Restricciones", {
            "fields": ("applicable_products", "applicable_categories"),
            "classes": ("collapse",)
        }),
    )

    def validity_badge(self, obj):
        if obj.is_valid:
            return format_html(
                '<span style="color:#22c55e;font-weight:bold">{}</span>',
                '✓ Válido'
            )
        return format_html(
            '<span style="color:#ef4444;font-weight:bold">{}</span>',
            '✗ Inválido'
        )
    validity_badge.short_description = "Validez"