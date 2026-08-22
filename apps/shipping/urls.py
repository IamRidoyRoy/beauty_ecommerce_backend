from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import ShippingMethodViewSet
r=DefaultRouter(); r.register("shipping-methods",ShippingMethodViewSet,basename="shipping-methods"); urlpatterns=[path("",include(r.urls))]
