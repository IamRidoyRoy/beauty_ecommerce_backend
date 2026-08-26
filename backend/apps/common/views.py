from django.conf import settings
from django.core.management import call_command
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.viewsets import ModelViewSet

from apps.accounts.models import User, UserRole
from apps.catalog.models import Product, ProductVariant
from apps.inventory.models import Purchase, Supplier
from apps.orders.models import Order
from apps.promotions.models import Coupon
from apps.shipping.models import Shipment
from .models import AnalyticsEvent, AnnouncementMessage, CheckoutSettings, HeroSlide
from .permissions import role_permission
from .responses import success

class AnalyticsEventSerializer(serializers.ModelSerializer):
    class Meta:
        model=AnalyticsEvent
        fields=('event_type','session_token','cart_token','product_id_ref','metadata')

class AnalyticsEventView(APIView):
    permission_classes=[AllowAny]
    def post(self,request):
        serializer=AnalyticsEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user if request.user.is_authenticated else None)
        return success(message='Event recorded.',status=201)




class AnnouncementMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnouncementMessage
        fields = ("id", "text", "icon", "link_url", "active", "order", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class AnnouncementMessageListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        queryset = (AnnouncementMessage.objects.filter(active=True)
            .annotate(_priority_bucket=Case(When(order__gt=0, then=Value(0)), default=Value(1), output_field=IntegerField()))
            .order_by("_priority_bucket", "order", "id"))
        return success(AnnouncementMessageSerializer(queryset, many=True).data)


class HeroSlideSerializer(serializers.ModelSerializer):
    class Meta:
        model = HeroSlide
        fields = (
            "id", "eyebrow", "title", "subtitle", "image", "mobile_image", "image_alt",
            "primary_cta_label", "primary_cta_url", "secondary_cta_label", "secondary_cta_url",
            "text_position", "theme", "overlay_opacity", "active", "order", "starts_at", "ends_at",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_overlay_opacity(self, value):
        if value > 90:
            raise serializers.ValidationError("Overlay opacity must be between 0 and 90.")
        return value

    def validate(self, attrs):
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "End time must be after the start time."})
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["image"] = instance.image.url if instance.image else None
        data["mobile_image"] = instance.mobile_image.url if instance.mobile_image else None
        return data


class HeroSlideListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        now = timezone.now()
        queryset = (
            HeroSlide.objects.filter(active=True)
            .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
            .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
            .order_by("order", "id")
        )
        return success(HeroSlideSerializer(queryset, many=True, context={"request": request}).data)

DemoAdmin=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN)
ManagementAdmin=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER)
StaffAdmin=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN)
SearchAdmin=role_permission(
    UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.PRODUCT_MANAGER,
    UserRole.INVENTORY_MANAGER,UserRole.ORDER_MANAGER,UserRole.CUSTOMER_SUPPORT,
    UserRole.MARKETING_MANAGER,UserRole.FINANCE_MANAGER,
)


MarketingAdmin=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.MARKETING_MANAGER)



class AnnouncementMessageAdminViewSet(ModelViewSet):
    permission_classes = [MarketingAdmin]
    serializer_class = AnnouncementMessageSerializer
    queryset = (AnnouncementMessage.objects.all()
        .annotate(_priority_bucket=Case(When(order__gt=0, then=Value(0)), default=Value(1), output_field=IntegerField()))
        .order_by("_priority_bucket", "order", "id"))
    search_fields = ("text", "link_url")
    filterset_fields = ("active", "icon")
    ordering_fields = ("order", "created_at", "updated_at")
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]


class HeroSlideAdminViewSet(ModelViewSet):
    permission_classes = [MarketingAdmin]
    serializer_class = HeroSlideSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = HeroSlide.objects.all().order_by("order", "id")
    search_fields = ("title", "subtitle", "eyebrow")
    filterset_fields = ("active", "text_position", "theme")
    ordering_fields = ("order", "created_at", "updated_at", "title")
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

class DemoImportView(APIView):
    permission_classes=[DemoAdmin]
    def post(self,request):
        if not settings.DEBUG:
            raise PermissionDenied('Demo import is available only in development.')
        call_command('seed_full_demo')
        return success(message='Demo data imported.')

class CheckoutSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model=CheckoutSettings
        fields=('id','existing_customer_otp_verification','created_at','updated_at')
        read_only_fields=('id','created_at','updated_at')

class CheckoutSettingsAdminView(APIView):
    permission_classes=[ManagementAdmin]
    def get_object(self):
        obj,_=CheckoutSettings.objects.get_or_create(pk=1,defaults={'existing_customer_otp_verification':True})
        return obj
    def get(self,request):
        return success(CheckoutSettingsSerializer(self.get_object()).data)
    def patch(self,request):
        obj=self.get_object(); serializer=CheckoutSettingsSerializer(obj,data=request.data,partial=True); serializer.is_valid(raise_exception=True); serializer.save()
        return success(serializer.data,'Checkout settings updated.')

class StaffUserSerializer(serializers.ModelSerializer):
    password=serializers.CharField(write_only=True,required=False,allow_blank=False,min_length=8)
    class Meta:
        model=User
        fields=('id','uuid','full_name','email','phone','role','is_active','is_staff','is_superuser','password','created_at','updated_at')
        read_only_fields=('id','uuid','is_superuser','created_at','updated_at')
    def validate_role(self,value):
        if value==UserRole.CUSTOMER:
            raise serializers.ValidationError('Customer role is not a staff dashboard role.')
        return value
    def create(self,validated_data):
        password=validated_data.pop('password',None)
        validated_data['is_staff']=True
        user=User.objects.create_user(password=password,**validated_data)
        return user
    def update(self,instance,validated_data):
        password=validated_data.pop('password',None)
        if instance.is_superuser and 'role' in validated_data:
            validated_data['role']=UserRole.SUPER_ADMIN
        for key,value in validated_data.items():
            setattr(instance,key,value)
        instance.is_staff=True
        if password:
            instance.set_password(password)
        instance.save()
        return instance

class StaffUserViewSet(ModelViewSet):
    permission_classes=[StaffAdmin]
    serializer_class=StaffUserSerializer
    http_method_names=['get','post','patch','delete','head','options']
    search_fields=('full_name','phone','email')
    filterset_fields=('role','is_active')
    ordering_fields=('created_at','full_name','role')
    def get_queryset(self):
        return User.objects.filter(is_staff=True).exclude(role=UserRole.CUSTOMER).order_by('-is_superuser','full_name','id')
    def perform_destroy(self,instance):
        if instance.pk==self.request.user.pk:
            raise ValidationError({'user':'You cannot delete your own staff account.'})
        if instance.is_superuser:
            raise ValidationError({'user':'Superusers cannot be deleted from the dashboard.'})
        instance.delete()

class GlobalSearchView(APIView):
    permission_classes=[SearchAdmin]
    def get(self,request):
        query=request.query_params.get('q','').strip()
        if len(query)<2:
            return success([])
        results=[]
        def add(type_,id_,title,subtitle,url):
            if len(results)<30:
                results.append({'type':type_,'id':id_,'title':title,'subtitle':subtitle or '', 'url':url})
        for row in Order.objects.filter(Q(order_number__icontains=query)|Q(customer_name__icontains=query)|Q(customer_phone__icontains=query)|Q(items__sku_snapshot__icontains=query)).distinct().order_by('-created_at')[:6]:
            add('order',row.id,row.order_number,f'{row.customer_name} · {row.customer_phone}',f'/sales/orders/{row.order_number}')
        for row in User.objects.filter(role=UserRole.CUSTOMER).filter(Q(full_name__icontains=query)|Q(phone__icontains=query)|Q(email__icontains=query)).order_by('-id')[:5]:
            add('customer',row.id,row.full_name or row.phone or row.email or f'Customer #{row.id}',row.phone or row.email or '',f'/customers/{row.id}')
        for row in Product.objects.filter(Q(name__icontains=query)|Q(sku__icontains=query)|Q(barcode__icontains=query)|Q(variants__sku__icontains=query)).distinct().order_by('-id')[:6]:
            add('product',row.id,row.name,row.sku or 'Variable product',f'/catalog/products/{row.id}/edit')
        for row in ProductVariant.objects.select_related('product').filter(Q(sku__icontains=query)|Q(barcode__icontains=query)|Q(product__name__icontains=query)).order_by('-id')[:4]:
            add('variant',row.id,row.sku,row.product.name,f'/catalog/variants?product={row.product_id}')
        for row in Supplier.objects.filter(Q(name__icontains=query)|Q(phone__icontains=query)|Q(email__icontains=query))[:4]:
            add('supplier',row.id,row.name,row.phone or row.email or '',f'/procurement/suppliers?search={query}')
        for row in Purchase.objects.select_related('supplier').filter(Q(purchase_number__icontains=query)|Q(supplier_invoice__icontains=query)|Q(supplier__name__icontains=query)).order_by('-id')[:4]:
            add('purchase',row.id,row.purchase_number,row.supplier.name,f'/procurement/purchases/{row.id}')
        for row in Coupon.objects.filter(code__icontains=query)[:3]:
            add('coupon',row.id,row.code,row.coupon_type,'/marketing/coupons')
        for row in Shipment.objects.select_related('order').filter(Q(tracking_code__icontains=query)|Q(order__order_number__icontains=query)|Q(courier__icontains=query)).order_by('-id')[:4]:
            add('shipment',row.id,row.tracking_code or f'Shipment #{row.id}',f'{row.courier} · {row.order.order_number}','/sales/shipments')
        return success(results)
