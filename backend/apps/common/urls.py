from django.urls import path
from .views import AnalyticsEventView, AnnouncementMessageListView, HeroSlideListView
urlpatterns=[path("analytics/events/",AnalyticsEventView.as_view()), path("hero-slides/",HeroSlideListView.as_view()), path("announcement-messages/",AnnouncementMessageListView.as_view())]
