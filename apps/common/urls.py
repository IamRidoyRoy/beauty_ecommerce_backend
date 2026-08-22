from django.urls import path
from .views import AnalyticsEventView
urlpatterns=[path("analytics/events/",AnalyticsEventView.as_view())]
