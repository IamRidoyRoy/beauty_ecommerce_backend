from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import CheckoutView,MyOrderViewSet
r=DefaultRouter(); r.register("orders",MyOrderViewSet,basename="my-orders")
urlpatterns=[path("checkout/",CheckoutView.as_view()),path("",include(r.urls))]
