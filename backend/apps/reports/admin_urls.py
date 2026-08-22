from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import DashboardView,ReportView,ReportExportViewSet
r=DefaultRouter(); r.register("reports/exports",ReportExportViewSet,basename="report-exports")
urlpatterns=[path("",include(r.urls)),path("dashboard/",DashboardView.as_view()),path("reports/",ReportView.as_view()),path("reports/<slug:report>/",ReportView.as_view())]
