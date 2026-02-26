from django.contrib import admin
from django.utils.html import format_html
from .models import Order, OrderItem, Refund, RefundItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product_name", "variant_name", "sku", "unit_price", "quantity", "subtotal"]
    can_delete = False


class RefundInline(admin.TabularInline):
    model = Refund
    extra = 0
    readonly_fields = ["status", "amount", "reason", "processed_at"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "id", "status_badge", "guest_name", "guest_email",
        "total", "shipping_city", "created_at"
    ]
    list_filter = ["status", "created_at", "shipping_city"]
    search_fields = ["guest_email", "guest_name", "wompi_reference", "shipping_name"]
    readonly_fields = [
        "subtotal", "discount_amount", "shipping_amount", "total",
        "wompi_transaction_id", "wompi_reference", "created_at", "updated_at"
    ]
    ordering = ["-created_at"]
    inlines = [OrderItemInline, RefundInline]
    actions = ["mark_as_paid", "mark_as_shipped", "mark_as_delivered"]

    fieldsets = (
        ("Estado", {
            "fields": ("status",)
        }),
        ("Cliente", {
            "fields": ("user", "guest_name", "guest_email")
        }),
        ("Envío", {
            "fields": (
                "shipping_name", "shipping_address", "shipping_city",
                "shipping_department", "shipping_postal_code", "shipping_phone"
            )
        }),
        ("Montos", {
            "fields": ("subtotal", "discount_amount", "shipping_amount", "total", "coupon")
        }),
        ("Wompi", {
            "fields": ("wompi_transaction_id", "wompi_reference"),
            "classes": ("collapse",)
        }),
        ("Notas", {
            "fields": ("notes",),
            "classes": ("collapse",)
        }),
    )

    def status_badge(self, obj):
        colors = {
            "PENDING_PAYMENT": "#f59e0b",
            "PAYMENT_PROCESSING": "#3b82f6",
            "PAID": "#10b981",
            "PREPARING": "#8b5cf6",
            "SHIPPED": "#06b6d4",
            "DELIVERED": "#22c55e",
            "CANCELLED": "#ef4444",
            "REFUNDED": "#6b7280",
            "PARTIALLY_REFUNDED": "#f97316",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = "Estado"

    @admin.action(description="Marcar como Pagado")
    def mark_as_paid(self, request, queryset):
        queryset.update(status=Order.Status.PAID)

    @admin.action(description="Marcar como Enviado")
    def mark_as_shipped(self, request, queryset):
        queryset.update(status=Order.Status.SHIPPED)

    @admin.action(description="Marcar como Entregado")
    def mark_as_delivered(self, request, queryset):
        queryset.update(status=Order.Status.DELIVERED)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "status", "amount", "processed_at"]
    list_filter = ["status"]
    readonly_fields = ["processed_at", "processed_by"]
    actions = ["approve_refunds"]

    @admin.action(description="Aprobar reembolsos seleccionados")
    def approve_refunds(self, request, queryset):
        for refund in queryset.filter(status=Refund.Status.PENDING):
            refund.approve()
