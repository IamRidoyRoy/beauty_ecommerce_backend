from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import AdminReviewViewSet
r=DefaultRouter(); r.register("reviews",AdminReviewViewSet,basename="admin-reviews"); urlpatterns=[path("",include(r.urls))]
