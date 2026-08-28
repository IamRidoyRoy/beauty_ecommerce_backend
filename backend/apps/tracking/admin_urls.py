from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TrackingEventLogAdminViewSet, TrackingSettingsAdminView, TrackingTestView

router = DefaultRouter()
router.register("tracking/events", TrackingEventLogAdminViewSet, basename="admin-tracking-events")

urlpatterns = [
    path("", include(router.urls)),
    path("tracking/settings/", TrackingSettingsAdminView.as_view()),
    path("tracking/test/", TrackingTestView.as_view()),
]
