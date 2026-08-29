from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdminCourierConfigViewSet, AdminShipmentViewSet, AdminShippingMethodViewSet

r = DefaultRouter()
r.register("shipping", AdminShippingMethodViewSet, basename="admin-shipping")
r.register("shipments", AdminShipmentViewSet, basename="admin-shipments")
r.register("courier-configs", AdminCourierConfigViewSet, basename="admin-courier-configs")
urlpatterns = [path("", include(r.urls))]
