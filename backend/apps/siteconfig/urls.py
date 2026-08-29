from django.urls import path
from .views import AnnouncementItemPublicView, HomepageBannerPublicView, SiteBrandingPublicView

urlpatterns = [
    path("site-settings/", SiteBrandingPublicView.as_view()),
    path("homepage-banners/", HomepageBannerPublicView.as_view()),
    path("announcement-items/", AnnouncementItemPublicView.as_view()),
]
