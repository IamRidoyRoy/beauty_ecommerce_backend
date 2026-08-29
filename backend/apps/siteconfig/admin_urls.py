from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import HomepageBannerAdminViewSet, SiteBrandingAdminView

router = DefaultRouter()
router.register("homepage-banners", HomepageBannerAdminViewSet, basename="admin-homepage-banners")

urlpatterns = [
    path("site-settings/", SiteBrandingAdminView.as_view()),
    path("", include(router.urls)),
]
