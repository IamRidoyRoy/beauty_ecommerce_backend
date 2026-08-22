from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import ReviewViewSet
r=DefaultRouter(); r.register("reviews",ReviewViewSet,basename="reviews"); urlpatterns=[path("",include(r.urls))]
