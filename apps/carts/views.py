from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from apps.common.responses import success
from apps.common.models import AnalyticsEvent
from .models import CartItem
from .serializers import CartSerializer,CartItemSerializer
from .services import get_request_cart,add_cart_item,update_cart_item,remove_cart_item
class CartView(APIView):
    permission_classes=[AllowAny]
    def get(self,request):
        cart=get_request_cart(request); cart=type(cart).objects.prefetch_related("items__product__images","items__product_variant__product__images","items__product_variant__attributes__attribute").get(pk=cart.pk)
        return success(CartSerializer(cart,context={"request":request}).data)
class CartItemListView(APIView):
    permission_classes=[AllowAny]
    def post(self,request):
        cart=get_request_cart(request); s=CartItemSerializer(data=request.data); s.is_valid(raise_exception=True)
        item=add_cart_item(cart=cart,product=s.validated_data.get("product"),product_variant=s.validated_data.get("product_variant"),quantity=s.validated_data.get("quantity",1))
        target_product=item.product_id or item.product_variant.product_id
        AnalyticsEvent.objects.create(event_type=AnalyticsEvent.EventType.ADD_TO_CART,user=request.user if request.user.is_authenticated else None,cart_token=str(cart.token),product_id_ref=target_product)
        return success({"cart_token":str(cart.token),"item":CartItemSerializer(item).data},"Item added.",201)
class CartItemDetailView(APIView):
    permission_classes=[AllowAny]
    def _item(self,request,pk): return get_object_or_404(CartItem.objects.select_related("product","product_variant__product").prefetch_related("product_variant__attributes__attribute"),pk=pk,cart=get_request_cart(request))
    def patch(self,request,pk):
        item=self._item(request,pk); quantity=request.data.get("quantity");
        if quantity is None: from rest_framework.exceptions import ValidationError; raise ValidationError({"quantity":"This field is required."})
        return success(CartItemSerializer(update_cart_item(item=item,quantity=int(quantity))).data,"Cart updated.")
    def delete(self,request,pk): remove_cart_item(item=self._item(request,pk)); return success(message="Item removed.")
