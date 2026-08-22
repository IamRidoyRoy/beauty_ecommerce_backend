from rest_framework.viewsets import ReadOnlyModelViewSet
from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from .models import Payment
from .serializers import PaymentSerializer
Finance=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.FINANCE_MANAGER)
class AdminPaymentViewSet(ReadOnlyModelViewSet): permission_classes=[Finance]; serializer_class=PaymentSerializer; queryset=Payment.objects.select_related("order").order_by("-id"); filterset_fields=("method","status"); search_fields=("transaction_id","gateway_reference","order__order_number","order__customer_name","order__customer_phone"); ordering_fields=("created_at","amount","paid_at")
