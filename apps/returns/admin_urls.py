from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import AdminReturnViewSet,AdminRefundViewSet
r=DefaultRouter(); r.register("returns",AdminReturnViewSet,basename="admin-returns"); r.register("refunds",AdminRefundViewSet,basename="admin-refunds"); urlpatterns=[path("",include(r.urls))]
