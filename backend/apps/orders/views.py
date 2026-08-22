from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet,ModelViewSet
from rest_framework.decorators import action
from apps.accounts.models import UserRole,User
from apps.accounts.serializers import UserSerializer
from apps.common.permissions import role_permission
from apps.common.responses import success
from apps.carts.services import get_request_cart
from apps.common.models import AnalyticsEvent
from .models import Order
from .serializers import CheckoutSerializer,OrderSerializer,AdminOrderSerializer,OrderTransitionSerializer
from .services import checkout,transition_order
class CheckoutView(APIView):
    permission_classes=[AllowAny]
    def post(self,request):
        s=CheckoutSerializer(data=request.data); s.is_valid(raise_exception=True); cart=get_request_cart(request,create=False)
        if not cart:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"cart":"Cart not found."})
        v=s.validated_data; customer={k:v[k] for k in ("name","phone","district","thana","address")}; customer["label"]=v.get("label","")
        AnalyticsEvent.objects.create(event_type=AnalyticsEvent.EventType.CHECKOUT_STARTED,user=request.user if request.user.is_authenticated else None,cart_token=str(cart.token))
        result=checkout(cart=cart,customer_data=customer,shipping_method=v.get("shipping_method"),payment_method=v["payment_method"],coupon_code=v.get("coupon_code","").strip(),request_user=request.user if request.user.is_authenticated else None,order_note=v.get("order_note", ""))
        AnalyticsEvent.objects.create(event_type=AnalyticsEvent.EventType.ORDER_COMPLETED,user=result["order"].user,cart_token=str(cart.token),metadata={"order_number":result["order"].order_number,"total":str(result["order"].total)})
        data={"order":OrderSerializer(result["order"],context={"request":request}).data,"account_created":result["account_created"],"existing_account":result.get("existing_account",False),"verification_required":result.get("verification_required",False),"verification_bypassed":result.get("verification_bypassed",False),"delivery":result.get("delivery",{})}
        if result.get("auth"): data["auth"]=result["auth"]
        return success(data,"Order placed successfully.",201)
class MyOrderViewSet(ReadOnlyModelViewSet):
    permission_classes=[IsAuthenticated]; serializer_class=OrderSerializer; lookup_field="order_number"
    def get_queryset(self): return Order.objects.filter(user=self.request.user).select_related("shipping_method","user").prefetch_related("items","payments").order_by("-created_at")
OrderReadAdmin=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.ORDER_MANAGER,UserRole.CUSTOMER_SUPPORT)
OrderWriteAdmin=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.ORDER_MANAGER)
class AdminOrderViewSet(ReadOnlyModelViewSet):
    permission_classes=[OrderReadAdmin]; serializer_class=AdminOrderSerializer; lookup_field="order_number"
    def get_permissions(self):
        classes=[OrderWriteAdmin] if self.action=="transition" else [OrderReadAdmin]
        return [permission() for permission in classes]
    queryset=Order.objects.select_related("user","shipping_method").prefetch_related("items__product","items__variant","payments","shipments").order_by("-created_at")
    filterset_fields=("order_status","payment_status","fulfillment_status","shipping_method"); search_fields=("order_number","customer_name","customer_phone","items__sku_snapshot"); ordering_fields=("created_at","total")
    @action(detail=True,methods=["post"])
    def transition(self,request,order_number=None):
        s=OrderTransitionSerializer(data=request.data); s.is_valid(raise_exception=True); new_status=s.validated_data["new_status"]
        if new_status in {Order.Status.RETURN_REQUESTED,Order.Status.PARTIALLY_RETURNED,Order.Status.RETURNED,Order.Status.REFUNDED}:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"order_status":"Use the return/refund service endpoints for return and refund states."})
        return success(AdminOrderSerializer(transition_order(order=self.get_object(),new_status=new_status,actor=request.user),context={"request":request}).data,"Order status updated.")
    @action(detail=True,methods=["get"])
    def invoice(self,request,order_number=None):
        order=self.get_object(); data={"company":{"name":"Beauty Commerce","address":"Configure company address","phone":"Configure company phone"},"invoice_number":f"INV-{order.order_number}","order":OrderSerializer(order,context={"request":request}).data,"customer":{"name":order.customer_name,"phone":order.customer_phone},"address":order.shipping_address_snapshot,"payment": [{"method":p.method,"status":p.status,"amount":str(p.amount),"transaction_id":p.transaction_id} for p in order.payments.all()],"shipment":[{"courier":x.courier,"tracking_code":x.tracking_code,"status":x.status} for x in order.shipments.all()]}
        return success(data)
CustomerAdmin=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.CUSTOMER_SUPPORT)
class AdminCustomerViewSet(ReadOnlyModelViewSet):
    permission_classes=[CustomerAdmin]; serializer_class=UserSerializer
    queryset=User.objects.filter(role=UserRole.CUSTOMER).prefetch_related("orders","addresses").order_by("-created_at"); search_fields=("full_name","phone","email")
