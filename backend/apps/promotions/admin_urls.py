from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import CouponAdminViewSet,PromotionAdminViewSet
r=DefaultRouter(); r.register("coupons",CouponAdminViewSet,basename="admin-coupons"); r.register("promotions",PromotionAdminViewSet,basename="admin-promotions"); urlpatterns=[path("",include(r.urls))]
