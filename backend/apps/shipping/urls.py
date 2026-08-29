from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CourierWebhookView, ShippingMethodViewSet

r = DefaultRouter()
r.register("shipping-methods", ShippingMethodViewSet, basename="shipping-methods")
urlpatterns = [
    path("", include(r.urls)),
    path("courier/webhooks/<str:provider>/", CourierWebhookView.as_view(), name="courier-webhook"),
]
