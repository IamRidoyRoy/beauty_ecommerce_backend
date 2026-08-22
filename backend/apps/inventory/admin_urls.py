from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import *
r=DefaultRouter(); r.register("warehouses",WarehouseViewSet,basename="warehouses"); r.register("suppliers",SupplierViewSet,basename="suppliers"); r.register("purchases",PurchaseViewSet,basename="purchases"); r.register("purchase-items",PurchaseItemViewSet,basename="purchase-items"); r.register("movements",StockMovementViewSet,basename="movements")
inventory_list=InventoryViewSet.as_view({"get":"list"})
urlpatterns=[path("",inventory_list,name="inventory-list"),path("transfer/",TransferStockView.as_view()),path("adjust/",AdjustStockView.as_view()),path("",include(r.urls))]
