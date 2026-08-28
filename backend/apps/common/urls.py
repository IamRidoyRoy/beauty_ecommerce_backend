from django.urls import path
from .views import AnalyticsEventView, HeroSlideListView
urlpatterns=[path("analytics/events/",AnalyticsEventView.as_view()), path("hero-slides/",HeroSlideListView.as_view())]
