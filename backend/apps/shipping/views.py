from __future__ import annotations

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from apps.common.responses import success
from apps.orders.models import Order

from .courier_config import ensure_courier_configs, is_provider_available, schema_for
from .gateways.base import CourierGatewayError
from .models import CourierConfig, CourierEvent, Shipment, ShippingMethod
from .serializers import CourierConfigSerializer, CourierEventSerializer, ShipmentSerializer, ShippingMethodSerializer
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
    http_method_names = ["get", "patch", "put", "head", "options"]

    def get_queryset(self):
        ensure_courier_configs()
        return CourierConfig.objects.select_related("updated_by").order_by("sort_order", "id")

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
