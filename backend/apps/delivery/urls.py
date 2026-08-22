from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DeliveryModuleViewSet, DeliveryQuoteViewSet, DistrictViewSet, ThanaViewSet

router = DefaultRouter()
router.register("districts", DistrictViewSet, basename="districts")
router.register("thanas", ThanaViewSet, basename="thanas")
router.register("delivery-modules", DeliveryModuleViewSet, basename="delivery-modules")
router.register("delivery-charge", DeliveryQuoteViewSet, basename="delivery-charge")

urlpatterns = [path("", include(router.urls))]
