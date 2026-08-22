from rest_framework import serializers
from .models import ShippingMethod,Shipment
class ShippingMethodSerializer(serializers.ModelSerializer):
    class Meta: model=ShippingMethod; fields=("id","name","code","base_charge","estimated_days","free_threshold","active")
class ShipmentSerializer(serializers.ModelSerializer):
    class Meta: model=Shipment; fields="__all__"
