from django.urls import path
from .views import CouponValidateView
urlpatterns=[path("coupons/validate/",CouponValidateView.as_view())]
