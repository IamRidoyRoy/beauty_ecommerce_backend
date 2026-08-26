from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import AnnouncementMessageAdminViewSet, CheckoutSettingsAdminView, DemoImportView, GlobalSearchView, HeroSlideAdminViewSet, StaffUserViewSet

router=DefaultRouter()
router.register('staff-users',StaffUserViewSet,basename='admin-staff-users')
router.register('hero-slides',HeroSlideAdminViewSet,basename='admin-hero-slides')
router.register('announcement-messages',AnnouncementMessageAdminViewSet,basename='admin-announcement-messages')

urlpatterns=[
    path('',include(router.urls)),
    path('demo/import/',DemoImportView.as_view()),
    path('global-search/',GlobalSearchView.as_view()),
    path('checkout-settings/',CheckoutSettingsAdminView.as_view()),
]
