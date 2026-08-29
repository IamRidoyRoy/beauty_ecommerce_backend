from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from apps.common.responses import success

from .gateways import PaymentGatewayError
from .models import Payment, PaymentGatewayConfig
from .serializers import PaymentGatewayConfigSerializer, PaymentReconciliationSerializer, PaymentSerializer, PublicPaymentSerializer
from .services import (
    find_payment_for_provider_payload,
    gateway_provider,
    initiate_gateway_payment,
    mark_payment_unpaid,
    process_webhook,
    reconcile_payment,
    webhook_event_id,
)
from .gateway_config import ensure_gateway_configs, is_provider_available



Finance = role_permission(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER, UserRole.FINANCE_MANAGER)
GatewayAdmin = role_permission(UserRole.SUPER_ADMIN, UserRole.ADMIN)


def _payload(request):
    data = {}
    if hasattr(request, "query_params"):
        data.update(request.query_params.dict())
    if isinstance(getattr(request, "data", None), dict):
        data.update(request.data)
    else:
        try:
            data.update(request.POST.dict())
        except Exception:
            pass
    return data


def _storefront_redirect(payment: Payment, status_value: str):
    base = getattr(settings, "PAYMENT_STOREFRONT_URL", "").strip().rstrip("/")
    if not base:
        return JsonResponse({"payment": str(payment.public_token), "order": payment.order.order_number, "status": status_value})
    query = urlencode({"payment": status_value})
    return redirect(f"{base}/order-success/{payment.order.order_number}?{query}")


class PublicPaymentMethodsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        ensure_gateway_configs()
        methods = [{
            "code": Payment.Method.COD,
            "display_name": "Cash on Delivery",
            "provider": "cod",
            "environment": "offline",
            "sort_order": 0,
        }]
        for config in PaymentGatewayConfig.objects.filter(is_active=True).order_by("sort_order", "id"):
            if not is_provider_available(config.provider):
                continue
            methods.append({
                "code": config.provider,
                "display_name": config.display_name,
                "provider": config.provider,
                "environment": config.environment,
                "sort_order": config.sort_order,
            })
        return success(methods)


class PaymentInitiateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, public_token):
        payment = Payment.objects.select_related("order__user").filter(public_token=public_token).first()
        if not payment:
            return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)
        if payment.status in {Payment.Status.PAID, Payment.Status.PARTIAL_REFUND, Payment.Status.REFUNDED}:
            return success(PublicPaymentSerializer(payment).data, "Payment is already completed.")
        try:
            payment = initiate_gateway_payment(payment=payment, request=request)
        except PaymentGatewayError as exc:
            return Response(
                {"success": False, "message": str(exc), "errors": {"payment": exc.code}},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return success(PublicPaymentSerializer(payment).data, "Payment initialized.")


class SSLCommerzCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    outcome = "success"

    def post(self, request):
        return self._handle(request)

    def get(self, request):
        return self._handle(request)

    def _handle(self, request):
        payload = _payload(request)
        payment = find_payment_for_provider_payload(provider="sslcommerz", payload=payload)
        if not payment:
            return JsonResponse({"ok": False, "detail": "Payment not found."}, status=404)
        try:
            payment = reconcile_payment(payment=payment, callback_payload=payload)
        except PaymentGatewayError:
            payment.refresh_from_db()
        if payment.status != Payment.Status.PAID and self.outcome in {"fail", "cancel"}:
            payment = mark_payment_unpaid(
                payment=payment,
                status=Payment.Status.CANCELLED if self.outcome == "cancel" else Payment.Status.FAILED,
                failure_code=str(payload.get("status") or self.outcome).upper(),
                failure_message=str(payload.get("error") or payload.get("failedreason") or ""),
            )
        return _storefront_redirect(payment, payment.status)


class SSLCommerzSuccessView(SSLCommerzCallbackView):
    outcome = "success"


class SSLCommerzFailView(SSLCommerzCallbackView):
    outcome = "fail"


class SSLCommerzCancelView(SSLCommerzCallbackView):
    outcome = "cancel"


class SSLCommerzIPNView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        payload = _payload(request)
        payment = find_payment_for_provider_payload(provider="sslcommerz", payload=payload)
        if not payment:
            return JsonResponse({"ok": False, "detail": "Payment not found."}, status=404)
        event_id = webhook_event_id("sslcommerz", payload)

        def handler(data):
            reconcile_payment(payment=payment, callback_payload=data)

        try:
            event, created = process_webhook(
                provider="sslcommerz", event_id=event_id, payload=payload, handler=handler, payment=payment
            )
        except PaymentGatewayError as exc:
            return JsonResponse({"ok": False, "detail": str(exc)}, status=400)
        return JsonResponse({"ok": True, "processed": created, "event_id": event.event_id})


class BKashCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        payload = _payload(request)
        payment = find_payment_for_provider_payload(provider="bkash", payload=payload)
        if not payment:
            return JsonResponse({"ok": False, "detail": "Payment not found."}, status=404)
        try:
            payment = reconcile_payment(payment=payment, callback_payload=payload)
        except PaymentGatewayError:
            payment.refresh_from_db()
        return _storefront_redirect(payment, payment.status)

    post = get


class NagadCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        payload = _payload(request)
        payment = find_payment_for_provider_payload(provider="nagad", payload=payload)
        if not payment:
            return JsonResponse({"ok": False, "detail": "Payment not found."}, status=404)
        try:
            payment = reconcile_payment(payment=payment, callback_payload=payload)
        except PaymentGatewayError:
            payment.refresh_from_db()
        return _storefront_redirect(payment, payment.status)

    post = get


class GenericGatewayWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, provider):
        if provider not in {"bkash", "nagad"}:
            return JsonResponse({"ok": False, "detail": "Unsupported provider."}, status=404)
        payload = _payload(request)
        payment = find_payment_for_provider_payload(provider=provider, payload=payload)
        if not payment:
            return JsonResponse({"ok": False, "detail": "Payment not found."}, status=404)
        event_id = webhook_event_id(provider, payload)

        def handler(data):
            # Never trust a webhook's paid flag on its own; always query the gateway.
            reconcile_payment(payment=payment, callback_payload=data)

        try:
            event, created = process_webhook(
                provider=provider, event_id=event_id, payload=payload, handler=handler, payment=payment
            )
        except PaymentGatewayError as exc:
            return JsonResponse({"ok": False, "detail": str(exc)}, status=400)
        return JsonResponse({"ok": True, "processed": created, "event_id": event.event_id})


class AdminPaymentGatewayConfigViewSet(ModelViewSet):
    permission_classes = [GatewayAdmin]
    serializer_class = PaymentGatewayConfigSerializer
    http_method_names = ["get", "patch", "put", "head", "options"]
    pagination_class = None

    def get_queryset(self):
        ensure_gateway_configs()
        return PaymentGatewayConfig.objects.select_related("updated_by").order_by("sort_order", "id")


class AdminPaymentViewSet(ReadOnlyModelViewSet):
    permission_classes = [Finance]
    serializer_class = PaymentSerializer
    queryset = Payment.objects.select_related("order").prefetch_related("reconciliations").order_by("-id")
    filterset_fields = ("method", "status")
    search_fields = (
        "transaction_id", "gateway_reference", "order__order_number", "order__customer_name", "order__customer_phone"
    )
    ordering_fields = ("created_at", "amount", "paid_at", "last_verified_at")

    @action(detail=True, methods=["post"])
    def reconcile(self, request, pk=None):
        payment = self.get_object()
        if not gateway_provider(payment):
            return Response({"detail": "COD payments cannot be gateway-reconciled."}, status=400)
        try:
            payment = reconcile_payment(payment=payment, requested_by=request.user)
        except PaymentGatewayError as exc:
            return Response(
                {"success": False, "message": str(exc), "errors": {"payment": exc.code}},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return success(PaymentSerializer(payment).data, "Payment reconciled with gateway.")

    @action(detail=True, methods=["get"])
    def reconciliations(self, request, pk=None):
        payment = self.get_object()
        rows = payment.reconciliations.select_related("requested_by").order_by("-created_at")[:100]
        return success(PaymentReconciliationSerializer(rows, many=True).data)
