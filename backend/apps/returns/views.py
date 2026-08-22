from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework.decorators import action
from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from apps.common.responses import success
from .models import ReturnRequest,Refund
from .serializers import *
from .services import create_return_request,approve_return,reject_return,receive_return,create_refund,complete_refund
class ReturnCreateView(APIView):
    permission_classes=[IsAuthenticated]
    def post(self,request):
        s=CreateReturnSerializer(data=request.data); s.is_valid(raise_exception=True); rr=create_return_request(order=s.validated_data["order"],user=request.user,items=s.validated_data["items"],reason=s.validated_data["reason"]); return success(ReturnRequestSerializer(rr).data,"Return requested.",201)
ReturnAdmin=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.ORDER_MANAGER,UserRole.CUSTOMER_SUPPORT)
class AdminReturnViewSet(ReadOnlyModelViewSet):
    permission_classes=[ReturnAdmin]; serializer_class=ReturnRequestSerializer; queryset=ReturnRequest.objects.select_related("order","user","reviewed_by").prefetch_related("items__order_item").order_by("-id"); filterset_fields=("status",); search_fields=("order__order_number","order__customer_name","order__customer_phone","reason","notes"); ordering_fields=("created_at","updated_at")
    @action(detail=True,methods=["post"])
    def approve(self,request,pk=None): return success(ReturnRequestSerializer(approve_return(return_request=self.get_object(),actor=request.user)).data,"Return approved.")
    @action(detail=True,methods=["post"])
    def reject(self,request,pk=None): return success(ReturnRequestSerializer(reject_return(return_request=self.get_object(),actor=request.user,notes=request.data.get("notes",""))).data,"Return rejected.")
    @action(detail=True,methods=["post"])
    def receive(self,request,pk=None): s=ReceiveReturnSerializer(data=request.data); s.is_valid(raise_exception=True); return success(ReturnRequestSerializer(receive_return(return_request=self.get_object(),warehouse=s.validated_data["warehouse"],actor=request.user)).data,"Return received.")
    @action(detail=True,methods=["post"])
    def transition(self,request,pk=None):
        row=self.get_object(); next_status=str(request.data.get("status","")).strip()
        allowed={"review","inspected","refund_processing","completed"}
        transitions={"requested":{"review"},"received":{"inspected"},"inspected":{"refund_processing"},"refund_processing":{"completed"}}
        if next_status not in allowed or next_status not in transitions.get(row.status,set()):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"status":f"Cannot move return from {row.status} to {next_status or 'empty'}."})
        row.status=next_status
        if request.data.get("notes"):
            row.notes=(row.notes+"\n"+str(request.data["notes"])).strip()
        row.reviewed_by=request.user
        row.save(update_fields=["status","notes","reviewed_by","updated_at"])
        return success(ReturnRequestSerializer(row).data,"Return status updated.")
Finance=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.FINANCE_MANAGER)
class AdminRefundViewSet(ReadOnlyModelViewSet):
    permission_classes=[Finance]; serializer_class=RefundSerializer; queryset=Refund.objects.select_related("order","payment","created_by").order_by("-id"); filterset_fields=("status",); search_fields=("order__order_number","order__customer_name","order__customer_phone","payment__transaction_id","gateway_reference","reason"); ordering_fields=("created_at","amount","completed_at")
    @action(detail=False,methods=["post"])
    def create_refund(self,request): s=CreateRefundSerializer(data=request.data); s.is_valid(raise_exception=True); return success(RefundSerializer(create_refund(**s.validated_data,actor=request.user)).data,"Refund created.",201)
    @action(detail=True,methods=["post"])
    def complete(self,request,pk=None): return success(RefundSerializer(complete_refund(refund=self.get_object(),gateway_reference=request.data.get("gateway_reference",""))).data,"Refund completed.")
