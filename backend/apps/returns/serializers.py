from rest_framework import serializers
from apps.orders.models import Order,OrderItem
from apps.inventory.models import Warehouse
from apps.payments.models import Payment
from .models import ReturnRequest,ReturnItem,Refund
class ReturnItemSerializer(serializers.ModelSerializer):
    class Meta: model=ReturnItem; fields=("id","order_item","quantity","reason","restock")
class ReturnRequestSerializer(serializers.ModelSerializer):
    items=ReturnItemSerializer(many=True,read_only=True)
    class Meta: model=ReturnRequest; fields="__all__"; read_only_fields=("user","reviewed_by","status")
class CreateReturnSerializer(serializers.Serializer):
    order=serializers.PrimaryKeyRelatedField(queryset=Order.objects.all()); reason=serializers.CharField(); items=serializers.ListField(child=serializers.DictField(),allow_empty=False)
    def validate_items(self,rows):
        out=[]
        for row in rows:
            try: oi=OrderItem.objects.get(pk=row.get("order_item"))
            except OrderItem.DoesNotExist: raise serializers.ValidationError("Invalid order item.")
            out.append({"order_item":oi,"quantity":int(row.get("quantity",0)),"reason":row.get("reason",""),"restock":bool(row.get("restock",True))})
        return out
class ReceiveReturnSerializer(serializers.Serializer): warehouse=serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.filter(is_active=True))
class RefundSerializer(serializers.ModelSerializer):
    class Meta: model=Refund; fields="__all__"; read_only_fields=("created_by","completed_at")
class CreateRefundSerializer(serializers.Serializer): payment=serializers.PrimaryKeyRelatedField(queryset=Payment.objects.all()); amount=serializers.DecimalField(max_digits=14,decimal_places=2); reason=serializers.CharField(required=False,allow_blank=True)
