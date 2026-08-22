from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission
from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from apps.common.responses import success
from .selectors import dashboard,REPORTS
FULL={UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER}
REPORT_ROLES={
    "sales":{UserRole.FINANCE_MANAGER,UserRole.ORDER_MANAGER,UserRole.MARKETING_MANAGER},
    "orders":{UserRole.ORDER_MANAGER},
    "product-performance":{UserRole.PRODUCT_MANAGER,UserRole.MARKETING_MANAGER},
    "category-performance":{UserRole.PRODUCT_MANAGER,UserRole.MARKETING_MANAGER},
    "brand-performance":{UserRole.PRODUCT_MANAGER,UserRole.MARKETING_MANAGER},
    "inventory":{UserRole.INVENTORY_MANAGER},"stock-aging":{UserRole.INVENTORY_MANAGER},"dead-stock":{UserRole.INVENTORY_MANAGER,UserRole.PRODUCT_MANAGER},
    "low-performing-products":{UserRole.PRODUCT_MANAGER,UserRole.MARKETING_MANAGER},"best-sellers":{UserRole.PRODUCT_MANAGER,UserRole.MARKETING_MANAGER},
    "customers":{UserRole.MARKETING_MANAGER},"customer-lifetime-value":{UserRole.MARKETING_MANAGER,UserRole.FINANCE_MANAGER},
    "payments":{UserRole.FINANCE_MANAGER},"returns":{UserRole.ORDER_MANAGER},"refunds":{UserRole.FINANCE_MANAGER},
    "discounts":{UserRole.MARKETING_MANAGER,UserRole.FINANCE_MANAGER},"coupon-performance":{UserRole.MARKETING_MANAGER},"sales-geography":{UserRole.MARKETING_MANAGER,UserRole.ORDER_MANAGER},
    "funnel":{UserRole.MARKETING_MANAGER},"profit":{UserRole.FINANCE_MANAGER},
}
class ReportPermission(BasePermission):
    def has_permission(self,request,view):
        u=request.user
        if not u or not u.is_authenticated:return False
        if u.is_superuser or u.role in FULL:return True
        report=view.kwargs.get("report") or request.query_params.get("type")
        return u.role in REPORT_ROLES.get(report,set())
DashboardAccess=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.FINANCE_MANAGER,UserRole.MARKETING_MANAGER,UserRole.ORDER_MANAGER,UserRole.INVENTORY_MANAGER,UserRole.PRODUCT_MANAGER)
class DashboardView(APIView):
    permission_classes=[DashboardAccess]
    def get(self,request): return success(dashboard(request.query_params))
class ReportView(APIView):
    permission_classes=[ReportPermission]
    def get(self,request,report=None):
        report=report or request.query_params.get("type")
        if report not in REPORTS: raise ValidationError({"report":f"Unknown report. Available: {', '.join(REPORTS)}"})
        return success({"report":report,"results":REPORTS[report](request.query_params)})

from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.decorators import action
from .models import ReportExport
from .serializers import ReportExportSerializer
from .tasks import export_report
class ReportExportViewSet(ReadOnlyModelViewSet):
    permission_classes=[DashboardAccess]; serializer_class=ReportExportSerializer
    def get_queryset(self):
        qs=ReportExport.objects.select_related("requested_by").order_by("-id")
        return qs if self.request.user.role in FULL or self.request.user.is_superuser else qs.filter(requested_by=self.request.user)
    def create(self,request,*args,**kwargs):
        s=ReportExportSerializer(data=request.data); s.is_valid(raise_exception=True)
        # Reuse report permission against requested report, not just the URL.
        allowed=self.request.user.is_superuser or self.request.user.role in FULL or self.request.user.role in REPORT_ROLES.get(s.validated_data["report"],set())
        if not allowed:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not have access to this report.")
        obj=ReportExport.objects.create(requested_by=request.user,**s.validated_data); export_report.delay(obj.id); return success(ReportExportSerializer(obj,context={"request":request}).data,"Report export queued.",202)
