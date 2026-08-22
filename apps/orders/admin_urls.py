from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import AdminOrderViewSet,AdminCustomerViewSet
r=DefaultRouter(); r.register("orders",AdminOrderViewSet,basename="admin-orders"); r.register("customers",AdminCustomerViewSet,basename="admin-customers")
urlpatterns=[path("",include(r.urls))]
