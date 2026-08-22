from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import AdminShippingMethodViewSet,AdminShipmentViewSet
r=DefaultRouter(); r.register("shipping",AdminShippingMethodViewSet,basename="admin-shipping"); r.register("shipments",AdminShipmentViewSet,basename="admin-shipments"); urlpatterns=[path("",include(r.urls))]
