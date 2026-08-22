from rest_framework import serializers
from .models import Review,ReviewImage
class ReviewImageSerializer(serializers.ModelSerializer):
    class Meta: model=ReviewImage; fields=("id","image","order")
class ReviewSerializer(serializers.ModelSerializer):
    images=ReviewImageSerializer(many=True,read_only=True); user_name=serializers.CharField(source="user.full_name",read_only=True)
    class Meta: model=Review; fields=("id","user","user_name","product","order_item","rating","title","comment","status","verified_purchase","images","created_at"); read_only_fields=("user","status","verified_purchase")
    def validate(self,attrs):
        oi=attrs.get("order_item"); product=attrs.get("product")
        if oi and oi.product_id!=product.id: raise serializers.ValidationError({"order_item":"Order item does not match product."})
        request=self.context.get("request")
        if oi and request and request.user.is_authenticated and oi.order.user_id!=request.user.id: raise serializers.ValidationError({"order_item":"Order item does not belong to this customer."})
        return attrs

class AdminReviewSerializer(serializers.ModelSerializer):
    images=ReviewImageSerializer(many=True,read_only=True)
    class Meta: model=Review; fields="__all__"; read_only_fields=("verified_purchase",)
