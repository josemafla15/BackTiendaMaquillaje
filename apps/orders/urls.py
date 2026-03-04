from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import OrderViewSet, RefundViewSet

orders_router = DefaultRouter()
orders_router.register("", OrderViewSet, basename="order")

refunds_router = DefaultRouter()
refunds_router.register("", RefundViewSet, basename="refund")

urlpatterns = [
    path("refunds/", include(refunds_router.urls)),
    path("", include(orders_router.urls)),
]