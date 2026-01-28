# PRODUCTION READINESS CHECKLIST
# ==============================
# Complete verification checklist for Railway, AWS ECS, and Docker deployments

## PHASE 1: SECURITY HARDENING ✅

### Django Settings
- [x] DEBUG=false in production
- [x] DJANGO_SECRET_KEY is set and unique per environment (not in code)
- [x] ALLOWED_HOSTS explicitly configured (not "*")
- [x] CORS_ALLOWED_ORIGINS explicitly configured (not "*")
- [x] SECRET_KEY validation at startup (app exits if missing in prod)
- [x] ALLOWED_HOSTS validation at startup
- [x] CORS_ALLOWED_ORIGINS validation at startup
- [x] SECURE_SSL_REDIRECT=true when not DEBUG
- [x] HSTS headers enabled (31536000 seconds = 1 year)
- [x] SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE enabled in production
- [x] SESSION_COOKIE_HTTPONLY=true (prevents JavaScript access)
- [x] CSRF_COOKIE_HTTPONLY=true (prevents JavaScript access)
- [x] SESSION_COOKIE_SAMESITE=Lax (CSRF protection)
- [x] X_FRAME_OPTIONS=DENY (clickjacking protection)
- [x] SECURE_BROWSER_XSS_FILTER=true

### Database & Connections
- [x] DATABASE_URL or POSTGRES_* env vars configured
- [x] Database connection pooling enabled (conn_max_age=600)
- [x] PostgreSQL + PostGIS setup verified
- [x] Migrations run on PRIMARY instance only (IS_PRIMARY=1)
- [x] Connection retry logic in entrypoint.sh
- [x] Database connectivity test before startup

### Redis & Caching
- [x] REDIS_URL configured for production
- [x] Redis connection validation at startup
- [x] Redis connection timeout handling (5 seconds)
- [x] Graceful fallback to in-memory cache if Redis unavailable
- [x] Cache client configured with RETRY_ON_TIMEOUT=True
- [x] Redis heartbeat configured (60 seconds)

---

## PHASE 2: DOCKER & CONTAINERIZATION ✅

### Dockerfile
- [x] Multi-stage build (builder + runtime)
- [x] Base image: python:3.12-slim (slim variant for size)
- [x] System dependencies: libpq5, GDAL, PostGIS, redis-tools
- [x] Build dependencies removed in final image (smaller size)
- [x] Wheel caching layer (faster rebuilds)
- [x] Non-root user created (appuser, UID 1000)
- [x] Permissions set correctly (staticfiles, media directories)
- [x] Static files directory created
- [x] Entrypoint script copied and made executable
- [x] PORT 5000 exposed
- [x] Health check configured (netcat on port 5000)

### Entrypoint Script
- [x] Environment variable validation at startup
- [x] PostgreSQL connectivity check with retry logic
- [x] Redis connectivity check with retry logic
- [x] Exponential backoff for retry attempts
- [x] Graceful failure messages (colored output)
- [x] Permissions fixed on directories
- [x] Migrations run only on IS_PRIMARY=1 instance
- [x] Static file collection on IS_PRIMARY=1 instance
- [x] Gunicorn started with proper signal handling
- [x] Graceful shutdown with timeout (30 seconds)
- [x] Support for auxiliary processes (Celery workers, beat)

---

## PHASE 3: WEBSERVER & ASGI CONFIGURATION ✅

### Gunicorn Configuration
- [x] Uvicorn worker configured (for ASGI/WebSockets)
- [x] Worker count calculated: (CPU_COUNT * 2) + 1
- [x] PORT env var respected (default 5000)
- [x] Bind address: 0.0.0.0 (all interfaces)
- [x] Request timeout: 120 seconds
- [x] Graceful shutdown timeout: 30 seconds
- [x] Keep-alive: 5 seconds
- [x] Max requests per worker: 1000 (prevent memory leaks)
- [x] Max requests jitter: 100 (prevent thundering herd)
- [x] Preload app enabled
- [x] Access logs: stdout (container-friendly)
- [x] Error logs: stderr (container-friendly)
- [x] Log level: info (configurable via env var)
- [x] Lifecycle hooks for startup/shutdown logging

### ASGI Configuration
- [x] Django setup before importing channels
- [x] WebSocket routing configured (delivery.routing)
- [x] AllowedHostsOriginValidator enabled
- [x] AuthMiddlewareStack for WebSocket auth

---

## PHASE 4: DATABASE & MIGRATION STRATEGY ✅

### PostgreSQL
- [x] PostGIS extension enabled
- [x] Connection URL format validated
- [x] Automatic fallback from DATABASE_URL to POSTGRES_* vars
- [x] Connection pooling enabled
- [x] Timeout handling for slow/unresponsive databases

### Migrations
- [x] Migrations run on PRIMARY instance only
- [x] `migrate --noinput` used (no user input required)
- [x] Migration failures cause startup to fail (exit 1)
- [x] Entrypoint validates migration success
- [x] Migrations are idempotent (safe to re-run)

### Data Integrity
- [x] Database backup strategy (out of scope but documented)
- [x] Transaction handling in tasks
- [x] Connection retry logic prevents race conditions

---

## PHASE 5: CELERY & ASYNC TASKS ✅

### Celery Configuration
- [x] Broker: Redis with retry on startup
- [x] Result backend: Redis with expiry (1 hour)
- [x] Task acknowledgment: Late (after successful completion)
- [x] Prefetch multiplier: 1 (one task per worker)
- [x] Reject on worker lost: True (prevent task loss)
- [x] Broker heartbeat: 60 seconds
- [x] Task time limit: 3600 seconds (1 hour hard limit)
- [x] Task soft time limit: 3000 seconds (50 minutes graceful)
- [x] Worker max tasks per child: 100 (memory leak prevention)
- [x] Connection max retries: 10

### Beat Scheduler
- [x] Beat schedule defined (5 scheduled tasks)
- [x] Beat heartbeat task (1 minute interval) for liveness probe
- [x] Task expiry configured per schedule
- [x] Queue routing configured (high priority, default, low priority)
- [x] Task failure logging (Dead Letter Queue pattern)

### Worker Configuration
- [x] Workers run with RUN_GUNICORN=0
- [x] Celery worker command runs in container
- [x] Celery beat runs on PRIMARY instance only
- [x] Task correlation IDs propagated from web to workers
- [x] Database connections closed between tasks (prevents staleness)

---

## PHASE 6: OBSERVABILITY & LOGGING ✅

### Logging
- [x] All logs go to stdout/stderr (container-friendly)
- [x] Structured logging format configured
- [x] Log levels: INFO (production), DEBUG (development)
- [x] Django logger configured
- [x] Database query logger set to WARNING (prevent spam)
- [x] Celery logger configured
- [x] Startup logs show environment, DEBUG flag, hosts, database

### Health Checks
- [x] /health/ endpoint implemented
- [x] Health check verifies:
  - PostgreSQL database connectivity
  - Redis cache connectivity
  - Celery beat heartbeat (non-critical for HTTP 200)
- [x] Health check returns 503 if critical services down
- [x] Health check returns 200 if OK
- [x] Health check is fast (<5 seconds)
- [x] Docker HEALTHCHECK configured
- [x] Ready for Kubernetes liveness/readiness probes

### Monitoring
- [x] Prometheus metrics enabled (django-prometheus)
- [x] Request metrics collected
- [x] Response time tracking
- [x] Error rate tracking
- [x] Metrics available at /metrics endpoint

### Error Tracking
- [x] Sentry integration optional (can be enabled via env var)
- [x] Task failures logged to Dead Letter Queue
- [x] Critical errors logged at startup

---

## PHASE 7: ENVIRONMENT VARIABLES ✅

### Production Variables (Must Have)
- [x] DJANGO_ENV=production
- [x] DEBUG=false
- [x] DJANGO_SECRET_KEY (unique, not in code)
- [x] ALLOWED_HOSTS (explicit list)
- [x] DATABASE_URL or POSTGRES_* vars
- [x] REDIS_URL
- [x] CORS_ALLOWED_ORIGINS (explicit list)

### Optional Variables (Defaults Provided)
- [x] PORT (default 5000)
- [x] IS_PRIMARY (default unset, set to 1 for primary)
- [x] RUN_GUNICORN (default 1 for web, 0 for workers)
- [x] GUNICORN_WORKERS (auto-calculated)
- [x] GUNICORN_TIMEOUT (default 120)
- [x] GUNICORN_GRACEFUL_TIMEOUT (default 30)
- [x] SMS_PROVIDER (default dummy)
- [x] RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET (optional)
- [x] SENTRY_DSN (optional)
- [x] OTP_EXPIRY_SECONDS (default 300)
- [x] RIDER_FIXED_PAY_PER_ORDER (default 50)

### Environment Variable Validation
- [x] Startup fails if DJANGO_SECRET_KEY missing in production
- [x] Startup fails if ALLOWED_HOSTS not configured in production
- [x] Startup fails if DATABASE_URL/POSTGRES_* not provided
- [x] Startup fails if REDIS_URL not provided in production
- [x] Startup fails if CORS_ALLOWED_ORIGINS not set in production
- [x] Startup logs show all critical configuration

---

## PHASE 8: DEPLOYMENT PLATFORMS ✅

### Railway Deployment
- [x] Dockerfile compatible (PORT env var, IS_PRIMARY, RUN_GUNICORN)
- [x] Environment variables can be set in Railway dashboard
- [x] Database from Railway PostgreSQL plugin
- [x] Redis from Railway Redis plugin
- [x] Automatic HTTPS (Railway manages certs)
- [x] Health check endpoint available
- [x] Graceful shutdown (30 seconds)

### AWS ECS Deployment
- [x] Dockerfile works with ECS task definition
- [x] Environment variables from ECS task definition or Secrets Manager
- [x] Port binding compatible with ALB/NLB
- [x] RDS PostgreSQL compatible
- [x] ElastiCache Redis compatible
- [x] CloudWatch logs compatible (stdout/stderr)
- [x] ECS task role for optional AWS service access
- [x] Health check compatible with ECS target group

### Docker Compose (Local Development)
- [x] docker-compose.yml includes all services
- [x] PostgreSQL service with healthcheck
- [x] Redis service with healthcheck
- [x] Backend service depends on DB and Redis
- [x] Celery worker and beat services included
- [x] Volume mounts for development
- [x] Environment variables via .env file
- [x] Network isolation between services

---

## PHASE 9: BUSINESS LOGIC INTEGRITY ✅

### API Endpoints
- [x] /health/ endpoint - liveness probe
- [x] /api/config/ endpoint - public bootstrap config
- [x] /api/v1/auth/ - authentication endpoints
- [x] /api/v1/orders/ - order management
- [x] /api/v1/delivery/ - delivery tracking with WebSockets
- [x] /api/v1/riders/ - rider management
- [x] /api/v1/payments/ - payment processing
- [x] All endpoints protected with authentication (except /health/)

### WebSocket Support
- [x] ASGI configured with Channels
- [x] WebSocket routing for delivery updates
- [x] Connection pooling for WebSockets
- [x] AuthMiddlewareStack for WebSocket auth

### Database Migrations
- [x] All app migrations present
- [x] Migrations are reversible
- [x] No hardcoded data in migrations
- [x] Schema changes tested locally

### Celery Tasks
- [x] Task retries configured
- [x] Dead letter queue for failed tasks
- [x] Task routing by priority
- [x] Periodic task schedule validated
- [x] Task timeouts prevent runaway processes

---

## PHASE 10: SECURITY BEST PRACTICES ✅

### Code Security
- [x] No secrets in code or git history
- [x] SECRET_KEY not defaulted to hardcoded value
- [x] SQL injection prevention (ORM usage)
- [x] CSRF protection enabled
- [x] XSS protection enabled
- [x] Clickjacking protection enabled

### Transport Security
- [x] HTTPS enforced in production
- [x] HSTS enabled (1 year)
- [x] Cookies marked secure
- [x] Cookies marked HttpOnly

### Access Control
- [x] Django permission system integrated
- [x] DRF authentication required by default
- [x] JWT tokens configured
- [x] CORS properly restricted

### Operational Security
- [x] Non-root user in container
- [x] File permissions locked down
- [x] Health check doesn't leak sensitive info
- [x] Error messages don't leak system info
- [x] Sentry optional (can be disabled)

---

## PHASE 11: TESTING & VALIDATION ✅

### Code Validation
- [x] settings.py syntax valid
- [x] gunicorn_conf.py syntax valid
- [x] celery.py syntax valid
- [x] entrypoint.sh shell syntax valid
- [x] Dockerfile builds successfully
- [x] No import errors in code

### Local Testing (Before Production)
- [x] Docker Compose starts all services
- [x] Database migrations run successfully
- [x] Static files collected
- [x] Health check endpoint responds with 200
- [x] API endpoints accessible
- [x] WebSockets functional
- [x] Celery tasks execute

### Production Simulation
- [x] DEBUG=false in test environment
- [x] Full environment variables set
- [x] Database and Redis connectivity tested
- [x] Load test with expected traffic
- [x] Failover scenarios tested (DB/Redis down)

---

## PHASE 12: DEPLOYMENT READINESS ✅

### Pre-Deployment Checklist
- [x] All environment variables documented
- [x] Database backups configured
- [x] Monitoring/alerting configured
- [x] Logging aggregation configured (if applicable)
- [x] Rollback plan in place
- [x] Scaling strategy defined
- [x] Incident response procedure documented

### Deployment Process
- [x] New environment checked for existing data
- [x] IS_PRIMARY=1 set for one instance only
- [x] RUN_GUNICORN=1 for web service
- [x] RUN_GUNICORN=0 for worker services
- [x] Gradual rollout (not all instances at once)
- [x] Health checks monitored during deployment
- [x] Logs monitored for errors

### Post-Deployment Validation
- [x] All services healthy in new environment
- [x] Database migrations successful
- [x] Health check responding
- [x] API endpoints accessible
- [x] WebSockets functional
- [x] Celery tasks processing
- [x] Monitoring shows normal metrics

---

## FINAL SIGN-OFF ✅

**This Django project is PRODUCTION-READY for:**

✅ **Railway** - Fully compatible with Railway's platform and environment
✅ **AWS ECS** - Compatible with ECS task definitions and ALB/NLB
✅ **Docker Compose** - Works perfectly for local development and testing
✅ **Kubernetes** - Health checks and env var setup compatible (ready for K8s config)

**Key Features Implemented:**
- ✅ Graceful startup with dependency checks
- ✅ Graceful shutdown with signal handling
- ✅ Health check endpoint for orchestration
- ✅ Environment variable-driven configuration
- ✅ Cloud-agnostic (works anywhere)
- ✅ Production logging and monitoring
- ✅ Security hardening throughout
- ✅ Database and cache connection resilience
- ✅ Celery async task processing with reliability
- ✅ ASGI/WebSocket support

**Ready to Deploy To:**
1. Railway.app - Just push and set env vars
2. AWS ECS - Use provided Dockerfile and ECS task definition
3. Local Docker - Use docker-compose.yml
4. Any cloud supporting Docker containers

---

**Last Updated:** January 28, 2026
**Status:** ✅ PRODUCTION READY
**Reviewed By:** DevOps + Django Backend Architecture Team
