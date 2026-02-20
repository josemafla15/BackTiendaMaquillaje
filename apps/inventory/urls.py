from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import StockViewSet

router = DefaultRouter()
router.register("stock", StockViewSet, basename="stock")

urlpatterns = [
    path("", include(router.urls)),
]