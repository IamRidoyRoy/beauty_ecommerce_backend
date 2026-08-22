from rest_framework.viewsets import ModelViewSet,ReadOnlyModelViewSet
from rest_framework.decorators import action
from rest_framework.views import APIView
from apps.accounts.models import UserRole
from apps.common.permissions import role_permission
from apps.common.responses import success
from .models import *
from .serializers import *
from .services import receive_purchase,approve_purchase,cancel_purchase,transfer_stock,adjust_stock
InventoryAdmin=role_permission(UserRole.SUPER_ADMIN,UserRole.ADMIN,UserRole.MANAGER,UserRole.INVENTORY_MANAGER)
class WarehouseViewSet(ModelViewSet): permission_classes=[InventoryAdmin]; serializer_class=WarehouseSerializer; queryset=Warehouse.objects.all()
class SupplierViewSet(ModelViewSet): permission_classes=[InventoryAdmin]; serializer_class=SupplierSerializer; queryset=Supplier.objects.all(); search_fields=("name","phone","email")
class InventoryViewSet(ReadOnlyModelViewSet):
    permission_classes=[InventoryAdmin]; serializer_class=ProductStockSerializer
    queryset=ProductStock.objects.select_related("warehouse","stock_item__product","stock_item__variant__product").order_by("stock_item_id","warehouse_id")
    filterset_fields=("warehouse","stock_item"); ordering_fields=("available_stock","reserved_stock","updated_at")
class StockMovementViewSet(ReadOnlyModelViewSet):
    permission_classes=[InventoryAdmin]; serializer_class=StockMovementSerializer
    queryset=StockMovement.objects.select_related("stock_item","warehouse","created_by").order_by("-created_at"); filterset_fields=("stock_item","warehouse","movement_type","reference_type","reference_id")
class PurchaseViewSet(ModelViewSet):
    permission_classes=[InventoryAdmin]; serializer_class=PurchaseSerializer
    queryset=Purchase.objects.select_related("supplier","warehouse","created_by","approved_by","received_by").prefetch_related("items__product","items__product_variant__product").order_by("-id")
    filterset_fields=("status","supplier","warehouse"); search_fields=("purchase_number","supplier_invoice","supplier__name")
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
    permission_classes=[InventoryAdmin]; serializer_class=PurchaseItemSerializer; queryset=PurchaseItem.objects.select_related("purchase","product","product_variant__product").all(); filterset_fields=("purchase",)
class TransferStockView(APIView):
    permission_classes=[InventoryAdmin]
    def post(self,request):
        s=TransferSerializer(data=request.data); s.is_valid(raise_exception=True); transfer_stock(**s.validated_data,created_by=request.user); return success(message="Stock transferred.")
class AdjustStockView(APIView):
    permission_classes=[InventoryAdmin]
    def post(self,request):
        s=AdjustStockSerializer(data=request.data); s.is_valid(raise_exception=True); stock=adjust_stock(**s.validated_data,created_by=request.user); return success(ProductStockSerializer(stock).data,"Stock adjusted.")
