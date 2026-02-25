
import os
import sys
import logging
from pathlib import Path
import dj_database_url

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from corsheaders.defaults import default_headers

from datetime import timedelta 



AUTH_USER_MODEL = "accounts.User"


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


BASE_DIR = Path(__file__).resolve().parent.parent
DJANGO_ENV = os.getenv("DJANGO_ENV", "production")

logger.info(f"🚀 Django initializing in {DJANGO_ENV} environment")



DEBUG = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

if DEBUG:
    logger.warning(" DEBUG mode is enabled - NEVER use in production")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        logger.warning("  DJANGO_SECRET_KEY not set, using insecure dev key")
        SECRET_KEY = "dev-insecure-key-change-in-production"
    else:
        logger.critical(" DJANGO_SECRET_KEY environment variable is REQUIRED in production")
        sys.exit(1)

ALLOWED_HOSTS_STR = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")

ALLOWED_HOSTS = [
    ".railway.app",
    "quickdash.up.railway.app",
    "quickdashbackend.up.railway.app",
    ".railway.internal", 
    "*"
]



CSRF_TRUSTED_ORIGINS = [
    url.strip() for url in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if url.strip()
]


CORS_ALLOWED_ORIGINS = [
    url.strip() for url in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if url.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_FOR = True

if not DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",

    # Third-party
    "rest_framework",
    "django_filters",
    "corsheaders",
    "channels",
    "drf_spectacular",
    "django_prometheus",
    "storages",
    "django_celery_beat",
    "leaflet",

    # Local apps
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

if not DEBUG:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")


ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


DATABASES = {
    "default": dj_database_url.config(
        conn_max_age=600,
        conn_health_checks=True,
        engine="django.contrib.gis.db.backends.postgis",
    )
}

if not DATABASES["default"]:
    if os.getenv("PGHOST"):
        DATABASES["default"] = {
            "ENGINE": "django.contrib.gis.db.backends.postgis",
            "NAME": os.getenv("PGDATABASE", os.getenv("POSTGRES_DB")),
            "USER": os.getenv("PGUSER", os.getenv("POSTGRES_USER")),
            "PASSWORD": os.getenv("PGPASSWORD", os.getenv("POSTGRES_PASSWORD")),
            "HOST": os.getenv("PGHOST", os.getenv("POSTGRES_HOST")),
            "PORT": os.getenv("PGPORT", os.getenv("POSTGRES_PORT", "5432")),
        }

if "default" in DATABASES and DATABASES["default"]:
    db_config = DATABASES["default"]
    logger.info(f"Database configured: {db_config.get('HOST')}:{db_config.get('PORT')}/{db_config.get('NAME')}")
else:
    logger.critical(" Database configuration failed. Check DATABASE_URL or PG* variables.")


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


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0" if DEBUG else None)

if not REDIS_URL and not DEBUG:
    logger.critical(" REDIS_URL environment variable is REQUIRED in production")
    sys.exit(1)

if REDIS_URL:
    logger.info(f"Redis configured")
    
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
    CELERY_BROKER_HEARTBEAT = 60
    CELERY_TASK_ACKS_LATE = True
    CELERY_WORKER_PREFETCH_MULTIPLIER = 1
    
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
                "RETRY_ON_TIMEOUT": True,
            }
        }
    }
    
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
                "capacity": 1500,
                "expiry": 10,
            },
        }
    }
else:
    logger.warning("  Redis not configured, using in-memory cache (NOT for production)")
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }
    CELERY_BROKER_URL = None
    CELERY_RESULT_BACKEND = None
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOW_ALL_ORIGINS = False
    cors_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if cors_origins_str:
        CORS_ALLOWED_ORIGINS = [o.strip() for o in cors_origins_str.split(",") if o.strip()]
        logger.info(f"CORS configured for {len(CORS_ALLOWED_ORIGINS)} origins")
    else:
        logger.warning("CORS_ALLOWED_ORIGINS not set. CORS blocked.")

CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ["Content-Type", "X-CSRFToken"]
CORS_ALLOW_HEADERS = list(default_headers) + [
    "idempotency-key",
    "x-location-lat",
    "x-location-lng",
    "x-address-id",
]


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO" if not DEBUG else "DEBUG",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


STATICFILES_DIRS = [
    BASE_DIR / "static",
]



if not DEBUG:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"



REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/day",
        "user": "1000/day",
        "otp_send": "5/hour", 
        "registration": "5/hour",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
}


X_FRAME_OPTIONS = "DENY" if not DEBUG else "SAMEORIGIN"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_SECURITY_POLICY_NOSCRIPT_SOURCES = ("'none'",)


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
RIDER_FIXED_PAY_PER_ORDER = int(os.getenv("RIDER_FIXED_PAY_PER_ORDER", 50))


RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")


SMS_PROVIDER = os.getenv("SMS_PROVIDER", "dummy")
SMS_PROVIDER_KEY = os.getenv("SMS_PROVIDER_KEY", "")
SMS_PROVIDER_SECRET = os.getenv("SMS_PROVIDER_SECRET", "")
SMS_PROVIDER_SENDER_ID = os.getenv("SMS_PROVIDER_SENDER_ID", "QUICKD")
SMS_PROVIDER_URL = os.getenv("SMS_PROVIDER_URL", "")

OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", 300))
OTP_RESEND_COOLDOWN = int(os.getenv("OTP_RESEND_COOLDOWN", 60))


if os.getenv("SENTRY_DSN"):
    try:
        sentry_sdk.init(
            dsn=os.getenv("SENTRY_DSN"),
            integrations=[DjangoIntegration(), RedisIntegration(), CeleryIntegration()],
            environment=DJANGO_ENV,
            traces_sample_rate=0.1,
        )
        logger.info(" Sentry error tracking initialized")
    except Exception as e:
        logger.warning(f"  Failed to initialize Sentry: {e}")
else:
    logger.info("ℹ  Sentry not configured (optional)")


logger.info(f" Django configuration loaded successfully")
logger.info(f"   Environment: {DJANGO_ENV}")
logger.info(f"   DEBUG: {DEBUG}")
logger.info(f"   Allowed Hosts: {ALLOWED_HOSTS}")
logger.info(f"   CSRF Trusted Origins: {CSRF_TRUSTED_ORIGINS}")
logger.info(f"   Database: {DATABASES.get('default', {}).get('HOST', 'unknown')}")





SIMPLE_JWT = {
    "SIGNING_KEY": os.getenv("JWT_SIGNING_KEY", SECRET_KEY),
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_LIFETIME": timedelta(days=365),    
    "REFRESH_TOKEN_LIFETIME": timedelta(days=365),  
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}





LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Kolkata' 

USE_I18N = True
USE_TZ = True 

DATETIME_FORMAT = 'd/m/Y H:i'
DATE_FORMAT = 'd/m/Y'