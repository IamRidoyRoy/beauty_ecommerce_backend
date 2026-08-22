from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdminDeliveryModuleViewSet, AdminDistrictViewSet, AdminThanaViewSet

router = DefaultRouter()
router.register("delivery/modules", AdminDeliveryModuleViewSet, basename="admin-delivery-modules")
router.register("delivery/districts", AdminDistrictViewSet, basename="admin-delivery-districts")
router.register("delivery/thanas", AdminThanaViewSet, basename="admin-delivery-thanas")

urlpatterns = [path("", include(router.urls))]
