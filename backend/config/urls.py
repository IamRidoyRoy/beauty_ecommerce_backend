from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path,include
from drf_spectacular.views import SpectacularAPIView,SpectacularSwaggerView,SpectacularRedocView
urlpatterns=[
    path("django-admin/",admin.site.urls),
    path("api/schema/",SpectacularAPIView.as_view(),name="schema"),
    path("api/docs/",SpectacularSwaggerView.as_view(url_name="schema"),name="swagger-ui"),
    path("api/redoc/",SpectacularRedocView.as_view(url_name="schema"),name="redoc"),
    path("api/v1/auth/",include("apps.accounts.urls")),
    path("api/v1/",include("apps.catalog.urls")), path("api/v1/",include("apps.carts.urls")), path("api/v1/",include("apps.promotions.urls")),
    path("api/v1/",include("apps.orders.urls")), path("api/v1/",include("apps.shipping.urls")), path("api/v1/",include("apps.delivery.urls")), path("api/v1/",include("apps.returns.urls")), path("api/v1/",include("apps.reviews.urls")), path("api/v1/",include("apps.common.urls")),
    path("api/v1/admin/",include("apps.common.admin_urls")), path("api/v1/admin/",include("apps.catalog.admin_urls")), path("api/v1/admin/inventory/",include("apps.inventory.admin_urls")),
    path("api/v1/admin/",include("apps.orders.admin_urls")), path("api/v1/admin/",include("apps.delivery.admin_urls")), path("api/v1/admin/",include("apps.promotions.admin_urls")), path("api/v1/admin/",include("apps.payments.admin_urls")), path("api/v1/admin/",include("apps.shipping.admin_urls")), path("api/v1/admin/",include("apps.returns.admin_urls")), path("api/v1/admin/",include("apps.reviews.admin_urls")), path("api/v1/admin/",include("apps.reports.admin_urls")),
]
if settings.DEBUG: urlpatterns += static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)
