from __future__ import annotations

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from apps.common.responses import success
from apps.orders.models import Order

from .courier_config import ensure_courier_configs, is_provider_available, schema_for
from .gateways.base import CourierGatewayError, provider_error_details
from .models import CourierConfig, CourierEvent, Shipment, ShippingMethod
from .serializers import (
    CourierBatchSubmitSerializer,
    CourierConfigSerializer,
    CourierDispatchOrderSerializer,
    CourierEventSerializer,
    ShipmentSerializer,
    ShippingMethodSerializer,
)
from .services import book_order, cancel_shipment, process_webhook, request_steadfast_return, test_courier_connection, track_shipment


class ShippingMethodViewSet(ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = ShippingMethodSerializer
    queryset = ShippingMethod.objects.filter(active=True)


ShippingAdmin = role_permission(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER, UserRole.ORDER_MANAGER)
CourierConfigAdmin = role_permission(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER)


class AdminShippingMethodViewSet(ModelViewSet):
    permission_classes = [ShippingAdmin]
    serializer_class = ShippingMethodSerializer
    queryset = ShippingMethod.objects.all()
    search_fields = ("name", "code")
    filterset_fields = ("active",)
    ordering_fields = ("name", "base_charge")


class AdminShipmentViewSet(ReadOnlyModelViewSet):
    permission_classes = [ShippingAdmin]
    serializer_class = ShipmentSerializer
    queryset = Shipment.objects.select_related("order", "booked_by").all().order_by("-created_at")
    search_fields = ("courier", "tracking_code", "external_id", "order__order_number", "order__customer_name", "order__customer_phone")
    filterset_fields = ("courier", "status", "environment", "booking_source")
    ordering_fields = ("created_at", "updated_at", "booked_at", "dispatched_at", "delivered_at")

    @action(detail=False, methods=["get"], url_path="courier-orders")
    def courier_orders(self, request):
        """Packed orders waiting for courier submission plus already Shipped rows."""
        qs = (
            Order.objects.filter(order_status__in=[Order.Status.PACKED, Order.Status.SHIPPED])
            .select_related("shipping_method")
            .prefetch_related("items", "shipments")
            .order_by("-updated_at", "-created_at")
        )
        state = str(request.query_params.get("state") or "").strip().lower()
        if state in {Order.Status.PACKED, Order.Status.SHIPPED}:
            qs = qs.filter(order_status=state)
        courier = str(request.query_params.get("courier") or "").strip().lower()
        if courier:
            qs = qs.filter(shipments__courier__iexact=courier).distinct()
        search = str(request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(order_number__icontains=search)
                | Q(customer_name__icontains=search)
                | Q(customer_phone__icontains=search)
                | Q(items__sku_snapshot__icontains=search)
                | Q(shipments__tracking_code__icontains=search)
            ).distinct()
        page = self.paginate_queryset(qs)
        if page is not None:
            data = CourierDispatchOrderSerializer(page, many=True, context={"request": request}).data
            return self.get_paginated_response(data)
        return success(CourierDispatchOrderSerializer(qs, many=True, context={"request": request}).data)

    @action(detail=False, methods=["post"], url_path="submit-orders")
    def submit_orders(self, request):
        payload = CourierBatchSubmitSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        provider = payload.validated_data["provider"]
        order_ids = payload.validated_data["order_ids"]
        options = payload.validated_data.get("options") or {}

        submitted = []
        failed = []
        # Each order is intentionally independent: a provider/location error for one
        # parcel must not roll back other parcels that were accepted successfully.
        for order_id in order_ids:
            order = Order.objects.filter(pk=order_id).first()
            if not order:
                failed.append({"order_id": order_id, "order_number": "", "message": "Order not found.", "code": "order_not_found"})
                continue
            try:
                shipment = book_order(
                    order=order,
                    provider=provider,
                    options=options,
                    actor=request.user,
                    source=Shipment.BookingSource.MANUAL,
                )
                order.refresh_from_db(fields=["order_status", "updated_at"])
                submitted.append({
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "order_status": order.order_status,
                    "shipment_id": shipment.id,
                    "courier": shipment.courier,
                    "courier_display": CourierConfig.objects.filter(provider=shipment.courier).values_list("display_name", flat=True).first() or schema_for(shipment.courier).get("label", shipment.courier),
                    "tracking_code": shipment.tracking_code or shipment.external_id,
                    "shipment_status": shipment.status,
                })
            except CourierGatewayError as exc:
                failed.append({
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "message": str(exc),
                    "code": exc.code,
                    "details": getattr(exc, "details", None) or provider_error_details(getattr(exc, "response", None)),
                })
            except Exception as exc:
                failed.append({
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "message": str(exc),
                    "code": "courier_submit_failed",
                })

        message = f"{len(submitted)} order(s) submitted to courier."
        if failed:
            message += f" {len(failed)} failed."
        return success({
            "submitted": submitted,
            "failed": failed,
            "submitted_count": len(submitted),
            "failed_count": len(failed),
        }, message)

    @action(detail=False, methods=["get"], url_path="available-couriers")
    def available_couriers(self, request):
        ensure_courier_configs()
        rows = []
        for cfg in CourierConfig.objects.filter(is_active=True).order_by("sort_order", "id"):
            available = is_provider_available(cfg.provider)
            if available:
                schema = schema_for(cfg.provider)
                rows.append({
                    "provider": cfg.provider,
                    "display_name": cfg.display_name,
                    "environment": "sandbox" if cfg.sandbox_mode and schema.get("supports_sandbox") else "live",
                    "supports_cancel": bool(schema.get("supports_cancel")) and cfg.cancel_api_enabled,
                    "supports_sandbox": bool(schema.get("supports_sandbox")),
                    "auto_book_enabled": cfg.auto_book_enabled,
                    "sort_order": cfg.sort_order,
                })
        return success(rows)

    @action(detail=False, methods=["post"], url_path="book")
    def book(self, request):
        order_id = request.data.get("order")
        provider = request.data.get("provider")
        if not order_id or not provider:
            return Response({"success": False, "message": "order and provider are required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            order = Order.objects.get(pk=order_id)
            shipment = book_order(order=order, provider=provider, options=request.data.get("options") or {}, actor=request.user)
            return success(self.get_serializer(shipment).data, "Courier shipment booked successfully.", 201)
        except Order.DoesNotExist:
            return Response({"success": False, "message": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        except CourierGatewayError as exc:
            return Response({"success": False, "message": str(exc), "errors": {"courier": exc.code}}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def track(self, request, pk=None):
        try:
            shipment = track_shipment(shipment=self.get_object(), actor=request.user)
            return success(self.get_serializer(shipment).data, "Shipment status synced with courier.")
        except CourierGatewayError as exc:
            return Response({"success": False, "message": str(exc), "errors": {"courier": exc.code}}, status=status.HTTP_502_BAD_GATEWAY)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        try:
            shipment = cancel_shipment(shipment=self.get_object(), reason=str(request.data.get("reason") or ""), actor=request.user)
            return success(self.get_serializer(shipment).data, "Cancellation submitted to courier.")
        except CourierGatewayError as exc:
            return Response({"success": False, "message": str(exc), "errors": {"courier": exc.code}}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="request-return")
    def request_return(self, request, pk=None):
        try:
            data = request_steadfast_return(shipment=self.get_object(), reason=str(request.data.get("reason") or ""), actor=request.user)
            return success(data, "Steadfast return request submitted.")
        except CourierGatewayError as exc:
            return Response({"success": False, "message": str(exc), "errors": {"courier": exc.code}}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        rows = self.get_object().events.select_related("requested_by").order_by("-created_at")[:200]
        return success(CourierEventSerializer(rows, many=True).data)


class AdminCourierConfigViewSet(ModelViewSet):
    permission_classes = [CourierConfigAdmin]
    serializer_class = CourierConfigSerializer
    # This endpoint represents a tiny fixed provider registry, not a pageable business list.
    # Returning a plain list keeps the dashboard contract stable regardless of global DRF pagination.
    pagination_class = None
    # POST is required for detail actions such as test-connection.
    # Collection-level create remains explicitly disabled below so providers
    # can only come from the fixed registry created by ensure_courier_configs().
    http_method_names = ["get", "post", "patch", "put", "head", "options"]

    def get_queryset(self):
        ensure_courier_configs()
        return CourierConfig.objects.select_related("updated_by").order_by("sort_order", "id")

    def create(self, request, *args, **kwargs):
        # Courier providers are a fixed registry (Pathao, Steadfast, RedX, CarryBee).
        # POST is enabled only so custom detail actions such as test-connection work.
        raise MethodNotAllowed("POST", detail="Courier configurations cannot be created manually.")

    @action(detail=True, methods=["post"], url_path="test-connection")
    def test_connection(self, request, pk=None):
        cfg = self.get_object()
        try:
            data = test_courier_connection(cfg, actor=request.user)
            return success({"provider": cfg.provider, "environment": cfg.environment, "response": data}, f"{cfg.display_name} connection successful.")
        except CourierGatewayError as exc:
            return Response({"success": False, "message": str(exc), "errors": {"courier": exc.code}}, status=status.HTTP_502_BAD_GATEWAY)


class CourierWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, provider):
        try:
            shipment = process_webhook(provider=provider, payload=request.data if isinstance(request.data, dict) else {}, headers=request.headers)
            return success({"shipment_id": getattr(shipment, "id", None)}, "Courier webhook received.")
        except CourierGatewayError as exc:
            return Response({"success": False, "message": str(exc)}, status=status.HTTP_401_UNAUTHORIZED if exc.code in {"invalid_webhook_signature", "webhook_not_configured"} else status.HTTP_400_BAD_REQUEST)
