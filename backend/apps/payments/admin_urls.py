from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import AdminPaymentViewSet
r=DefaultRouter(); r.register("payments",AdminPaymentViewSet,basename="admin-payments"); urlpatterns=[path("",include(r.urls))]
