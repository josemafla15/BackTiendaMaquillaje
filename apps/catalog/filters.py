import django_filters
from .models import Product


class ProductFilter(django_filters.FilterSet):
    brand = django_filters.CharFilter(field_name="brand__slug")
    category = django_filters.CharFilter(
        field_name="categories__slug", distinct=True
    )
    min_price = django_filters.NumberFilter(
        field_name="variants__price", lookup_expr="gte"
    )
    max_price = django_filters.NumberFilter(
        field_name="variants__price", lookup_expr="lte"
    )
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")
    on_sale = django_filters.BooleanFilter(method="filter_on_sale")
    is_new = django_filters.BooleanFilter(method="filter_is_new")

    class Meta:
        model = Product
        fields = ["brand", "category", "is_featured"]

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(
                variants__stock__quantity__gt=0
            ).distinct()
        return queryset

    def filter_on_sale(self, queryset, name, value):
        if value:
            return queryset.filter(
                variants__sale_price__isnull=False
            ).distinct()
        return queryset

    def filter_is_new(self, queryset, name, value):
        """Productos creados en los últimos 30 días — sección NEW."""
        if value:
            from django.utils import timezone
            from datetime import timedelta
            thirty_days_ago = timezone.now() - timedelta(days=30)
            return queryset.filter(created_at__gte=thirty_days_ago)
        return queryset