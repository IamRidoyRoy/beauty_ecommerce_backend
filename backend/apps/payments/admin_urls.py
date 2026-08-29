from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdminPaymentGatewayConfigViewSet, AdminPaymentViewSet

r = DefaultRouter()
r.register("payments", AdminPaymentViewSet, basename="admin-payments")
r.register("payment-gateways", AdminPaymentGatewayConfigViewSet, basename="admin-payment-gateways")
urlpatterns = [path("", include(r.urls))]
