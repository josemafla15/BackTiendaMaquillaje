from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import OrderViewSet, RefundViewSet

router = DefaultRouter()
router.register("", OrderViewSet, basename="order")
router.register("refunds", RefundViewSet, basename="refund")

urlpatterns = [
    path("", include(router.urls)),
]