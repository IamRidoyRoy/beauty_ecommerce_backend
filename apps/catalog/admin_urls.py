from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import *
r=DefaultRouter(); r.register("products",AdminProductViewSet,basename="admin-products"); r.register("variants",AdminVariantViewSet,basename="admin-variants"); r.register("categories",AdminCategoryViewSet,basename="admin-categories"); r.register("brands",AdminBrandViewSet,basename="admin-brands"); r.register("images",AdminImageViewSet,basename="admin-images"); r.register("attributes",AdminAttributeViewSet,basename="admin-attributes"); r.register("attribute-values",AdminAttributeValueViewSet,basename="admin-attribute-values"); r.register("claims",AdminClaimViewSet,basename="admin-claims"); r.register("product-claims",AdminProductClaimViewSet,basename="admin-product-claims"); r.register("beauty-profiles",AdminBeautyProfileViewSet,basename="admin-beauty-profiles")
urlpatterns=[path("images/bulk-upload/",BulkImageUploadView.as_view()),path("",include(r.urls))]
