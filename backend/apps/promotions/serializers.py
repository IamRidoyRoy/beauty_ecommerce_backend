from rest_framework import serializers
from .models import Coupon,Promotion
class CouponSerializer(serializers.ModelSerializer):
    class Meta: model=Coupon; fields="__all__"; read_only_fields=("used_count",)
class PromotionSerializer(serializers.ModelSerializer):
    class Meta: model=Promotion; fields="__all__"
class CouponValidateSerializer(serializers.Serializer): code=serializers.CharField(max_length=60)
