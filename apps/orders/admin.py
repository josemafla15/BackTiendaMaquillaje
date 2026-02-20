from django.contrib import admin
from .models import Order, OrderItem, Refund, RefundItem

admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(Refund)
admin.site.register(RefundItem)