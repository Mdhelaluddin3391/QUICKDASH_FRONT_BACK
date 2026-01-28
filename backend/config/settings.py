# config/settings.py - PRODUCTION READY
# This is a comprehensive production-grade Django settings file
# Designed for Railway, AWS ECS, and Docker deployments
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

# Configure logging early for startup diagnostics
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==============================================================================
# PHASE 1: BASE CONFIGURATION
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
DJANGO_ENV = os.getenv("DJANGO_ENV", "production")

logger.info(f"🚀 Django initializing in {DJANGO_ENV} environment")

# ==============================================================================
# PHASE 2: SECURITY - STRICT PRODUCTION DEFAULTS
# ==============================================================================

# DEBUG - MUST DEFAULT TO FALSE
# Only enable if explicitly required in development
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

if DEBUG:
    logger.warning("⚠️  DEBUG mode is enabled - NEVER use in production")

# SECRET_KEY - REQUIRED IN PRODUCTION
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        logger.warning("⚠️  DJANGO_SECRET_KEY not set, using insecure dev key")
        SECRET_KEY = "dev-insecure-key-change-in-production"
    else:
        logger.critical("❌ DJANGO_SECRET_KEY environment variable is REQUIRED in production")
        sys.exit(1)

# ALLOWED_HOSTS - STRICT FOR PRODUCTION
# Default to localhost in dev, must be explicit in production
ALLOWED_HOSTS_STR = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
if not ALLOWED_HOSTS_STR and not DEBUG:
    logger.critical("❌ ALLOWED_HOSTS environment variable is REQUIRED in production")
    sys.exit(1)
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS_STR.split(",") if h.strip()] if ALLOWED_HOSTS_STR else []

# HTTPS / PROXY / SSL CONFIGURATION
# Critical for Railway, AWS ECS, and cloud deployments
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_FOR = True

if not DEBUG:
    SECURE_SSL_REDIRECT = True
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

# ==============================================================================
# PHASE 3: INSTALLED APPS
# ==============================================================================
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

# ==============================================================================
# PHASE 4: MIDDLEWARE
# ==============================================================================
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

# WhiteNoise for efficient static file serving in production
if not DEBUG:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

# ==============================================================================
# PHASE 5: URL / ASGI
# ==============================================================================
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ==============================================================================
# PHASE 6: DATABASE CONFIGURATION
# Support both DATABASE_URL and POSTGRES_* environment variables
# ==============================================================================
database_url = os.getenv("DATABASE_URL")

if not database_url:
    # Fallback to individual POSTGRES_* environment variables
    postgres_user = os.getenv("POSTGRES_USER")
    postgres_password = os.getenv("POSTGRES_PASSWORD")
    postgres_host = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port = os.getenv("POSTGRES_PORT", "5432")
    postgres_db = os.getenv("POSTGRES_DB")
    
    if postgres_user and postgres_password and postgres_db:
        database_url = (
            f"postgis://{postgres_user}:{postgres_password}"
            f"@{postgres_host}:{postgres_port}/{postgres_db}"
        )
        logger.info(f"Built DATABASE_URL from POSTGRES_* env vars")
    elif not DEBUG:
        logger.critical("❌ DATABASE_URL or POSTGRES_* env vars are REQUIRED in production")
        sys.exit(1)
    else:
        database_url = "postgis://postgres:postgres@localhost:5432/quickdash_dev"
        logger.warning("⚠️  Using development database URL")

DATABASES = {
    "default": dj_database_url.config(
        default=database_url,
        conn_max_age=600,
        engine="django.contrib.gis.db.backends.postgis",
    )
}

if "default" in DATABASES and DATABASES["default"]:
    db_config = DATABASES["default"]
    logger.info(f"Database configured: {db_config.get('HOST')}:{db_config.get('PORT')}/{db_config.get('NAME')}")

# ==============================================================================
# PHASE 7: TEMPLATES
# ==============================================================================
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

# ==============================================================================
# PHASE 8: REDIS / CACHE / CELERY
# Gracefully handle Redis unavailability
# ==============================================================================
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0" if DEBUG else None)

if not REDIS_URL and not DEBUG:
    logger.critical("❌ REDIS_URL environment variable is REQUIRED in production")
    sys.exit(1)

if REDIS_URL:
    logger.info(f"Redis configured: {REDIS_URL.split('@')[0] if '@' in REDIS_URL else REDIS_URL.split('/')[0]}")
    
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
    logger.warning("⚠️  Redis not configured, using in-memory cache (NOT for production)")
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }
    
    CELERY_BROKER_URL = None
    CELERY_RESULT_BACKEND = None
    
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }

# ==============================================================================
# PHASE 9: CORS CONFIGURATION
# Critical for cloud deployments - explicit allow list
# ==============================================================================
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
    logger.warning("⚠️  CORS_ALLOW_ALL_ORIGINS enabled in DEBUG mode")
else:
    CORS_ALLOW_ALL_ORIGINS = False
    cors_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if not cors_origins_str:
        logger.critical("❌ CORS_ALLOWED_ORIGINS environment variable is REQUIRED in production")
        sys.exit(1)
    CORS_ALLOWED_ORIGINS = [o.strip() for o in cors_origins_str.split(",") if o.strip()]
    logger.info(f"CORS configured for {len(CORS_ALLOWED_ORIGINS)} origins")

CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ["Content-Type", "X-CSRFToken"]
CORS_ALLOW_HEADERS = list(default_headers) + [
    "idempotency-key",
    "x-location-lat",
    "x-location-lng",
    "x-address-id",
]

# ==============================================================================
# PHASE 10: LOGGING CONFIGURATION
# Stdout/stderr for container environments
# ==============================================================================
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
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ==============================================================================
# PHASE 11: STATIC FILES & MEDIA
# ==============================================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

if not DEBUG:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ==============================================================================
# PHASE 12: AUTHENTICATION & DRF
# ==============================================================================
AUTH_USER_MODEL = "accounts.User"

SIMPLE_JWT = {
    "SIGNING_KEY": os.getenv("JWT_SIGNING_KEY", SECRET_KEY),
    "ALGORITHM": "HS256",
}

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
}

# ==============================================================================
# PHASE 13: SECURITY HEADERS
# ==============================================================================
X_FRAME_OPTIONS = "DENY" if not DEBUG else "SAMEORIGIN"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_SECURITY_POLICY_NOSCRIPT_SOURCES = ("'none'",)

# ==============================================================================
# PHASE 14: BUSINESS LOGIC
# ==============================================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
RIDER_FIXED_PAY_PER_ORDER = int(os.getenv("RIDER_FIXED_PAY_PER_ORDER", 50))

# ==============================================================================
# PHASE 15: PAYMENT GATEWAYS
# ==============================================================================
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

# ==============================================================================
# PHASE 16: SMS / OTP / NOTIFICATIONS
# ==============================================================================
SMS_PROVIDER = os.getenv("SMS_PROVIDER", "dummy")
SMS_PROVIDER_KEY = os.getenv("SMS_PROVIDER_KEY", "")
SMS_PROVIDER_SECRET = os.getenv("SMS_PROVIDER_SECRET", "")
SMS_PROVIDER_SENDER_ID = os.getenv("SMS_PROVIDER_SENDER_ID", "QUICKD")
SMS_PROVIDER_URL = os.getenv("SMS_PROVIDER_URL", "")

OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", 300))
OTP_RESEND_COOLDOWN = int(os.getenv("OTP_RESEND_COOLDOWN", 60))

# ==============================================================================
# PHASE 17: ERROR TRACKING (OPTIONAL)
# ==============================================================================
if os.getenv("SENTRY_DSN"):
    try:
        sentry_sdk.init(
            dsn=os.getenv("SENTRY_DSN"),
            integrations=[DjangoIntegration(), RedisIntegration(), CeleryIntegration()],
            environment=DJANGO_ENV,
            traces_sample_rate=0.1,
        )
        logger.info("✅ Sentry error tracking initialized")
    except Exception as e:
        logger.warning(f"⚠️  Failed to initialize Sentry: {e}")
else:
    logger.info("ℹ️  Sentry not configured (optional)")

# ==============================================================================
# STARTUP VALIDATION
# ==============================================================================
logger.info(f"✅ Django configuration loaded successfully")
logger.info(f"   Environment: {DJANGO_ENV}")
logger.info(f"   DEBUG: {DEBUG}")
logger.info(f"   Allowed Hosts: {ALLOWED_HOSTS}")
logger.info(f"   Database: {DATABASES.get('default', {}).get('HOST', 'unknown')}")
