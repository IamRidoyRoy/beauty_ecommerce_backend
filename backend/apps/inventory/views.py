from django.db.models import Q,F
from rest_framework.viewsets import ModelViewSet,ReadOnlyModelViewSet
from rest_framework.decorators import action
from rest_framework.views import APIView
from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from apps.common.responses import success
from .models import *
from .serializers import *
from .services import receive_purchase,approve_purchase,cancel_purchase,transfer_stock,adjust_stock,resolve_stock_item
InventoryAdmin=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.INVENTORY_MANAGER)
class WarehouseViewSet(ModelViewSet):
    permission_classes=[InventoryAdmin]
    serializer_class=WarehouseSerializer
    queryset=Warehouse.objects.all().order_by("name")
    search_fields=("name","code","address")
    filterset_fields=("is_active",)
    ordering_fields=("name","code","created_at")
class SupplierViewSet(ModelViewSet): permission_classes=[InventoryAdmin]; serializer_class=SupplierSerializer; queryset=Supplier.objects.all(); search_fields=("name","contact_person","phone","email","address"); filterset_fields=("is_active",); ordering_fields=("name","created_at")
class InventoryViewSet(ReadOnlyModelViewSet):
    permission_classes=[InventoryAdmin]; serializer_class=ProductStockSerializer
    queryset=ProductStock.objects.select_related("warehouse","stock_item__product__brand","stock_item__product__category","stock_item__variant__product__brand","stock_item__variant__product__category").prefetch_related("stock_item__variant__attributes").order_by("stock_item_id","warehouse_id")
    filterset_fields=("warehouse","stock_item"); ordering_fields=("available_stock","reserved_stock","updated_at","incoming_stock")
    def get_queryset(self):
        qs=super().get_queryset(); p=self.request.query_params; search=p.get("search","").strip(); brand=p.get("brand"); category=p.get("category")
        if search: qs=qs.filter(Q(stock_item__product__name__icontains=search)|Q(stock_item__product__sku__icontains=search)|Q(stock_item__variant__product__name__icontains=search)|Q(stock_item__variant__sku__icontains=search))
        if brand: qs=qs.filter(Q(stock_item__product__brand_id=brand)|Q(stock_item__variant__product__brand_id=brand))
        if category: qs=qs.filter(Q(stock_item__product__category_id=category)|Q(stock_item__variant__product__category_id=category))
        if p.get("low_stock") in {"true","True","1"}: qs=qs.filter(available_stock__lte=F("low_stock_threshold"))
        if p.get("out_of_stock") in {"true","True","1"}: qs=qs.filter(available_stock__lte=0)
        return qs.distinct()
class StockMovementViewSet(ReadOnlyModelViewSet):
    permission_classes=[InventoryAdmin]; serializer_class=StockMovementSerializer
    queryset=StockMovement.objects.select_related("stock_item__product","stock_item__variant__product","warehouse","created_by").order_by("-created_at"); filterset_fields=("stock_item","warehouse","movement_type","reference_type","reference_id"); search_fields=("note","reference_type","reference_id","stock_item__product__name","stock_item__product__sku","stock_item__variant__sku"); ordering_fields=("created_at","quantity")
class PurchaseViewSet(ModelViewSet):
    permission_classes=[InventoryAdmin]; serializer_class=PurchaseSerializer
    queryset=Purchase.objects.select_related("supplier","warehouse","created_by","approved_by","received_by").prefetch_related("items__product__images","items__product_variant__product__images","items__product_variant__images","items__product_variant__attributes__attribute").order_by("-id")
    filterset_fields=("status","supplier","warehouse"); search_fields=("purchase_number","supplier_invoice","supplier__name"); ordering_fields=("created_at","purchase_date","total","expected_date")
    def perform_create(self,serializer): serializer.save(created_by=self.request.user)
    @action(detail=True,methods=["post"])
    def approve(self,request,pk=None): return success(PurchaseSerializer(approve_purchase(purchase=self.get_object(),user=request.user),context={"request":request}).data,"Purchase approved.")
    @action(detail=True,methods=["post"])
    def cancel(self,request,pk=None): return success(PurchaseSerializer(cancel_purchase(purchase=self.get_object(),user=request.user),context={"request":request}).data,"Purchase cancelled.")
    @action(detail=True,methods=["post"])
    def receive(self,request,pk=None):
        s=ReceivePurchaseSerializer(data=request.data); s.is_valid(raise_exception=True)
        obj=receive_purchase(purchase=self.get_object(),receipts=s.validated_data["receipts"],user=request.user)
        return success(PurchaseSerializer(obj,context={"request":request}).data,"Purchase received.")
class PurchaseItemViewSet(ModelViewSet):
    permission_classes=[InventoryAdmin]; serializer_class=PurchaseItemSerializer; queryset=PurchaseItem.objects.select_related("purchase","product","product_variant__product").prefetch_related("product__images","product_variant__product__images","product_variant__images","product_variant__attributes__attribute").all(); filterset_fields=("purchase",)
class TransferStockView(APIView):
    permission_classes=[InventoryAdmin]
    def post(self,request):
        s=TransferSerializer(data=request.data); s.is_valid(raise_exception=True); transfer_stock(**s.validated_data,created_by=request.user); return success(message="Stock transferred.")
class AdjustStockView(APIView):
    permission_classes=[InventoryAdmin]
    def post(self,request):
        s=AdjustStockSerializer(data=request.data); s.is_valid(raise_exception=True); stock=adjust_stock(**s.validated_data,created_by=request.user); return success(ProductStockSerializer(stock).data,"Stock adjusted.")

class ResolveStockItemView(APIView):
    permission_classes=[InventoryAdmin]
    def post(self,request):
        from apps.catalog.models import Product,ProductVariant
        from rest_framework.exceptions import ValidationError
        product_id=request.data.get('product'); variant_id=request.data.get('variant')
        if bool(product_id)==bool(variant_id): raise ValidationError({'target':'Exactly one of product or variant is required.'})
        product=Product.objects.filter(pk=product_id).first() if product_id else None
        variant=ProductVariant.objects.filter(pk=variant_id).first() if variant_id else None
        if product_id and not product: raise ValidationError({'product':'Product not found.'})
        if variant_id and not variant: raise ValidationError({'variant':'Variant not found.'})
        item=resolve_stock_item(product=product,variant=variant)
        return success(StockItemSerializer(item).data)

class InventoryThresholdView(APIView):
    permission_classes=[InventoryAdmin]
    def patch(self,request,pk):
        from rest_framework.exceptions import NotFound,ValidationError
        stock=ProductStock.objects.filter(pk=pk).first()
        if not stock: raise NotFound('Stock row not found.')
        fields=[]
        for name in ('low_stock_threshold','reorder_level'):
            if name in request.data and request.data[name] is not None:
                value=int(request.data[name])
                if value<0: raise ValidationError({name:'Cannot be negative.'})
                setattr(stock,name,value); fields.append(name)
        if fields: stock.save(update_fields=fields+['updated_at'])
        return success(ProductStockSerializer(stock).data,'Inventory thresholds updated.')
