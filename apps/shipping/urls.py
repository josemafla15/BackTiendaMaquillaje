from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ShippingCalculateView, ShippingRateViewSet

router = DefaultRouter()
router.register("rates", ShippingRateViewSet, basename="shipping-rate")

urlpatterns = [
    path("calculate/", ShippingCalculateView.as_view(), name="shipping-calculate"),
    path("", include(router.urls)),
]