import os
from pathlib import Path
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from corsheaders.defaults import default_headers

# ------------------------------------------------------------------------------
# BASE
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DJANGO_ENV = os.getenv("DJANGO_ENV", "development")

# ------------------------------------------------------------------------------
# SECURITY
# ------------------------------------------------------------------------------
DEBUG = os.getenv("DEBUG", "0") == "1"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key")
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# ------------------------------------------------------------------------------
# RAILWAY SSL / PROXY FIX
# ------------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# ------------------------------------------------------------------------------
# CORS
# ------------------------------------------------------------------------------
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:8000"
    ).split(",")

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + [
    "idempotency-key",
    "x-location-lat",
    "x-location-lng",
    "x-address-id",
]

# ------------------------------------------------------------------------------
# APPS
# ------------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",

    "rest_framework",
    "django_filters",
    "corsheaders",
    "channels",
    "drf_spectacular",
    "django_prometheus",
    "storages",
    "django_celery_beat",
    "leaflet",

    "apps.accounts",
    "apps.customers",
    "apps.orders",
    "apps.inventory",
    "apps.payments",
    "apps.pricing",
    "apps.notifications",
    "apps.audit",
    "apps.delivery",
    "apps.riders",
    "apps.locations",
    "apps.catalog",
    "apps.warehouse",
    "apps.assistant",
    "apps.core",
]

# ------------------------------------------------------------------------------
# MIDDLEWARE
# ------------------------------------------------------------------------------
MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.core.middleware.CorrelationIDMiddleware",
    "apps.core.middleware.GlobalKillSwitchMiddleware",
    "apps.core.middleware.LocationContextMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

# ------------------------------------------------------------------------------
# URL / ASGI
# ------------------------------------------------------------------------------
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ------------------------------------------------------------------------------
# DATABASE (POSTGIS – SINGLE SOURCE OF TRUTH ✅)
# ------------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.getenv("POSTGRES_DB", "quickdash"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "HOST": os.getenv("POSTGRES_HOST"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

# ------------------------------------------------------------------------------
# REDIS / CACHE / CELERY
# ------------------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL")

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# ------------------------------------------------------------------------------
# CHANNELS
# ------------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# ------------------------------------------------------------------------------
# STATIC / MEDIA (RAILWAY EPHEMERAL OK)
# ------------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ------------------------------------------------------------------------------
# AUTH / JWT / DRF
# ------------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

SIMPLE_JWT = {
    "SIGNING_KEY": os.getenv("JWT_SIGNING_KEY", SECRET_KEY),
}

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

# ------------------------------------------------------------------------------
# SENTRY (OPTIONAL)
# ------------------------------------------------------------------------------
if not DEBUG and os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[DjangoIntegration(), RedisIntegration(), CeleryIntegration()],
        environment=DJANGO_ENV,
        traces_sample_rate=0.1,
    )

# ------------------------------------------------------------------------------
# BUSINESS
# ------------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
RIDER_FIXED_PAY_PER_ORDER = int(os.getenv("RIDER_FIXED_PAY_PER_ORDER", 50))
