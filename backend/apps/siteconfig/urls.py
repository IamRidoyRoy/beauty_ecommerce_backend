from django.urls import path
from .views import HomepageBannerPublicView, SiteBrandingPublicView

urlpatterns = [
    path("site-settings/", SiteBrandingPublicView.as_view()),
    path("homepage-banners/", HomepageBannerPublicView.as_view()),
]
