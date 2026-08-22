from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet,CategoryViewSet,BrandViewSet,WishlistView
r=DefaultRouter(); r.register("products",ProductViewSet,basename="product"); r.register("categories",CategoryViewSet,basename="category"); r.register("brands",BrandViewSet,basename="brand")
urlpatterns=[path("wishlist/",WishlistView.as_view()),path("",include(r.urls))]
