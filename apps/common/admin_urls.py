from django.urls import path
from .views import DemoImportView
urlpatterns=[path("demo/import/",DemoImportView.as_view())]
