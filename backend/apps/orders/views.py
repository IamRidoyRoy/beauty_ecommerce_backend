from django.utils.dateparse import parse_date
from django.db.models import Count, Sum, Avg, Max, DecimalField, Value
from django.db.models.functions import Coalesce
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
from apps.tracking.services import send_purchase_for_order
from apps.tracking.models import TrackingSettings, TrackingEventLog
from .models import Order
from .serializers import CheckoutSerializer,OrderSerializer,AdminOrderSerializer,OrderTransitionSerializer,AdminOrderCreateSerializer,AdminOrderCouponPreviewSerializer,AdminCustomerListSerializer,AdminCustomerDetailSerializer
from .services import checkout,transition_order_to_status,create_admin_order,preview_admin_order_coupon
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
        # Purchase is the authoritative server-side conversion. Browser GTM will
        # fire the same event_id (purchase:<order_number>) for Meta deduplication.
        try:
            tracking_settings = TrackingSettings.current()
            if not tracking_settings.require_marketing_consent or v.get("marketing_consent", True):
                send_purchase_for_order(order=result["order"], request=request)
        except Exception as exc:
            # Tracking must never make a successfully validated order fail. This
            # also keeps checkout operational if deployment code is copied before
            # the tracking migration has been applied.
            try:
                TrackingEventLog.objects.create(
                    event_name="Purchase",
                    event_id=f"purchase:{result['order'].order_number}",
                    source="server",
                    status=TrackingEventLog.Status.FAILED,
                    user_id_ref=getattr(result["order"].user, "id", None),
                    order_number=result["order"].order_number,
                    error_message=f"Unexpected tracking failure: {exc}",
                )
            except Exception:
                pass
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
        classes=[OrderWriteAdmin] if self.action in {"transition","create_order","validate_coupon"} else [OrderReadAdmin]
        return [permission() for permission in classes]
    queryset=Order.objects.select_related("user","shipping_method").prefetch_related("items__product","items__variant","payments","shipments").order_by("-created_at")
    filterset_fields=("order_status","payment_status","fulfillment_status","shipping_method"); search_fields=("order_number","customer_name","customer_phone","items__sku_snapshot","shipments__tracking_code","shipments__courier"); ordering_fields=("created_at","total")
    def get_queryset(self):
        qs=super().get_queryset(); start=parse_date(self.request.query_params.get("date_from", "")); end=parse_date(self.request.query_params.get("date_to", ""))
        if start: qs=qs.filter(created_at__date__gte=start)
        if end: qs=qs.filter(created_at__date__lte=end)
        courier=self.request.query_params.get("courier")
        if courier: qs=qs.filter(shipments__courier__iexact=courier)
        return qs.distinct()

    @action(detail=False,methods=["post"],url_path="validate-coupon")
    def validate_coupon(self,request):
        s=AdminOrderCouponPreviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v=s.validated_data
        data=preview_admin_order_coupon(
            items=v["items"],
            code=v["code"],
            phone=v.get("phone", ""),
        )
        return success(data,"Coupon applied successfully.")

    @action(detail=False,methods=["post"],url_path="create-order")
    def create_order(self,request):
        s=AdminOrderCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        v=s.validated_data
        customer={k:v[k] for k in ("name","phone","district","thana","address")}
        customer["label"]=v.get("label","")
        result=create_admin_order(
            items=v["items"],
            customer_data=customer,
            shipping_method=v.get("shipping_method"),
            payment_method=v["payment_method"],
            coupon_code=v.get("coupon_code","").strip(),
            order_note=v.get("order_note",""),
            actor=request.user,
        )
        data={
            "order":AdminOrderSerializer(result["order"],context={"request":request}).data,
            "account_created":result.get("account_created",False),
            "existing_account":result.get("existing_account",False),
            "delivery":result.get("delivery",{}),
        }
        return success(data,"Order created successfully.",201)

    @action(detail=True,methods=["post"])
    def transition(self,request,order_number=None):
        s=OrderTransitionSerializer(data=request.data); s.is_valid(raise_exception=True); new_status=s.validated_data["new_status"]
        if new_status in {Order.Status.RETURN_REQUESTED,Order.Status.PARTIALLY_RETURNED,Order.Status.RETURNED,Order.Status.REFUNDED}:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"order_status":"Use the return/refund service endpoints for return and refund states."})
        return success(AdminOrderSerializer(transition_order_to_status(order=self.get_object(),new_status=new_status,actor=request.user),context={"request":request}).data,"Order status updated.")
    @action(detail=True,methods=["get"])
    def invoice(self,request,order_number=None):
        order=self.get_object(); data={"company":{"name":"Beauty Commerce","address":"Configure company address","phone":"Configure company phone"},"invoice_number":f"INV-{order.order_number}","order":OrderSerializer(order,context={"request":request}).data,"customer":{"name":order.customer_name,"phone":order.customer_phone},"address":order.shipping_address_snapshot,"payment": [{"method":p.method,"status":p.status,"amount":str(p.amount),"transaction_id":p.transaction_id} for p in order.payments.all()],"shipment":[{"courier":x.courier,"tracking_code":x.tracking_code,"status":x.status} for x in order.shipments.all()]}
        return success(data)
CustomerAdmin=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.ORDER_MANAGER,UserRole.CUSTOMER_SUPPORT)
class AdminCustomerViewSet(ReadOnlyModelViewSet):
    permission_classes=[CustomerAdmin]
    search_fields=("full_name","phone","email")
    filterset_fields=("is_active",)
    ordering_fields=("created_at","full_name","phone","orders_count","lifetime_spend","average_order","last_order")

    def get_serializer_class(self):
        return AdminCustomerDetailSerializer if self.action == "retrieve" else AdminCustomerListSerializer

    def get_queryset(self):
        money_field=DecimalField(max_digits=16,decimal_places=2)
        qs=(User.objects.filter(role=UserRole.CUSTOMER)
            .annotate(
                orders_count=Count("orders",distinct=True),
                lifetime_spend=Coalesce(Sum("orders__total"),Value(0),output_field=money_field),
                average_order=Coalesce(Avg("orders__total"),Value(0),output_field=money_field),
                last_order=Max("orders__created_at"),
            )
            .prefetch_related(
                "addresses",
                "orders__items",
                "orders__payments",
                "orders__shipping_method",
                "orders__refunds",
                "return_requests__order",
                "reviews__product",
                "wishlist_items__product",
            )
            .order_by("-created_at"))
        return qs

    @action(detail=True,methods=["patch"],url_path="status")
    def status(self,request,pk=None):
        customer=self.get_object()
        value=request.data.get("is_active")
        if not isinstance(value,bool):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"is_active":"A boolean value is required."})
        customer.is_active=value
        customer.save(update_fields=["is_active","updated_at"])
        return success(self.get_serializer(customer).data,"Customer status updated.")
