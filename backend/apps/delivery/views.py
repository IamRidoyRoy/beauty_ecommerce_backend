from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from apps.common.responses import success

from .models import City, DeliveryModule, Thana
from .serializers import (
    AdminCitySerializer,
    AdminThanaSerializer,
    CitySerializer,
    DeliveryModuleSerializer,
    ThanaSerializer,
)
from .services import resolve_delivery_quote


class DistrictViewSet(ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = CitySerializer
    pagination_class = None
    queryset = City.objects.filter(active=True).select_related("delivery_module").order_by("name")

    @action(detail=True, methods=["get"], url_path="thanas")
    def thanas(self, request, pk=None):
        district = self.get_object()
        rows = district.thanas.filter(active=True).select_related("city__delivery_module", "delivery_module").order_by("name")
        return Response(ThanaSerializer(rows, many=True).data)


class ThanaViewSet(ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = ThanaSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Thana.objects.filter(active=True).select_related("city__delivery_module", "delivery_module").order_by("name")
        district = self.request.query_params.get("district") or self.request.query_params.get("city")
        if district:
            qs = qs.filter(city_id=district)
        return qs


class DeliveryModuleViewSet(ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = DeliveryModuleSerializer
    pagination_class = None
    queryset = DeliveryModule.objects.filter(active=True).order_by("sort_order", "id")


class DeliveryQuoteViewSet(ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = DeliveryModuleSerializer
    pagination_class = None
    queryset = DeliveryModule.objects.none()

    def list(self, request, *args, **kwargs):
        district_id = request.query_params.get("district")
        thana_id = request.query_params.get("thana")
        if not district_id or not thana_id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"district": "district is required.", "thana": "thana is required."})
        try:
            district = City.objects.select_related("delivery_module").get(pk=district_id, active=True)
        except (City.DoesNotExist, ValueError):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"district": "Invalid district."})
        try:
            thana = Thana.objects.select_related("city__delivery_module", "delivery_module").get(pk=thana_id, active=True)
        except (Thana.DoesNotExist, ValueError):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"thana": "Invalid thana."})
        quote = resolve_delivery_quote(district=district, thana=thana)
        return success({
            "district": {"id": district.id, "name": district.name},
            "thana": {"id": thana.id, "name": thana.name},
            "delivery_module": DeliveryModuleSerializer(quote.module).data,
            "charge": str(quote.charge),
        })


DeliveryAdmin = role_permission(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER, UserRole.ORDER_MANAGER)


class AdminDeliveryModuleViewSet(ModelViewSet):
    permission_classes = [DeliveryAdmin]
    serializer_class = DeliveryModuleSerializer
    queryset = DeliveryModule.objects.all().order_by("sort_order", "id")


class AdminDistrictViewSet(ModelViewSet):
    permission_classes = [DeliveryAdmin]
    serializer_class = AdminCitySerializer
    queryset = City.objects.select_related("delivery_module").all().order_by("name")
    search_fields = ("name",)
    filterset_fields = ("active", "delivery_module")


class AdminThanaViewSet(ModelViewSet):
    permission_classes = [DeliveryAdmin]
    serializer_class = AdminThanaSerializer
    queryset = Thana.objects.select_related("city", "delivery_module").all().order_by("city__name", "name")
    search_fields = ("name", "city__name")
    filterset_fields = ("active", "city", "delivery_module")
