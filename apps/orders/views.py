from rest_framework import viewsets, mixins, filters
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend

from .tasks import send_order_status_email


from .models import Order, Refund
from .serializers import OrderSerializer, RefundSerializer, OrderStatusSerializer

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.db.models import Count

from django.db.models import Sum, Count, F
from django.utils import timezone
from datetime import timedelta


class OrderViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrderSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["guest_email", "guest_name", "shipping_name", "wompi_reference"]
    ordering_fields = ["created_at", "total"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in ["list_all", "update_status", "cancel"]:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        # Admin ve todos los pedidos
        if user.is_staff:
            return Order.objects.prefetch_related(
                "items__variant__product"
            ).order_by("-created_at")
        # Usuario normal solo ve los suyos
        return Order.objects.filter(
            user=user
        ).prefetch_related("items__variant").order_by("-created_at")

    @action(detail=True, methods=["patch"], url_path="status", permission_classes=[IsAdminUser])
    def update_status(self, request, pk=None):
        """
        PATCH /api/orders/{id}/status/
        Body: { "status": "SHIPPED" }
        """
        order = self.get_object()
        serializer = OrderStatusSerializer(order, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        send_order_status_email.delay(str(order.id), serializer.data['status'])
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def cancel(self, request, pk=None):
        order = self.get_object()
        try:
            order.cancel()
            send_order_status_email.delay(str(order.id), 'CANCELLED')
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": "cancelado"})
    
    @action(detail=False, methods=["get"], url_path="refundable", permission_classes=[IsAdminUser])
    def refundable(self, request):
        """
        GET /api/orders/refundable/
        Retorna órdenes en estado DELIVERED o PARTIALLY_REFUNDED.
        """
        orders = Order.objects.filter(
            status__in=[Order.Status.DELIVERED, Order.Status.PARTIALLY_REFUNDED]
        ).prefetch_related("items__variant__product").order_by("-created_at")
        
        page = self.paginate_queryset(orders)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)
    
    @action(
    detail=False,
    methods=["get"],
    url_path="stats",
    permission_classes=[IsAdminUser])
    def stats(self, request):
        """
        GET /api/orders/stats/
        Retorna total de pedidos y conteo por estado en una sola query.
        """
        status_counts = (
            Order.objects
            .values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )
        total = Order.objects.count()
    
        return Response({
            "total": total,
            "by_status": {item["status"]: item["count"] for item in status_counts},
        })

    
    @action(
    detail=False,
    methods=["get"],
    url_path="revenue",
    permission_classes=[IsAdminUser]
)
    def revenue(self, request):
        from datetime import date

        department = request.query_params.get("department")
        date_from  = request.query_params.get("date_from")   # YYYY-MM-DD
        date_to    = request.query_params.get("date_to")     # YYYY-MM-DD
        month      = request.query_params.get("month")       # YYYY-MM

        qs = Order.objects.filter(status=Order.Status.DELIVERED)
        if department:
            qs = qs.filter(shipping_department__iexact=department)

        now         = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Rango para la gráfica
        if date_from and date_to:
            range_start = timezone.datetime.strptime(date_from, "%Y-%m-%d").replace(
                tzinfo=timezone.get_current_timezone()
            )
            range_end = timezone.datetime.strptime(date_to, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59,
                tzinfo=timezone.get_current_timezone()
            )
        elif month:
            year, m = map(int, month.split("-"))
            range_start = timezone.datetime(year, m, 1, tzinfo=timezone.get_current_timezone())
            if m == 12:
                range_end = timezone.datetime(year + 1, 1, 1, tzinfo=timezone.get_current_timezone())
            else:
                range_end = timezone.datetime(year, m + 1, 1, tzinfo=timezone.get_current_timezone())
        else:
            range_start = today_start - timedelta(days=30)
            range_end   = now

        def total_in_range(start, end):
            return qs.filter(
                created_at__gte=start, created_at__lt=end
            ).aggregate(total=Sum("total"))["total"] or 0

        # Comparativas fijas (siempre hoy/semana/mes)
        week_start       = today_start - timedelta(days=7)
        month_start      = today_start - timedelta(days=30)
        prev_today_start = today_start - timedelta(days=1)
        prev_week_start  = week_start  - timedelta(days=7)
        prev_month_start = month_start - timedelta(days=30)

        # Ingresos diarios para la gráfica
        daily = (
            qs.filter(created_at__gte=range_start, created_at__lte=range_end)
            .extra(select={"day": "DATE(created_at)"})
            .values("day")
            .annotate(total=Sum("total"))
            .order_by("day")
        )

        return Response({
            "summary": {
                "today":      float(total_in_range(today_start, now)),
                "prev_today": float(total_in_range(prev_today_start, today_start)),
                "week":       float(total_in_range(week_start, now)),
                "prev_week":  float(total_in_range(prev_week_start, week_start)),
                "month":      float(total_in_range(month_start, now)),
                "prev_month": float(total_in_range(prev_month_start, month_start)),
            },
            "daily": [
                {"day": str(row["day"]), "total": float(row["total"])}
                for row in daily
            ],
        })


    @action(
        detail=False,
        methods=["get"],
        url_path="products-stats",
        permission_classes=[IsAdminUser]
    )
    def products_stats(self, request):
        """
        GET /api/orders/products-stats/?department=Nariño
        Métricas de ventas por producto en pedidos DELIVERED.
        """
        department = request.query_params.get("department")

        qs = Order.objects.filter(status=Order.Status.DELIVERED)
        if department:
            qs = qs.filter(shipping_department__iexact=department)

        order_ids = qs.values_list("id", flat=True)

        from apps.orders.models import OrderItem
        items = (
            OrderItem.objects
            .filter(order_id__in=order_ids)
            .values(
                product_name=F("variant__product__name"),
                variant_name=F("variant__name"),
                sku=F("variant__sku"),
            )
            .annotate(
                units_sold=Sum("quantity"),
                revenue=Sum("subtotal"),
                orders_count=Count("order", distinct=True),
            )
            .order_by("-revenue")
        )

        return Response([
            {
                "product_name":  row["product_name"],
                "variant_name":  row["variant_name"],
                "sku":           row["sku"],
                "units_sold":    row["units_sold"],
                "revenue":       float(row["revenue"]),
                "orders_count":  row["orders_count"],
            }
            for row in items
        ])
    
    @action(
    detail=False,
    methods=["get"],
    url_path="analytics",
    permission_classes=[IsAdminUser]
    )
    def analytics(self, request):
        from apps.orders.models import OrderItem
        from apps.catalog.models import Category

        # ── Parámetros ──────────────────────────────────────────────────────
        preset       = request.query_params.get("preset")        # today|yesterday|last7|last30|this_month|this_year
        date_from    = request.query_params.get("date_from")     # YYYY-MM-DD
        date_to      = request.query_params.get("date_to")       # YYYY-MM-DD
        department   = request.query_params.get("department")
        brand_slug   = request.query_params.get("brand")
        category_slug= request.query_params.get("category")
        product_slug = request.query_params.get("product")

        now         = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # ── Calcular rango actual ────────────────────────────────────────────
        if preset == "today":
            range_start, range_end = today_start, now
        elif preset == "yesterday":
            range_start = today_start - timedelta(days=1)
            range_end   = today_start
        elif preset == "last7":
            range_start = today_start - timedelta(days=7)
            range_end   = now
        elif preset == "last30":
            range_start = today_start - timedelta(days=30)
            range_end   = now
        elif preset == "this_month":
            range_start = today_start.replace(day=1)
            range_end   = now
        elif preset == "this_year":
            range_start = today_start.replace(month=1, day=1)
            range_end   = now
        elif date_from and date_to:
            tz = timezone.get_current_timezone()
            range_start = timezone.datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=tz)
            range_end   = timezone.datetime.strptime(date_to,   "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=tz
            )
        else:
            range_start = today_start - timedelta(days=30)
            range_end   = now

        # ── Periodo anterior (misma duración) ───────────────────────────────
        duration       = range_end - range_start
        prev_start     = range_start - duration
        prev_end       = range_start

        # ── QuerySet base ────────────────────────────────────────────────────
        def base_qs(start, end):
            qs = Order.objects.filter(
                status=Order.Status.DELIVERED,
                created_at__gte=start,
                created_at__lte=end,
            )
            if department:
                qs = qs.filter(shipping_department__iexact=department)
            return qs

        qs_current  = base_qs(range_start, range_end)
        qs_previous = base_qs(prev_start,  prev_end)

        def items_qs(order_qs):
            ids = order_qs.values_list("id", flat=True)
            iq  = OrderItem.objects.filter(order_id__in=ids)
            if brand_slug:
                iq = iq.filter(variant__product__brand__slug=brand_slug)
            if category_slug:
                iq = iq.filter(variant__product__categories__slug=category_slug)
            if product_slug:
                iq = iq.filter(variant__product__slug=product_slug)
            return iq

        items_current  = items_qs(qs_current)
        items_previous = items_qs(qs_previous)

        def agg(qs_orders, qs_items):
            result = qs_orders.aggregate(
                subtotal=Sum("subtotal"),
                discount=Sum("discount_amount"),
                count=Count("id")
            )
            subtotal = float(result["subtotal"] or 0)
            discount = float(result["discount"] or 0)
            rev = subtotal - discount
            cnt = result["count"] or 0
            return rev, cnt, (rev / cnt if cnt else 0)

        rev,      orders,      ticket      = agg(qs_current,  items_current)
        prev_rev, prev_orders, prev_ticket = agg(qs_previous, items_previous)

        def pct(current, previous):
            if not previous:
                return 100.0 if current > 0 else 0.0
            return round((current - previous) / previous * 100, 1)

        # ── Ingresos diarios ─────────────────────────────────────────────────
        daily = (
            qs_current
            .extra(select={"day": "DATE(created_at)"})
            .values("day")
            .annotate(
                revenue=Sum("total"),
                orders=Count("id"),
            )
            .order_by("day")
        )

        # ── Top 10 productos por unidades ────────────────────────────────────
        top_products = (
            items_current
            .values(
                pname=F("variant__product__name"),
                pslug=F("variant__product__slug"),
            )
            .annotate(units_sold=Sum("quantity"), revenue=Sum("subtotal"))
            .order_by("-units_sold")[:10]
        )

        # ── Top 10 productos por ingresos ────────────────────────────────────
        revenue_by_product = (
            items_current
            .values(
                pname=F("variant__product__name"),
                pslug=F("variant__product__slug"),
            )
            .annotate(revenue=Sum("subtotal"), units_sold=Sum("quantity"))
            .order_by("-revenue")[:10]
        )

        # ── Por categoría ────────────────────────────────────────────────────
        by_category = (
            items_current
            .filter(variant__product__categories__parent=None)  # ← solo raíz
            .values(cat_name=F("variant__product__categories__name"))
            .annotate(revenue=Sum("subtotal"), units_sold=Sum("quantity"))
            .exclude(cat_name=None)
            .order_by("-revenue")
        )

        # ── Por marca ────────────────────────────────────────────────────────
        by_brand = (
            items_current
            .values(brand_name=F("variant__product__brand__name"))
            .annotate(revenue=Sum("subtotal"), units_sold=Sum("quantity"))
            .order_by("-revenue")
        )

       

        # ── Por departamento ─────────────────────────────────────────────────
        by_department = (
            qs_current
            .values("shipping_department")
            .annotate(
                revenue=Sum("subtotal") - Sum("discount_amount"),
                orders_count=Count("id")
            )
            .order_by("-revenue")
        )

        return Response({
            "period": {
                "start": range_start.date().isoformat(),
                "end":   range_end.date().isoformat(),
            },
            "summary": {
                "revenue":      rev,
                "orders":       orders,
                "avg_ticket":   ticket,
                "prev_revenue": prev_rev,
                "prev_orders":  prev_orders,
                "prev_ticket":  prev_ticket,
                "pct_revenue":  pct(rev,    prev_rev),
                "pct_orders":   pct(orders, prev_orders),
                "pct_ticket":   pct(ticket, prev_ticket),
            },
            "daily": [
                {
                    "day":     str(r["day"]),
                    "revenue": float(r["revenue"]),
                    "orders":  r["orders"],
                }
                for r in daily
            ],
            "top_products": [
                {
                    "product_name": r["pname"],
                    "units_sold":   r["units_sold"],
                    "revenue":      float(r["revenue"]),
                }
                for r in top_products
            ],
            "revenue_by_product": [
                {
                    "product_name": r["pname"],
                    "revenue":      float(r["revenue"]),
                    "units_sold":   r["units_sold"],
                }
                for r in revenue_by_product
            ],
            "by_category": [
                {
                    "category":   r["cat_name"],
                    "revenue":    float(r["revenue"]),
                    "units_sold": r["units_sold"],
                }
                for r in by_category
            ],
            "by_brand": [
                {
                    "brand":      r["brand_name"],
                    "revenue":    float(r["revenue"]),
                    "units_sold": r["units_sold"],
                }
                for r in by_brand
            ],
            "by_department": [
                {
                    "department":   r["shipping_department"],
                    "revenue":      float(r["revenue"]),
                    "orders_count": r["orders_count"],
                }
                for r in by_department
            ],
        })


class RefundViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAdminUser]
    serializer_class = RefundSerializer
    queryset = Refund.objects.select_related("order").order_by("-created_at")
    
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        refund = self.get_object()
        if refund.status != Refund.Status.PENDING:
            return Response(
                {"detail": "Solo se pueden rechazar reembolsos en estado PENDING."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        refund.status = Refund.Status.REJECTED
        refund.save(update_fields=["status", "updated_at"])
        return Response({"status": "rechazado"})
    
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        refund = self.get_object()
        try:
            refund.approve()
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": "aprobado"})