from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import CheckoutSettingsAdminView, DemoImportView, GlobalSearchView, StaffUserViewSet

router=DefaultRouter()
router.register('staff-users',StaffUserViewSet,basename='admin-staff-users')

urlpatterns=[
    path('',include(router.urls)),
    path('demo/import/',DemoImportView.as_view()),
    path('global-search/',GlobalSearchView.as_view()),
    path('checkout-settings/',CheckoutSettingsAdminView.as_view()),
]
