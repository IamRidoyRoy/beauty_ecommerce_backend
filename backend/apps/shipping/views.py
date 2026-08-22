from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ReadOnlyModelViewSet,ModelViewSet
from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from .models import ShippingMethod,Shipment
from .serializers import ShippingMethodSerializer,ShipmentSerializer
class ShippingMethodViewSet(ReadOnlyModelViewSet): permission_classes=[AllowAny]; serializer_class=ShippingMethodSerializer; queryset=ShippingMethod.objects.filter(active=True)
ShippingAdmin=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.ORDER_MANAGER)
class AdminShippingMethodViewSet(ModelViewSet): permission_classes=[ShippingAdmin]; serializer_class=ShippingMethodSerializer; queryset=ShippingMethod.objects.all(); search_fields=("name","code"); filterset_fields=("active",); ordering_fields=("name","base_charge")
class AdminShipmentViewSet(ModelViewSet): permission_classes=[ShippingAdmin]; serializer_class=ShipmentSerializer; queryset=Shipment.objects.select_related("order").all(); search_fields=("courier","tracking_code","order__order_number","order__customer_name","order__customer_phone"); filterset_fields=("courier","status"); ordering_fields=("dispatched_at","delivered_at","id")
