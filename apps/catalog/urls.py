from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ProductViewSet, VariantViewSet, BrandViewSet, CategoryViewSet

router = DefaultRouter()
router.register("products", ProductViewSet, basename="product")
router.register("variants", VariantViewSet, basename="variant")
router.register("brands", BrandViewSet, basename="brand")
router.register("categories", CategoryViewSet, basename="category")

urlpatterns = [
    path("", include(router.urls)),
]