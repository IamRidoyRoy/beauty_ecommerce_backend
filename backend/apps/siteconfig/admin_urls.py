from django.urls import path
from .views import SiteBrandingAdminView

urlpatterns = [path("site-settings/", SiteBrandingAdminView.as_view())]
