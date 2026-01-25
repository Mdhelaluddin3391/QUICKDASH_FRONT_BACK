# config/settings.py

import os
from pathlib import Path
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from corsheaders.defaults import default_headers

# ------------------------------------------------------------------------------
# BASE & ENVIRONMENT
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DJANGO_ENV = os.getenv("DJANGO_ENV", "development")

# ------------------------------------------------------------------------------
# SECURITY
# ------------------------------------------------------------------------------
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")

# ------------------------------------------------------------------------------
# CORS CONFIG (SINGLE SOURCE OF TRUTH ✅)
# ------------------------------------------------------------------------------
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOW_ALL_ORIGINS = False
    allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS")
    if allowed_origins:
        CORS_ALLOWED_ORIGINS = allowed_origins.split(",")
    else:
        CORS_ALLOWED_ORIGINS = [
            "http://localhost:8000",
            "http://127.0.0.1:5500",
            "http://127.0.0.1:8000",
            "http://0.0.0.0:8081",
            "http://localhost:8081",
            "http://localhost:5000",
            "http://127.0.0.1:5000",
            "https://quickdash.com",
            "https://www.quickdash.com",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:2000",
            "http://127.0.0.1:2000",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
            "http://localhost:3002",
            "http://127.0.0.1:3002",
            "http://localhost:3003",
            "http://127.0.0.1:3003",
                    
        ]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = list(default_headers) + [
    "idempotency-key",
    "x-location-lat",
    "x-location-lng",
    "x-address-id",
]

# ------------------------------------------------------------------------------
# APPLICATIONS
# ------------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",

    # Third Party
    "rest_framework",
    "django_filters",
    "corsheaders",
    "channels",
    "drf_spectacular",
    "django_prometheus",
    "storages",
    "django_celery_beat",
    'leaflet',
    'apps.orders.apps.OrdersConfig',

    # Local Apps
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
# MIDDLEWARE (ORDER MATTERS ⚠️)
# ------------------------------------------------------------------------------
MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",

    "corsheaders.middleware.CorsMiddleware",  # MUST BE FIRST
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
# URL / TEMPLATES
# ------------------------------------------------------------------------------
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

# ------------------------------------------------------------------------------
# DATABASE & CACHE
# ------------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.getenv("POSTGRES_DB", "quickdash"),
        "USER": os.getenv("POSTGRES_USER", "quickdash"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "quickdash_secure"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 0,
    }
}

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
        }
    }
}

# ------------------------------------------------------------------------------
# SECURITY HEADERS (PRODUCTION ONLY)
# ------------------------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ------------------------------------------------------------------------------
# STATIC & MEDIA
# ------------------------------------------------------------------------------
USE_S3 = os.getenv("USE_S3", "0") == "1"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

if USE_S3:
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "ap-south-1")
    AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"

    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True

    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {"BACKEND": "storages.backends.s3boto3.S3StaticStorage"},
    }

    STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/static/"
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"
else:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

# ------------------------------------------------------------------------------
# CELERY & CHANNELS
# ------------------------------------------------------------------------------
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# ------------------------------------------------------------------------------
# AUTH & DRF
# ------------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

SIMPLE_JWT = {
    "SIGNING_KEY": os.getenv("JWT_SIGNING_KEY", "dev-signing-key"),
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
}




REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.authentication.SecureJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "1000/min", 
        "user": "10000/day",
        "otp_send": "100/minute",      
        "registration": "1000/minute",
        "location_ping": "100/minute", 
        "ai_assistant": "100/minute",
    },
    # Use our custom exception handler to map BusinessLogicException -> 400 JSON
    "EXCEPTION_HANDLER": "apps.utils.exceptions.custom_exception_handler",
}
# ------------------------------------------------------------------------------
# LOGGING & MONITORING
# ------------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

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
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "dummy_key")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "dummy_secret")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")
GOOGLE_MAPS_KEY = os.getenv("GOOGLE_MAPS_KEY", "")




# Leaflet Configuration (Optional but recommended for India)
LEAFLET_CONFIG = {
    'DEFAULT_CENTER': (22.5937, 78.9629), # India Center
    'DEFAULT_ZOOM': 5,
    'MIN_ZOOM': 3,
    'MAX_ZOOM': 18,
    'SCALE': 'both',
    'ATTRIBUTION_PREFIX': 'QuickDash',
}


# ------------------------------------------------------------------------------
# CSRF CONFIGURATION
# ------------------------------------------------------------------------------
# This tells Django to trust requests coming from your localhost
CSRF_TRUSTED_ORIGINS = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000"
).split(",")