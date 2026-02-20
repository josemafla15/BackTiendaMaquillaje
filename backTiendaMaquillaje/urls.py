from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenBlacklistView

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # JWT Auth
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/token/blacklist/", TokenBlacklistView.as_view(), name="token_blacklist"),

    # Apps
    path("api/catalog/", include("apps.catalog.urls")),
    path("api/inventory/", include("apps.inventory.urls")),
    path("api/orders/", include("apps.orders.urls")),
    path("api/promotions/", include("apps.promotions.urls")),
]