from django.contrib import admin
from .models import ShippingRate


@admin.register(ShippingRate)
class ShippingRateAdmin(admin.ModelAdmin):
    list_display = [
        "name", "city", "department", "price",
        "free_shipping_from", "estimated_days_min",
        "estimated_days_max", "is_default", "is_active",
    ]
    list_filter = ["is_active", "is_default", "department"]
    search_fields = ["name", "city", "department"]
    list_editable = ["price", "free_shipping_from", "is_active"]
    ordering = ["department", "city"]