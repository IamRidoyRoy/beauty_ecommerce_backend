from pathlib import Path
from datetime import timedelta
import os

BASE_DIR = Path(__file__).resolve().parents[2]
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
DEBUG = False
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "django.contrib.staticfiles",
    "corsheaders", "rest_framework", "rest_framework_simplejwt.token_blacklist", "django_filters", "drf_spectacular",
    "apps.common", "apps.siteconfig", "apps.accesscontrol", "apps.accounts", "apps.catalog", "apps.inventory", "apps.carts", "apps.promotions",
    "apps.orders", "apps.payments", "apps.shipping", "apps.delivery", "apps.returns", "apps.reviews", "apps.reports", "apps.notifications", "apps.tracking",
]
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware", "django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
              "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
AUTH_USER_MODEL = "accounts.User"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ("apps.common.renderers.EnvelopeJSONRenderer", "rest_framework.renderers.BrowsableAPIRenderer"),
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend", "rest_framework.filters.SearchFilter", "rest_framework.filters.OrderingFilter"),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 24,
    "DEFAULT_THROTTLE_RATES": {"auth": "20/hour", "otp": "5/10min"},
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Beauty E-commerce API", "DESCRIPTION": "Commercial storefront + management API supporting native simple and variable products.",
    "VERSION": "1.0.0", "SERVE_INCLUDE_SCHEMA": False,
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30), "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True, "BLACKLIST_AFTER_ROTATION": True, "UPDATE_LAST_LOGIN": True,
}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
from corsheaders.defaults import default_headers
CORS_ALLOW_HEADERS = (*default_headers, "x-cart-token")

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@example.com")
SMS_BACKEND = os.getenv("SMS_BACKEND", "")
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_BEAT_SCHEDULE = {
    "low-stock-hourly": {"task": "apps.notifications.tasks.low_stock_alerts", "schedule": 3600.0},
    "trending-every-6h": {"task": "apps.catalog.tasks.recalculate_trending", "schedule": 21600.0},
    "payment-reconciliation-every-10m": {"task": "apps.payments.tasks.reconcile_open_gateway_payments", "schedule": 600.0},
    "courier-auto-book-every-minute": {"task": "apps.shipping.tasks.auto_book_courier_orders", "schedule": 60.0},
    "courier-tracking-sync-every-5m": {"task": "apps.shipping.tasks.sync_courier_shipments", "schedule": 300.0},
    "courier-delivered-order-reconcile-every-minute": {"task": "apps.shipping.tasks.reconcile_delivered_courier_orders", "schedule": 60.0},
}


# Payment gateway configuration -------------------------------------------------
PAYMENT_GATEWAY_TIMEOUT = int(os.getenv("PAYMENT_GATEWAY_TIMEOUT", "20"))
PAYMENT_CONFIG_ENCRYPTION_KEY = os.getenv("PAYMENT_CONFIG_ENCRYPTION_KEY", "")
PAYMENT_API_BASE_URL = os.getenv("PAYMENT_API_BASE_URL", "").rstrip("/")
PAYMENT_STOREFRONT_URL = os.getenv("PAYMENT_STOREFRONT_URL", "").rstrip("/")

SSLCOMMERZ_SANDBOX = os.getenv("SSLCOMMERZ_SANDBOX", "true").lower() == "true"
SSLCOMMERZ_STORE_ID = os.getenv("SSLCOMMERZ_STORE_ID", "")
SSLCOMMERZ_STORE_PASSWORD = os.getenv("SSLCOMMERZ_STORE_PASSWORD", "")

BKASH_SANDBOX = os.getenv("BKASH_SANDBOX", "true").lower() == "true"
BKASH_BASE_URL = os.getenv("BKASH_BASE_URL", "")
BKASH_APP_KEY = os.getenv("BKASH_APP_KEY", "")
BKASH_APP_SECRET = os.getenv("BKASH_APP_SECRET", "")
BKASH_USERNAME = os.getenv("BKASH_USERNAME", "")
BKASH_PASSWORD = os.getenv("BKASH_PASSWORD", "")

NAGAD_SANDBOX = os.getenv("NAGAD_SANDBOX", "true").lower() == "true"
NAGAD_BASE_URL = os.getenv("NAGAD_BASE_URL", "")
NAGAD_MERCHANT_ID = os.getenv("NAGAD_MERCHANT_ID", "")
NAGAD_MERCHANT_NUMBER = os.getenv("NAGAD_MERCHANT_NUMBER", "")
NAGAD_MERCHANT_PRIVATE_KEY = os.getenv("NAGAD_MERCHANT_PRIVATE_KEY", "")
NAGAD_GATEWAY_PUBLIC_KEY = os.getenv("NAGAD_GATEWAY_PUBLIC_KEY", "")
NAGAD_CLIENT_IP = os.getenv("NAGAD_CLIENT_IP", "")
NAGAD_API_VERSION = os.getenv("NAGAD_API_VERSION", "v-0.2.0")
NAGAD_CLIENT_TYPE = os.getenv("NAGAD_CLIENT_TYPE", "PC_WEB")
NAGAD_CURRENCY_CODE = os.getenv("NAGAD_CURRENCY_CODE", "050")


# Courier automation configuration ------------------------------------------------
COURIER_API_TIMEOUT = int(os.getenv("COURIER_API_TIMEOUT", "20"))
COURIER_CONFIG_ENCRYPTION_KEY = os.getenv("COURIER_CONFIG_ENCRYPTION_KEY", "")
