from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from apps.common.responses import success
from apps.carts.services import get_request_cart
from .models import Coupon,Promotion
from .serializers import CouponSerializer,PromotionSerializer,CouponValidateSerializer
from .services import validate_coupon
class CouponValidateView(APIView):
    permission_classes=[AllowAny]
    def post(self,request):
        s=CouponValidateSerializer(data=request.data); s.is_valid(raise_exception=True); cart=get_request_cart(request,create=False)
        if not cart:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"cart":"Cart is required."})
        result=validate_coupon(code=s.validated_data["code"],cart=cart,user=request.user if request.user.is_authenticated else None)
        return success({"code":result["coupon"].code,"discount":str(result["discount"]),"free_shipping":result["free_shipping"]},"Coupon is valid.")
Marketing=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.MARKETING_MANAGER)
class CouponAdminViewSet(ModelViewSet): permission_classes=[Marketing]; serializer_class=CouponSerializer; queryset=Coupon.objects.prefetch_related("brands","categories","products","customers").all(); search_fields=("code",); filterset_fields=("coupon_type","active","first_order_only")
class PromotionAdminViewSet(ModelViewSet): permission_classes=[Marketing]; serializer_class=PromotionSerializer; queryset=Promotion.objects.prefetch_related("brands","categories","products").all(); filterset_fields=("promotion_type","active","combinable"); search_fields=("name","code"); ordering_fields=("priority","starts_at","ends_at")


class CampaignAdminViewSet(PromotionAdminViewSet):
    """Dedicated campaign endpoint so Campaign access can be granted without exposing all promotions."""
    def get_queryset(self):
        return super().get_queryset().filter(config__campaign=True)

    def perform_create(self, serializer):
        config = dict(serializer.validated_data.get("config") or {})
        config["campaign"] = True
        serializer.save(config=config)
