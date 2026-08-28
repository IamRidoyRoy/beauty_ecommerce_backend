import uuid

from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.accounts.models import UserRole
from apps.common.models import AnalyticsEvent
from apps.common.permissions import role_permission
from apps.common.responses import success
from .models import TrackingEventLog, TrackingSettings
from .serializers import (
    TrackingEventIngestSerializer,
    TrackingEventLogSerializer,
    TrackingPublicConfigSerializer,
    TrackingSettingsAdminSerializer,
)
from .services import new_event_id, product_custom_data, send_meta_event


LEGACY_ANALYTICS_EVENT = {
    "ViewContent": AnalyticsEvent.EventType.PRODUCT_VIEW,
    "AddToCart": AnalyticsEvent.EventType.ADD_TO_CART,
    "AddToWishlist": AnalyticsEvent.EventType.WISHLIST,
    "InitiateCheckout": AnalyticsEvent.EventType.CHECKOUT_STARTED,
    "Purchase": AnalyticsEvent.EventType.ORDER_COMPLETED,
}

TrackingAdmin = role_permission(
    UserRole.SUPER_ADMIN,
    UserRole.ADMIN,
    UserRole.MANAGER,
    UserRole.MARKETING_MANAGER,
)


class TrackingConfigView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return success(TrackingPublicConfigSerializer(TrackingSettings.current()).data)


class TrackingEventView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = TrackingEventIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        settings = TrackingSettings.current()
        event_name = data["event_name"]
        event_id = data.get("event_id") or new_event_id(event_name.lower())

        if settings.require_marketing_consent and not data.get("consent", False):
            TrackingEventLog.objects.create(
                event_name=event_name,
                event_id=event_id,
                source="server",
                status=TrackingEventLog.Status.SKIPPED,
                user_id_ref=request.user.id if request.user.is_authenticated else None,
                error_message="Marketing consent is required.",
            )
            return success({"event_id": event_id, "server_sent": False, "reason": "consent_required"}, "Tracking skipped.")

        metadata = data.get("metadata") or {}
        custom_data = dict(metadata)
        custom_data.update(data.get("custom_data") or {})
        product_id = data.get("product_id_ref")
        if product_id and event_name in {"ViewContent", "AddToCart", "AddToWishlist"}:
            resolved = product_custom_data(
                product_id=product_id,
                variant_id=data.get("variant_id") or metadata.get("variant_id"),
                quantity=data.get("quantity") or metadata.get("quantity") or 1,
                currency=settings.currency,
            )
            resolved.update(custom_data)
            custom_data = resolved

        legacy_type = LEGACY_ANALYTICS_EVENT.get(event_name)
        if legacy_type:
            AnalyticsEvent.objects.create(
                event_type=legacy_type,
                user=request.user if request.user.is_authenticated else None,
                session_token=data.get("session_token", ""),
                cart_token=data.get("cart_token", ""),
                product_id_ref=product_id,
                metadata=metadata,
            )

        result = send_meta_event(
            event_name=event_name,
            event_id=event_id,
            event_source_url=data.get("event_source_url") or request.META.get("HTTP_REFERER", ""),
            custom_data=custom_data,
            request=request,
            user=request.user if request.user.is_authenticated else None,
            fbp=data.get("fbp", ""),
            fbc=data.get("fbc", ""),
        )
        return success({"event_id": event_id, "server_sent": bool(result.get("sent")), "server": result}, "Tracking event processed.", 201)


class TrackingSettingsAdminView(APIView):
    permission_classes = [TrackingAdmin]

    def get(self, request):
        return success(TrackingSettingsAdminSerializer(TrackingSettings.current()).data)

    def patch(self, request):
        obj = TrackingSettings.current()
        serializer = TrackingSettingsAdminSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success(TrackingSettingsAdminSerializer(obj).data, "Tracking settings updated.")


class TrackingTestView(APIView):
    permission_classes = [TrackingAdmin]

    def post(self, request):
        obj = TrackingSettings.current()
        result = send_meta_event(
            event_name="PageView",
            event_id=new_event_id("dashboard-test"),
            event_source_url=request.data.get("event_source_url") or "https://example.com/tracking-test",
            custom_data={"currency": obj.currency, "test_source": "beautyops_dashboard"},
            request=request,
            user=request.user,
            test_event=True,
        )
        obj.last_tested_at = timezone.now()
        obj.last_test_status = "success" if result.get("sent") else "failed"
        obj.last_test_message = "Meta Conversions API test event sent." if result.get("sent") else (result.get("error") or result.get("reason") or "Test event was not sent.")
        obj.save(update_fields=["last_tested_at", "last_test_status", "last_test_message", "updated_at"])
        status = 200 if result.get("sent") else 400
        return success({"result": result, "settings": TrackingSettingsAdminSerializer(obj).data}, obj.last_test_message, status)


class TrackingEventLogAdminViewSet(ReadOnlyModelViewSet):
    permission_classes = [TrackingAdmin]
    serializer_class = TrackingEventLogSerializer
    queryset = TrackingEventLog.objects.all()
    filterset_fields = ("event_name", "status", "source")
    search_fields = ("event_id", "order_number", "error_message")
    ordering_fields = ("created_at", "event_name", "status")
