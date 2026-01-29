# PRODUCTION ENVIRONMENT VARIABLES GUIDE
# ========================================
# Complete reference for all environment variables required and recommended for production

## PHASE 1: CRITICAL PRODUCTION VARIABLES
## These MUST be set in production. Application will fail without them.

### Django Core Settings
DJANGO_ENV=production                          # [required] Environment: production, development, staging
DEBUG=false                                    # [required] Must be 'false' in production
DJANGO_SECRET_KEY=<generate-with-django>      # [required] Use: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
ALLOWED_HOSTS=api.example.com,www.api.example.com    # [required] Comma-separated list of allowed hostnames

### Database Configuration
# Option A: Use DATABASE_URL (recommended)
DATABASE_URL=postgis://user:password@db.railway.app:5432/quickdash

# Option B: Use POSTGRES_* environment variables (fallback)
POSTGRES_USER=postgres                        # [required if DATABASE_URL not set]
POSTGRES_PASSWORD=<secure-password>           # [required if DATABASE_URL not set]
POSTGRES_HOST=db.railway.app                  # [required if DATABASE_URL not set]
POSTGRES_PORT=5432                            # [optional] Default: 5432
POSTGRES_DB=quickdash                         # [required if DATABASE_URL not set]

### Redis Configuration
REDIS_URL=redis://:password@redis.railway.app:6379/0    # [required] Redis connection string

### CORS Security
CORS_ALLOWED_ORIGINS=https://example.com,https://app.example.com    # [required] Comma-separated CORS origins

### JWT & Authentication
JWT_SIGNING_KEY=<same-as-django-secret-key>  # [optional] Defaults to DJANGO_SECRET_KEY if not set

---

## PHASE 2: CLOUD PLATFORM CONFIGURATION

### Railway Deployment
PORT=8000                                     # [optional] Default: 5000. Railway uses this to bind the server.
IS_PRIMARY=1                                  # [optional] Set to '1' for primary instance (runs migrations, collectstatic)
RUN_GUNICORN=1                                # [optional] Default: 1. Set to '0' for auxiliary processes (Celery)

### AWS ECS / AWS EC2
PORT=5000                                     # [optional] For ALB/NLB
ENVIRONMENT=production                        # [optional] For CloudWatch logging
LOG_LEVEL=info                                # [optional] info, debug, warning, error

---

## PHASE 3: PAYMENT CONFIGURATION

### Razorpay (Payment Gateway)
RAZORPAY_KEY_ID=<razorpay-key-id>             # [required if using Razorpay]
RAZORPAY_KEY_SECRET=<razorpay-secret>         # [required if using Razorpay]
RAZORPAY_WEBHOOK_SECRET=<webhook-secret>      # [optional] For webhook verification

---

## PHASE 4: SMS / OTP / NOTIFICATIONS

### SMS Provider Configuration
SMS_PROVIDER=twilio                           # [optional] Provider: twilio, aws_sns, etc. Default: dummy
SMS_PROVIDER_KEY=<api-key>                    # [optional] For SMS provider
SMS_PROVIDER_SECRET=<api-secret>              # [optional] For SMS provider
SMS_PROVIDER_SENDER_ID=QUICKD                 # [optional] Sender ID. Default: QUICKD
SMS_PROVIDER_URL=<api-endpoint>               # [optional] API endpoint URL

### OTP Settings
OTP_EXPIRY_SECONDS=300                        # [optional] OTP validity in seconds. Default: 300 (5 minutes)
OTP_RESEND_COOLDOWN=60                        # [optional] Cooldown between OTP resends. Default: 60 seconds

---

## PHASE 5: ERROR TRACKING & MONITORING

### Sentry (Error Tracking - Optional)
SENTRY_DSN=https://key@sentry.io/project     # [optional] Enable Sentry error tracking

### Prometheus Metrics
# Already enabled via django-prometheus middleware. No additional config needed.

---

## PHASE 6: BUSINESS LOGIC CONFIGURATION

### Rider Payment
RIDER_FIXED_PAY_PER_ORDER=50                  # [optional] Payment per order in currency units. Default: 50

---

## PHASE 7: GUNICORN WORKER CONFIGURATION

### Gunicorn Settings
GUNICORN_WORKERS=5                            # [optional] Default: (CPU_COUNT * 2) + 1
GUNICORN_TIMEOUT=120                          # [optional] Request timeout in seconds. Default: 120
GUNICORN_GRACEFUL_TIMEOUT=30                  # [optional] Graceful shutdown timeout. Default: 30
GUNICORN_KEEPALIVE=5                          # [optional] Keep-alive timeout. Default: 5
GUNICORN_MAX_REQUESTS=1000                    # [optional] Max requests per worker before recycle. Default: 1000
GUNICORN_MAX_REQUESTS_JITTER=100              # [optional] Random jitter. Default: 100
GUNICORN_LOG_LEVEL=info                       # [optional] Log level: debug, info, warning, error. Default: info

---

## PHASE 8: DEPLOYMENT-SPECIFIC

### For Local Docker Development
DJANGO_ENV=development
DEBUG=true
DATABASE_URL=postgis://postgres:postgres@db:5432/quickdash_dev
REDIS_URL=redis://redis:6379/0
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

### For Railway Production
DJANGO_ENV=production
DEBUG=false
# DATABASE_URL, REDIS_URL, ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS: Set in Railway dashboard
IS_PRIMARY=1 (only for primary instance)
RUN_GUNICORN=1 (only for web process)

### For AWS ECS Production
DJANGO_ENV=production
DEBUG=false
# DATABASE_URL (RDS endpoint), REDIS_URL (ElastiCache), etc.
PORT=5000
IS_PRIMARY=1 (only for task definition marked primary)

---

## ENVIRONMENT VARIABLE VALIDATION CHECKLIST

Before deploying to production, verify:

✅ DJANGO_SECRET_KEY is set and unique per environment
✅ DEBUG=false in all production environments
✅ ALLOWED_HOSTS is explicitly configured (not "*")
✅ DATABASE_URL or POSTGRES_* env vars are correctly set
✅ REDIS_URL is correctly set (required for production)
✅ CORS_ALLOWED_ORIGINS is explicitly configured (not "*")
✅ RAZORPAY_* keys are set if using Razorpay
✅ SMS_PROVIDER is configured if using SMS
✅ PORT is set correctly for your deployment platform
✅ IS_PRIMARY=1 only on primary instance
✅ RUN_GUNICORN=1 for web service, RUN_GUNICORN=0 for workers

---

## ENVIRONMENT VARIABLE EXAMPLES

### Example: Railway Deployment (.railway.json)
```json
{
  "DJANGO_ENV": "production",
  "DEBUG": "false",
  "ALLOWED_HOSTS": "api.quickdash.app,quickdash.app",
  "CORS_ALLOWED_ORIGINS": "https://quickdash.app,https://app.quickdash.app"
}
```

### Example: Docker Compose (.env)
```
DJANGO_ENV=development
DEBUG=true
DJANGO_SECRET_KEY=dev-insecure-key-change-in-production
DATABASE_URL=postgis://postgres:postgres@db:5432/quickdash_dev
REDIS_URL=redis://redis:6379/0
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:8000,http://localhost:3000
IS_PRIMARY=1
RUN_GUNICORN=1
PORT=5000
```

### Example: AWS ECS Task Definition (Environment Variables)
```
[
  { "name": "DJANGO_ENV", "value": "production" },
  { "name": "DEBUG", "value": "false" },
  { "name": "DJANGO_SECRET_KEY", "valueFrom": "arn:aws:secretsmanager:..." },
  { "name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:..." },
  { "name": "REDIS_URL", "valueFrom": "arn:aws:secretsmanager:..." },
  { "name": "ALLOWED_HOSTS", "value": "api.example.com" },
  { "name": "CORS_ALLOWED_ORIGINS", "value": "https://example.com" },
  { "name": "IS_PRIMARY", "value": "1" },
  { "name": "RUN_GUNICORN", "value": "1" },
  { "name": "PORT", "value": "5000" }
]
```

---

## NOTES

1. **Never commit secrets to git** - Use environment variables or secrets management tools
2. **Use strong passwords** for POSTGRES_PASSWORD, Redis passwords, and DJANGO_SECRET_KEY
3. **Test DATABASE_URL format**: postgis://user:password@host:port/database
4. **CORS_ALLOWED_ORIGINS must not include "*"** in production
5. **Always use HTTPS** - Set SECURE_SSL_REDIRECT=true automatically when DEBUG=false
6. **Test locally before deploying** - Use docker-compose with these env vars first
   