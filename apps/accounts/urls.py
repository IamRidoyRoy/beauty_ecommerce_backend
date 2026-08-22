from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView
from .views import LoginView,OTPRequestView,OTPVerifyView,GoogleAuthExtensionView,MeView,SetPasswordView,AddressViewSet
r=DefaultRouter(); r.register("addresses", AddressViewSet, basename="address")
urlpatterns=[path("login/",LoginView.as_view()),path("otp/request/",OTPRequestView.as_view()),path("otp/verify/",OTPVerifyView.as_view()),path("google/",GoogleAuthExtensionView.as_view()),path("refresh/",TokenRefreshView.as_view()),path("logout/",TokenBlacklistView.as_view()),path("me/",MeView.as_view()),path("set-password/",SetPasswordView.as_view()),path("",include(r.urls))]
