from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import CouponAdminViewSet,PromotionAdminViewSet,CampaignAdminViewSet
r=DefaultRouter(); r.register("coupons",CouponAdminViewSet,basename="admin-coupons"); r.register("promotions",PromotionAdminViewSet,basename="admin-promotions"); r.register("campaigns",CampaignAdminViewSet,basename="admin-campaigns"); urlpatterns=[path("",include(r.urls))]
