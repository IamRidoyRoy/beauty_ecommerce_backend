from django.urls import path

from .views import TrackingConfigView, TrackingEventView

urlpatterns = [
    path("tracking/config/", TrackingConfigView.as_view()),
    path("tracking/events/", TrackingEventView.as_view()),
]
