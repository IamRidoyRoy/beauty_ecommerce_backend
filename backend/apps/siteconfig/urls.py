from django.urls import path
from .views import SiteBrandingPublicView

urlpatterns = [path("site-settings/", SiteBrandingPublicView.as_view())]
