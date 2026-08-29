from django.urls import path

from .views import (
    BKashCallbackView,
    GenericGatewayWebhookView,
    NagadCallbackView,
    PaymentInitiateView,
    PublicPaymentMethodsView,
    SSLCommerzCancelView,
    SSLCommerzFailView,
    SSLCommerzIPNView,
    SSLCommerzSuccessView,
)

urlpatterns = [
    path("payment-methods/", PublicPaymentMethodsView.as_view(), name="payment-methods"),
    path("payments/<uuid:public_token>/initiate/", PaymentInitiateView.as_view(), name="payment-initiate"),
    path("payments/sslcommerz/callback/success/", SSLCommerzSuccessView.as_view(), name="sslcommerz-success"),
    path("payments/sslcommerz/callback/fail/", SSLCommerzFailView.as_view(), name="sslcommerz-fail"),
    path("payments/sslcommerz/callback/cancel/", SSLCommerzCancelView.as_view(), name="sslcommerz-cancel"),
    path("payments/sslcommerz/callback/ipn/", SSLCommerzIPNView.as_view(), name="sslcommerz-ipn"),
    path("payments/bkash/callback/", BKashCallbackView.as_view(), name="bkash-callback"),
    path("payments/nagad/callback/", NagadCallbackView.as_view(), name="nagad-callback"),
    path("payments/webhooks/<str:provider>/", GenericGatewayWebhookView.as_view(), name="payment-webhook"),
]
