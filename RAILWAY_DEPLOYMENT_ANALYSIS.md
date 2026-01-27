# Railway Deployment Analysis & Production Strategy
**Date:** January 2026 | **Project:** QuickDash | **Status:** Ready for FREE Railway Deployment

---

## 1. PROJECT OVERVIEW

### 1.1 Project Type
- **Type:** Full-stack microservices delivery & order management platform
- **Architecture:** Distributed multi-service system
- **Use Case:** Quick commerce / hyperlocal delivery with real-time tracking, rider management, and inventory sync

### 1.2 Complete Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Backend Framework** | Django REST Framework | 5.1+ |
| **Frontend Framework** | Vanilla HTML/JS + Nginx | Static SPA |
| **Database** | PostgreSQL + PostGIS | 15-3.3 |
| **Message Broker** | Redis | 7.2 Alpine |
| **Job Queue** | Celery | 5.3+ |
| **Job Scheduler** | Celery Beat | 2.5+ |
| **WebSocket** | Django Channels + Daphne | 4.0+ |
| **Web Server (Backend)** | Gunicorn + Uvicorn | 21.2 / 0.23 |
| **Web Server (Frontend)** | Nginx | stable-alpine |
| **Media Storage** | S3 (optional) or local | boto3 |
| **Authentication** | JWT (SimpleJWT) | 5.3+ |
| **Payment Gateway** | Razorpay API | 1.4 |
| **Geolocation** | PostGIS, GeoPy, Google Maps API | - |
| **Monitoring** | Sentry, Prometheus | 1.30+ / 2.3+ |

### 1.3 Architecture Type
- **Monorepo with separate services**
  - Backend: Django application + Celery workers + Celery Beat
  - Frontend: Static HTML/JS served via Nginx
  - Rider App: Separate static app (can be deployed separately)
  - All share PostgreSQL + Redis infrastructure

---

## 2. FOLDER STRUCTURE & PURPOSE

### 2.1 Top-Level Directories

```
/backend/                    # Main Django application (production-critical)
  ├── config/               # Django settings, ASGI/WSGI, Celery config
  ├── apps/                 # 15+ Django applications (modular business logic)
  │   ├── accounts/         # User management, authentication
  │   ├── orders/           # Order processing, status tracking
  │   ├── delivery/         # Rider assignment, real-time tracking (WebSocket)
  │   ├── riders/           # Rider management, earnings, payouts
  │   ├── inventory/        # Stock management, warehouse sync
  │   ├── payments/         # Payment processing, Razorpay integration
  │   ├── notifications/    # SMS/Email/Push notifications
  │   ├── audit/            # Compliance & transaction logging
  │   ├── core/             # Shared utilities, middleware, scheduled tasks
  │   └── (8+ other apps)   # Catalog, customers, pricing, locations, etc.
  ├── scripts/              # Entrypoint script, database setup
  ├── manage.py             # Django CLI
  ├── Dockerfile            # Backend container (Gunicorn + optional Celery)
  └── requirements.txt      # Python dependencies

/frontend/                   # Static SPA (customer-facing web app)
  ├── index.html            # Main SPA entry point
  ├── auth.html, cart.html  # Page templates
  ├── nginx.conf            # Reverse proxy + API routing config
  ├── config.local.json     # Frontend config (API URL, Google Maps key)
  ├── assets/               # CSS, JS, images
  ├── Dockerfile            # Nginx container
  ├── entrypoint.sh         # Runtime API URL injection
  └── package.json          # Node dev dependencies (http-server, Playwright tests)

/rider_app/                  # Rider mobile web app (SECONDARY - can skip initially)
  ├── index.html, dashboard.html
  ├── assets/               # Rider app static files
  └── (deployment: optional separate service)

/docker-compose.yml         # Local dev orchestration (5 services: db, redis, backend, celery, beat)
/requirements.txt           # Root-level Python deps (can be used for monorepo installs)
/README.md                  # Basic documentation

```

### 2.2 Critical vs. Optional for v1 Launch

**DEPLOY IN RAILWAY (Required for MVP):**
- ✅ Backend API (Django + Gunicorn)
- ✅ Frontend (Nginx)
- ✅ PostgreSQL Database
- ✅ Redis Cache (for sessions, Celery broker)
- ✅ Celery Worker (for async jobs: SMS, email, payments, rider assignments)
- ✅ Celery Beat (for scheduled tasks: inventory sync, payout processing)

**SKIP / DEFER (Not needed for free tier):**
- ❌ Rider App (deploy later as separate Railway service or as mobile app)
- ❌ AWS S3 (use local file storage initially; Railway has 512MB ephemeral disk per service)
- ❌ Sentry (optional; add later for error tracking)
- ❌ Prometheus metrics (optional; add later for monitoring)

---

## 3. BACKEND DETAILS

### 3.1 Framework & Structure

**Framework:** Django 5.1+ with Django REST Framework (DRF)

**Application Architecture:**
```
Backend = Monolithic Django app
├── 15+ independent Django apps (modular)
├── Shared database (PostgreSQL + PostGIS)
├── Asynchronous job processing (Celery + Redis)
├── Real-time WebSocket support (Django Channels)
└── Multiple service entry points:
    ├── HTTP REST API (Gunicorn + Uvicorn)
    ├── Celery Worker (async task processor)
    └── Celery Beat (scheduler daemon)
```

### 3.2 How Backend Starts in Production

**Primary Container (Backend API):**
```bash
# Via entrypoint.sh with IS_PRIMARY=1:
1. Wait for PostgreSQL to be ready
2. Wait for Redis to be ready
3. Run migrations: python manage.py migrate --noinput
4. Collect static files: python manage.py collectstatic --noinput --clear
5. Start Gunicorn ASGI server:
   gunicorn config.asgi:application \
     -k uvicorn.workers.UvicornWorker \
     --bind 0.0.0.0:5000 \
     --workers 3 \
     --timeout 120
```

**Worker Container (Celery Worker):**
```bash
# Via docker-compose override command:
celery -A config.celery worker -l info --concurrency=2
```

**Scheduler Container (Celery Beat):**
```bash
# Via docker-compose override command:
celery -A config.celery beat -l info
```

### 3.3 Database Used

**PostgreSQL 15 + PostGIS Extension**

Why PostGIS?
- Real-time delivery tracking with geospatial queries
- Rider location filtering, geofencing, distance calculations
- Store location coordinates, delivery zones, service areas

**Connection Details (from settings.py):**
```python
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",  # ← PostGIS
        "NAME": os.getenv("POSTGRES_DB", "quickdash"),
        "USER": os.getenv("POSTGRES_USER", "quickdash"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "quickdash_secure"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}
```

**Alternative for Railway:**
Railway supports PostgreSQL with PostGIS. Use Railway's managed PostgreSQL + enable PostGIS extension.

### 3.4 Redis, Celery & Workers

**Redis Usage (3 critical functions):**

1. **Celery Message Broker** (task queue)
   - Stores pending async jobs from backend
   - Workers pull tasks from Redis queue

2. **Celery Result Backend** (task results storage)
   - Stores job completion status & results

3. **Django Cache** (session storage, rate limiting)
   - Django caching framework uses Redis
   - Session storage for JWT/auth tokens

**Configuration:**
```python
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
    }
}
```

**Celery Setup:**

Queue Configuration (3 priority levels):
```python
TASK_QUEUES = (
    Queue('default', routing_key='default'),
    Queue('high_priority', routing_key='high_priority'),  # Rider assignments, OTP SMS
    Queue('low_priority', routing_key='low_priority'),    # AI assistant queries
)
```

**Scheduled Tasks (Celery Beat):**

| Task | Frequency | Purpose |
|------|-----------|---------|
| `reconcile_inventory_redis_db` | Every 10 min | Sync Redis cache with DB |
| `monitor_stuck_orders` | Every 5 min | Detect orders in limbo |
| `periodic_assign_unassigned_orders` | Every 5 min | Auto-assign to idle riders |
| `process_daily_payouts` | Daily @ 1 AM | Calculate & process rider earnings |
| `beat_heartbeat` | Every minute | Health check signal |

**Worker Reliability Features:**
- ✅ `task_acks_late = True` (acknowledge after completion, not before)
- ✅ `worker_prefetch_multiplier = 1` (fetch one task at a time)
- ✅ `task_reject_on_worker_lost = True` (retry if worker crashes)
- ✅ `broker_connection_retry_on_startup = True` (retry Redis connection on boot)

### 3.5 Static Files & Media Handling

**Current Setup (LOCAL FILE STORAGE):**
```python
USE_S3 = os.getenv("USE_S3", "0") == "1"  # Disabled by default

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"     # Django admin CSS/JS
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"            # User uploads (images, documents)
```

**Issue for Railway:**
- Railway services have **ephemeral 512MB disks**
- Files are **lost when container restarts** (no persistence)
- **Solution: Enable S3 storage for production**

**FOR RAILWAY FREE TIER (Temporary Solution):**
- Keep local storage initially
- Accept that media uploads are lost on restarts
- Upgrade later: enable AWS S3 or Railway's persistent volumes

---

## 4. FRONTEND DETAILS

### 4.1 Framework & Build

**Framework:** Vanilla HTML/CSS/JavaScript (Static SPA)
- No React, Vue, or Next.js build step
- Served as static files via Nginx
- Client-side routing (try_files fallback to index.html)

**Build Command:** 
- None needed! Frontend is pre-built static files
- Just copy HTML/CSS/JS to Nginx container

**Start Command (Production):**
```bash
nginx -g "daemon off;"  # Run in foreground (Docker requirement)
```

**Served on Port:** 80 (HTTP, no HTTPS on Railway free tier yet)

### 4.2 Environment Variables (Frontend)

**Frontend Config Injection:**

The `entrypoint.sh` script injects the backend API URL at **runtime** (not build-time):

```bash
# Environment variable:
API_BASE_URL=https://backend-service.railway.app

# Script replaces in config.js:
sed -i "s|const apiBase = .*|const apiBase = \"$API_BASE_URL\";|g" /usr/share/nginx/html/assets/js/config.js
```

**Required Frontend Env Vars:**

| Variable | Example | Purpose |
|----------|---------|---------|
| `API_BASE_URL` | `https://backend.railway.app` | Backend API root URL |
| `GOOGLE_MAPS_KEY` | `AIza...` | Google Maps JavaScript API key |

**Note:** Google Maps key can be in `config.local.json` (hardcoded) or injected from env vars.

### 4.3 Frontend Architecture

**Nginx Config Highlights (`nginx.conf`):**

```nginx
# 1. SPA Routing (fallback to index.html for client-side routing)
location / {
    try_files $uri $uri/ /index.html;
}

# 2. API Proxy (requests to /admin/ forwarded to Django backend)
location /admin/ {
    proxy_pass http://backend:5000;
    proxy_set_header Host $host;
}

# 3. Django Media (user uploads)
location /media/ {
    alias /usr/share/nginx/html/media/;
}

# 4. Django Static (admin CSS/JS from collectstatic)
location /static/ {
    alias /usr/share/nginx/html/static/;
}

# 5. Asset Caching (1 year for images/CSS/JS)
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
    expires 1y;
}
```

**Important:** Nginx expects static/media files to be in `/usr/share/nginx/html/`. These come from Django's `collectstatic` command, which is run by the **backend container during startup**.

---

## 5. DOCKER SETUP

### 5.1 Backend Dockerfile Breakdown

```dockerfile
# Base image: Python 3.12 with system libraries
FROM python:3.12-slim

# Python environment variables (no .pyc files, unbuffered logs)
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# System dependencies for:
#   - gcc: Python package compilation
#   - libpq-dev: PostgreSQL client
#   - libgdal-dev: PostGIS/geospatial libraries
#   - libmagic1: File type detection
RUN apt-get install -y gcc libpq-dev gdal-bin libmagic1 ...

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt && pip install gunicorn uvicorn

# Copy application code
COPY . .

# Create non-root user (security best practice)
RUN adduser --system appuser && chown -R appuser /app

# Expose port
EXPOSE 5000

# Run via entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```

### 5.2 Frontend Dockerfile Breakdown

```dockerfile
# Base image: Nginx with Alpine Linux (minimal)
FROM nginx:stable-alpine

# Copy Nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy frontend static files
COPY --chown=appuser . /usr/share/nginx/html

# Copy entrypoint script (for runtime API URL injection)
COPY entrypoint.sh /entrypoint.sh

# Create non-root user
RUN adduser -D -u 1000 appuser

# Expose port
EXPOSE 80

# Run via entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
```

### 5.3 docker-compose.yml Structure

**5 Services in Local Dev:**

```yaml
services:
  db:
    image: postgis/postgis:15-3.3
    ports: 5432
    volumes: postgres_data (persistent)
    
  redis:
    image: redis:7.2-alpine
    ports: 6379
    
  backend:
    build: ./backend
    ports: 5000
    depends_on: db, redis (with health checks)
    environment: RUN_GUNICORN=1, IS_PRIMARY=1
    
  celery_worker:
    build: ./backend
    command: celery -A config.celery worker -l info
    depends_on: db, redis
    environment: RUN_GUNICORN=0, IS_PRIMARY=0
    
  celery_beat:
    build: ./backend
    command: celery -A config.celery beat -l info
    depends_on: db, redis
    environment: RUN_GUNICORN=0, IS_PRIMARY=0
```

**Frontend NOT in docker-compose** (must be deployed separately).

### 5.4 Service Interdependencies

```
┌─────────────┐
│   Backend   │◄─── IS_PRIMARY=1 (runs migrations, collectstatic)
│ (Gunicorn)  │
│   :5000     │
└──────┬──────┘
       │
       ├──► PostgreSQL (reads/writes orders, inventory, users)
       │
       ├──► Redis (cache, sessions, Celery broker)
       │
       └──► Channels Redis (WebSocket state)

┌──────────────────────┐
│ Celery Worker        │◄─── Consumes tasks from Redis queue
│ (background jobs)    │
│ :concurrency=2       │
└──────────┬───────────┘
           │
           ├──► PostgreSQL (writes task results, updated orders)
           │
           ├──► Redis (reads task queue)
           │
           └──► External APIs (SMS, email, Razorpay, Google Maps)

┌──────────────────────┐
│ Celery Beat          │◄─── Schedules periodic tasks
│ (scheduler daemon)   │
└──────────┬───────────┘
           │
           └──► Redis (publishes scheduled tasks)

┌──────────────────────┐
│ Frontend (Nginx)     │◄─── Serves static HTML/CSS/JS
│ :80                  │
└──────────┬───────────┘
           │
           └──► Proxies /admin/* requests to Backend :5000
                (API requests, DRF, admin panel)
```

---

## 6. PRODUCTION READINESS CHECK

### 6.1 What Will Break on Railway Free Tier

| Issue | Impact | Severity |
|-------|--------|----------|
| **Ephemeral Disk (512MB)** | Media uploads lost on restart | 🔴 CRITICAL |
| **No persistent volumes** | Static files regenerated each boot (slow) | 🟡 MEDIUM |
| **1 CPU, 512MB RAM** | Celery workers may timeout on heavy loads | 🟡 MEDIUM |
| **No background job persistence** | Celery tasks in queue lost if Redis crashes | 🟡 MEDIUM |
| **Cold starts** | Gunicorn + 3 workers takes ~10 sec to boot | 🟡 MEDIUM |
| **No SSL/TLS (free)** | HTTP only (no HTTPS) | 🟡 MEDIUM |
| **No cron job infrastructure** | Celery Beat is stateful & singleton | 🟡 MEDIUM |

### 6.2 Must-Change for Production

**1. Environment Variables**
```
Change from local hardcoded values:
DEBUG=0                           # ← Set to 0 (disable debug mode)
DJANGO_SECRET_KEY=<generate>      # ← Generate secure key
ALLOWED_HOSTS=yourdomain.railway  # ← Set actual domain
POSTGRES_PASSWORD=<secure>        # ← Set strong password
REDIS_URL=<Railway_Redis>         # ← Point to Railway Redis
CORS_ALLOWED_ORIGINS=*            # ← Restrict to frontend URL
```

**2. Database Migrations**
- Railway will run migrations on first deploy, BUT entrypoint.sh already handles this
- Ensure `IS_PRIMARY=1` is set on backend service (only one can migrate)

**3. Security Headers**
- Currently DISABLED for local dev (HTTP only)
- In production (non-DEBUG), Django automatically enables:
  - `SECURE_PROXY_SSL_HEADER` (trust Railway's X-Forwarded-Proto)
  - `SECURE_SSL_REDIRECT` (force HTTPS)
  - `SECURE_HSTS_SECONDS` (strict transport security)

**4. Media File Storage**
```python
# Current: USE_S3=0 (local filesystem)
# Railway free: Accept data loss on redeploy
# Railway paid: Use Railway Postgres file storage or S3
```

**5. Remove Docker Volume Mounts**
```yaml
# In docker-compose: OK for dev
volumes:
  - ./backend:/app
  - static_volume:/app/staticfiles
  - media_volume:/app/media

# In Railway: Not possible (must use ephemeral disk or S3)
```

### 6.3 Separation Strategy for Railway

**Railway Service = Container Running One Process**

**Recommended 4 Services:**

| Service | Runs | Count | Scale | Cost |
|---------|------|-------|-------|------|
| 1. **Backend API** | Gunicorn + Uvicorn | 1 | Manual after MVP | $5/mo |
| 2. **Celery Worker** | celery worker | 1-2 | Manual based on queue | $5/mo each |
| 3. **Celery Beat** | celery beat | 1 | Fixed (singleton) | $5/mo |
| 4. **Frontend** | Nginx | 1 | Fixed | $5/mo |
| 5. **PostgreSQL** | Managed DB | 1 | Managed by Railway | ~$7/mo |
| 6. **Redis** | Managed Redis | 1 | Managed by Railway | ~$7/mo |

**Can Stay Together (if co-located):**
- Backend API + Celery Beat (share one Railway service) ❌ **NOT RECOMMENDED** (Celery Beat must be singleton, unpredictable restarts)

**Better Approach: Separate Everything**
- Easier to scale workers independently
- Cleaner logs & debugging
- Fault isolation (one component dies ≠ all die)

### 6.4 What Can Stay Together

**Technically:**
- Frontend + Backend API (both single-threaded, HTTP-only) → But no good reason
- Celery Beat + Celery Worker → **NO** (Beat must be singleton, Worker can scale)

**Best Practice:**
- Keep each service isolated in its own Railway container
- Use environment variables to pass service URLs (backend, redis, db)
- Easier to debug, monitor, and scale

---

## 7. RAILWAY DEPLOYMENT PLAN

### 7.1 Number of Railway Services Required

**FOR FREE TIER MVP:**

| Service | Type | Railway Component | Env | Auto-Deploy |
|---------|------|-------------------|-----|-------------|
| 1. **Backend API** | GitHub Repo | Docker (build from Dockerfile) | `backend/Dockerfile` | Yes (webhook) |
| 2. **Celery Worker** | GitHub Repo | Docker (same repo, different start cmd) | `backend/Dockerfile` | Yes |
| 3. **Celery Beat** | GitHub Repo | Docker (same repo, different start cmd) | `backend/Dockerfile` | Yes |
| 4. **Frontend** | GitHub Repo | Docker (build from Dockerfile) | `frontend/Dockerfile` | Yes |
| 5. **PostgreSQL** | Railway Add-on | Managed database | - | Auto |
| 6. **Redis** | Railway Add-on | Managed cache | - | Auto |

**Total Railway Services = 6** (4 custom + 2 managed)

**Free Tier Usage:**
- 100 hours/month compute (≈ 4 days continuous at 1 CPU)
- $5/mo per additional service (1st 100 hrs free)
- Cost for MVP: ~$15-25/mo (3-4 services + managed DB/Redis)

### 7.2 Backend API Service

**Service Name:** `quickdash-backend`

**Configuration:**
```
GitHub Repo: your-repo
Build: Dockerfile (backend/Dockerfile)
Start Command: (leave blank; uses entrypoint.sh)
Port: 5000
Environment Variables:
  - DEBUG=0
  - DJANGO_SECRET_KEY=<generate>
  - ALLOWED_HOSTS=quickdash-backend.railway.app,yourdomain.com
  - POSTGRES_HOST=<Railway DB host>
  - POSTGRES_DB=quickdash
  - POSTGRES_USER=postgres
  - POSTGRES_PASSWORD=<Railway DB password>
  - REDIS_URL=<Railway Redis URL>
  - IS_PRIMARY=1 (runs migrations)
  - RUN_GUNICORN=1
  - DJANGO_ENV=production
```

**Health Check:**
```
GET /health/
Expected Response: 200 OK
```

### 7.3 Celery Worker Service

**Service Name:** `quickdash-worker`

**Configuration:**
```
GitHub Repo: same as backend
Build: Dockerfile (backend/Dockerfile)
Start Command: celery -A config.celery worker -l info --concurrency=2
Port: (none, no HTTP)
Environment Variables: (same as backend except IS_PRIMARY=0, RUN_GUNICORN=0)
Restart Policy: Always (crashes are expected; auto-restart)
```

**Scaling:**
- Start with 1 worker (concurrency=2)
- If queue backs up, add 2nd worker (Railway clones service)
- Monitor with: `celery -A config.celery inspect active`

### 7.4 Celery Beat Service

**Service Name:** `quickdash-beat`

**Configuration:**
```
GitHub Repo: same as backend
Build: Dockerfile (backend/Dockerfile)
Start Command: celery -A config.celery beat -l info
Port: (none, no HTTP)
Environment Variables: (same as backend)
Restart Policy: Always
Max Instances: 1 (must be singleton; only one can schedule tasks)
```

**Important:** Do NOT scale Beat. Multiple instances = duplicate tasks.

### 7.5 Frontend Service

**Service Name:** `quickdash-frontend`

**Configuration:**
```
GitHub Repo: same as backend
Build: Dockerfile (frontend/Dockerfile)
Start Command: (leave blank; uses entrypoint.sh + CMD)
Port: 80
Environment Variables:
  - API_BASE_URL=https://quickdash-backend.railway.app
  - GOOGLE_MAPS_KEY=<your key>
```

**Note:** Frontend listens on HTTP only (Railway provides SSL termination at edge).

### 7.6 Database Strategy

**Option A: Railway PostgreSQL (RECOMMENDED FOR MVP)**
```
✅ Setup: Click "Add Service" → PostgreSQL
✅ Auto-configured: Connection string in Railway env vars
✅ Backups: Daily backups included
✅ PostGIS: Install via psql: CREATE EXTENSION postgis;
✅ Cost: ~$7/mo
⚠️ Limitation: 5GB storage on free tier (should be enough for MVP)
```

**Option B: External Postgres (e.g., AWS RDS, Neon, Supabase)**
```
✅ More control
❌ Additional $$ (typically $10-20/mo minimum)
❌ More setup, manual connection management
```

**For MVP:** Use Railway Postgres (simpler, included).

**Enable PostGIS (one-time setup):**
```bash
# Connect to Railway Postgres via Railway CLI or local psql
psql -h $POSTGRES_HOST -U postgres -d quickdash
> CREATE EXTENSION postgis;
> \dx  # Verify extension loaded
```

### 7.7 Redis Strategy

**Option A: Railway Redis (RECOMMENDED FOR MVP)**
```
✅ Setup: Click "Add Service" → Redis
✅ Auto-configured: URL in Railway env vars
✅ Cost: ~$7/mo
✅ 512MB should cover: Celery queue + session cache for MVP
```

**Option B: Remove Redis Temporarily (NOT RECOMMENDED)**
```
❌ Breaks: Celery tasks (needs queue)
❌ Breaks: WebSocket support (Channels Redis)
❌ Breaks: Django sessions
```

**Option C: Upstash Redis (External, free tier)**
```
✅ Free tier: 10K commands/day (barely sufficient)
❌ Limited for production
❌ Requires manual connection
```

**For MVP:** Use Railway Redis.

---

## 8. ENVIRONMENT VARIABLES LIST

### 8.1 Backend Environment Variables (COMPLETE LIST)

**Django Core:**
```env
DJANGO_ENV=production                          # production/development
DEBUG=0                                        # 0=False (security)
DJANGO_SECRET_KEY=<GENERATE_SECURE_KEY>        # Used for session signing
ALLOWED_HOSTS=backend.railway.app,yourdomain   # CSV of allowed domains
```

**Database (PostgreSQL):**
```env
POSTGRES_HOST=<Railway_DB_hostname>             # e.g., containers-us-west-XXX.railway.app
POSTGRES_PORT=5432                             # Standard PostgreSQL port
POSTGRES_DB=quickdash                          # Database name
POSTGRES_USER=postgres                         # PostgreSQL username
POSTGRES_PASSWORD=<RAILWAY_DB_PASSWORD>        # Auto-generated by Railway
```

**Redis & Celery:**
```env
REDIS_URL=redis://<Railway_Redis_password>@<host>:6379/0
CELERY_BROKER_URL=${REDIS_URL}                 # Celery message queue
CELERY_RESULT_BACKEND=${REDIS_URL}             # Celery result storage
```

**Security & CORS:**
```env
CORS_ALLOWED_ORIGINS=https://frontend.railway.app,https://yourdomain  # CSV
CSRF_TRUSTED_ORIGINS=https://frontend.railway.app,https://yourdomain  # CSV
JWT_SIGNING_KEY=<GENERATE_JWT_SECRET>          # JWT token signing
```

**Storage (Initially Disable S3):**
```env
USE_S3=0                                       # 0=local, 1=S3
# AWS_ACCESS_KEY_ID=xxx                       # (leave empty for now)
# AWS_SECRET_ACCESS_KEY=xxx                   # (leave empty for now)
# AWS_STORAGE_BUCKET_NAME=xxx                 # (leave empty for now)
```

**Payment Gateway (Razorpay):**
```env
RAZORPAY_KEY_ID=<your_razorpay_public_key>
RAZORPAY_KEY_SECRET=<your_razorpay_secret>
RAZORPAY_WEBHOOK_SECRET=<your_webhook_secret>
```

**Third-Party APIs:**
```env
GOOGLE_MAPS_KEY=<your_google_maps_api_key>    # Geolocation, distance matrix
SENTRY_DSN=<your_sentry_dsn>                  # Error tracking (optional)
```

**Business Logic:**
```env
RIDER_FIXED_PAY_PER_ORDER=50                  # ₹50 per delivery
```

**Process Control (Set by Railway):**
```env
IS_PRIMARY=1                                   # Backend API only (not Celery)
RUN_GUNICORN=1                                 # Backend API: yes; Celery: no
PORT=5000                                      # Gunicorn listen port
```

### 8.2 Frontend Environment Variables

**Minimal (Frontend is static):**
```env
API_BASE_URL=https://backend.railway.app                    # Backend API endpoint
GOOGLE_MAPS_KEY=<your_google_maps_api_key>                  # Frontend Google Maps
```

**Injection Mechanism:**
- Entrypoint script replaces placeholders in `assets/js/config.js`
- Happens at container startup, not build time
- No build-time dependencies

### 8.3 Which Variables Are Secrets?

**🔐 SECRETS (Store in Railway Secrets, NOT in code):**
- `DJANGO_SECRET_KEY` (Django session signing)
- `POSTGRES_PASSWORD` (DB access)
- `JWT_SIGNING_KEY` (JWT token signing)
- `RAZORPAY_KEY_SECRET` (Payment processing)
- `RAZORPAY_WEBHOOK_SECRET` (Payment webhooks)
- `AWS_SECRET_ACCESS_KEY` (S3 access; if using)
- `SENTRY_DSN` (Error tracking; contains token)
- `CELERY_BROKER_URL` (contains Redis password)

**🟡 SEMI-PUBLIC (Can be in env vars or config):**
- `API_BASE_URL` (public; in frontend config.js anyway)
- `GOOGLE_MAPS_KEY` (restricted by domain in Google Cloud; semi-public)
- `RAZORPAY_KEY_ID` (public key; OK to expose)
- `CORS_ALLOWED_ORIGINS` (public list; defines security policy)
- `ALLOWED_HOSTS` (public domain list)

**Generate Secure Keys:**
```bash
# Django SECRET_KEY
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# JWT_SIGNING_KEY (can be same as DJANGO_SECRET_KEY or different)
python -c 'import secrets; print(secrets.token_urlsafe(50))'
```

---

## 9. STEP-BY-STEP RAILWAY DEPLOYMENT SUMMARY

### 9.1 Prerequisites

- [ ] GitHub repo with code pushed
- [ ] Railway account (free tier)
- [ ] Docker Hub account (optional; if Railway can't build)
- [ ] Razorpay account (for payments)
- [ ] Google Maps API key (for geolocation)

### 9.2 Exact Deployment Steps

#### Step 1: Initialize Railway Project
```bash
# In Railway web dashboard:
1. Click "New" → "GitHub Repository"
2. Select your repo (auth with GitHub)
3. Railway auto-detects docker-compose.yml OR Dockerfile
4. Select service to deploy (choose "Backend" first)
```

#### Step 2: Deploy Backend API Service
```bash
# Railway Dashboard → Add Service → GitHub:
Service Name: quickdash-backend
GitHub Repo: <your-repo>
Dockerfile: backend/Dockerfile
Branch: main

# Variables (go to Service → Variables):
DJANGO_ENV=production
DEBUG=0
DJANGO_SECRET_KEY=<generate>
ALLOWED_HOSTS=quickdash-backend.railway.app
IS_PRIMARY=1
RUN_GUNICORN=1

# Trigger deploy:
→ Save → Railway auto-builds and deploys
→ Logs show Gunicorn startup
→ Service gets URL: https://quickdash-backend.railway.app
```

#### Step 3: Create PostgreSQL Service
```bash
# Railway Dashboard → New → Add PostgreSQL:
Tier: Hobby (free)
Region: Same as backend

# Railway auto-injects into backend:
POSTGRES_HOST=<auto>
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<auto>
POSTGRES_DB=postgres

# Rename database:
psql -h $POSTGRES_HOST -U postgres
> CREATE DATABASE quickdash;
> CREATE EXTENSION postgis;
```

#### Step 4: Create Redis Service
```bash
# Railway Dashboard → New → Add Redis:
Tier: Hobby (free)
Region: Same as backend

# Railway auto-injects:
REDIS_URL=redis://<password>@<host>:6379
```

#### Step 5: Update Backend Environment Variables
```bash
# Backend Service → Variables (update):
POSTGRES_HOST=<copy from PostgreSQL service>
POSTGRES_DB=quickdash
POSTGRES_PASSWORD=<copy from PostgreSQL service>
REDIS_URL=<copy from Redis service>
CORS_ALLOWED_ORIGINS=https://quickdash-frontend.railway.app
CELERY_BROKER_URL=${REDIS_URL}
CELERY_RESULT_BACKEND=${REDIS_URL}

# Redeploy:
→ Save → Railway redeploys
→ Backend now connects to real DB + Redis
```

#### Step 6: Deploy Celery Worker Service
```bash
# New Service → GitHub repo:
Service Name: quickdash-worker
Dockerfile: backend/Dockerfile
Start Command: celery -A config.celery worker -l info --concurrency=2

# Copy all variables from backend:
IS_PRIMARY=0
RUN_GUNICORN=0
(rest same as backend)

# Deploy
```

#### Step 7: Deploy Celery Beat Service
```bash
# New Service → GitHub repo:
Service Name: quickdash-beat
Dockerfile: backend/Dockerfile
Start Command: celery -A config.celery beat -l info

# Copy variables from backend:
IS_PRIMARY=0
RUN_GUNICORN=0

# Important: Set max instances = 1 (singleton)
→ Settings → Max instances: 1

# Deploy
```

#### Step 8: Deploy Frontend Service
```bash
# New Service → GitHub repo:
Service Name: quickdash-frontend
Dockerfile: frontend/Dockerfile
Port: 80

# Variables:
API_BASE_URL=https://quickdash-backend.railway.app
GOOGLE_MAPS_KEY=<your key>

# Deploy
```

#### Step 9: Verify Deployments & Test

**Check Backend:**
```bash
curl https://quickdash-backend.railway.app/admin/login/
# Expected: 200 OK (Django admin login page)
```

**Check Frontend:**
```bash
# Browser: https://quickdash-frontend.railway.app
# Expected: Your SPA loads, API calls go to backend
```

**Check Celery Workers:**
```bash
# Backend service logs:
# Should see: "Waiting for Redis" → "Redis is available"

# Worker service logs:
# Should see: "[*] celery@<worker-id> ready."

# Beat service logs:
# Should see: "[beat] Scheduler started"
```

**Check Database Connection:**
```bash
# Backend logs should show:
# "Running migrations..."
# "0XX migrations applied"
```

**Trigger Test Task:**
```bash
# From backend shell:
python manage.py shell
>>> from apps.core.tasks import beat_heartbeat
>>> beat_heartbeat.delay()

# Check logs on worker service (should process task)
```

### 9.3 What Railway Will Run Automatically

| When | What Runs |
|------|-----------|
| Service Deploy | `docker build` using specified Dockerfile |
| Container Start | Entrypoint script (backend: migrations + collectstatic) |
| Every Restart | entrypoint.sh runs again (idempotent) |
| On Redeploy | Full container rebuild (no cached layers) |

### 9.4 Post-Deployment Health Check

**Backend API Health:**
```bash
# Check REST API
curl -X GET "https://quickdash-backend.railway.app/api/health/" \
  -H "Content-Type: application/json"
  
# Expected: {"status": "ok"}
```

**Database Health:**
```bash
# From Railway shell on backend:
python manage.py dbshell
> SELECT version();  # Should show PostgreSQL + PostGIS
> SELECT COUNT(*) FROM django_migrations;  # Should show migrations applied
```

**Celery Health:**
```bash
# From Railway shell on backend:
python manage.py shell
>>> from celery import current_app
>>> current_app.control.inspect().active()  # Show active tasks
>>> current_app.control.inspect().stats()   # Show worker stats
```

**Redis Health:**
```bash
# From Railway shell on backend:
python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test', 'hello')
>>> cache.get('test')  # Should return 'hello'
```

**Frontend Connectivity:**
```bash
# Browser DevTools → Network tab
# When you load frontend:
1. Should load HTML from Nginx (200 OK)
2. Should load CSS/JS (200 OK)
3. When making API call, should go to https://backend.railway.app
4. Should receive response (or 401 if not authenticated)
```

### 9.5 Monitoring & Logs

**View Logs in Railway:**
```
Dashboard → Service → Logs tab
Filter by: "ERROR", "WARNING", "INFO"
Tail live logs for debugging
```

**Common Issues & Fixes:**

| Issue | Fix |
|-------|-----|
| "Connection refused: Redis" | Check REDIS_URL in env vars |
| "psycopg2: connection rejected" | Check POSTGRES_HOST, POSTGRES_PASSWORD |
| "Static files not found (404)" | Ensure IS_PRIMARY=1 on one backend instance |
| "Celery worker not processing tasks" | Check CELERY_BROKER_URL, Redis connection |
| "CORS error on frontend" | Check CORS_ALLOWED_ORIGINS in backend env |
| "Media files missing" | Expected on Railway free tier (ephemeral disk) |

---

## 10. QUICK REFERENCE: FREE TIER RAILWAY COSTS

**100 hours/month free compute = ~4 days continuous use**

| Service | Count | Hours/Month | Cost | Notes |
|---------|-------|-------------|------|-------|
| Backend API | 1 | 100 | $0 (free tier) | If < 100 hrs |
| Celery Worker | 1 | 100 | $5 | Or $0 if off-peak |
| Celery Beat | 1 | 100 | $5 | Always running |
| Frontend | 1 | 100 | $5 | Always running |
| PostgreSQL | 1 | - | $7 | Managed DB (always on) |
| Redis | 1 | - | $7 | Managed cache (always on) |
| **TOTAL** | - | 300 | **$24-29/mo** | Or $5-10 if optimize |

**How to Minimize Costs:**
1. Turn off Celery Worker during off-hours (manual)
2. Run Celery Beat with worker (combine into 1 service) ❌ BAD (loses scheduling)
3. Use external free Redis (Upstash) instead of Railway ✅ But limited throughput
4. Use SQLite instead of Postgres ❌ WON'T WORK (need PostGIS for geolocation)

**Bottom Line:**
- Minimum viable: **~$24/mo** for full stack
- For free: Deploy backend API only, keep Celery/Beat on local machine or turn off

---

## 11. DEPLOYMENT SUMMARY FOR NEXT STEP

### Quick Checklist Before Deployment:

- [ ] GitHub repo initialized with all code
- [ ] `.env` file NOT committed (use Railway secrets)
- [ ] `Dockerfile`s in `backend/` and `frontend/` verified working locally
- [ ] `docker-compose.yml` working (all services start cleanly)
- [ ] Database migrations tested locally
- [ ] Celery tasks can be triggered and processed
- [ ] Frontend loads and communicates with backend API
- [ ] All external API keys ready (Razorpay, Google Maps)

### Next Actions:

1. **Generate Security Keys:**
   ```bash
   # Django SECRET_KEY
   python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
   
   # JWT_SIGNING_KEY
   python -c 'import secrets; print(secrets.token_urlsafe(50))'
   ```

2. **Create Railway Project:**
   - Navigate to railway.app
   - Click "Start a New Project"
   - Choose "GitHub Repository"

3. **Connect Repo & Deploy Services:**
   - Follow Section 9.2 steps in exact order
   - Start with Backend, then add supporting services

4. **Configure Environment:**
   - Use generated keys
   - Set domain names when available
   - Enable SSL once custom domain added

5. **Test Health Endpoints:**
   - Verify all 6 services are running
   - Check logs for errors
   - Test API and frontend connectivity

---

## 12. ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────────┐
│                        RAILWAY DEPLOYMENT                        │
└─────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│ INTERNET / USER BROWSER                                            │
└────────────┬─────────────────────────────────────────────────────┘
             │
             ├─ https://quickdash-frontend.railway.app (port 80)
             │        │
             │        └──→ ┌──────────────────────┐
             │             │  FRONTEND (Nginx)    │
             │             │  1 Railway Service   │
             │             └──────────┬───────────┘
             │                        │ serves static HTML/CSS/JS
             │                        │ proxy to /admin/* → backend
             │
             ├─ https://quickdash-backend.railway.app (REST API)
             │        │
             │        └──→ ┌──────────────────────────┐
             │             │  BACKEND API (Gunicorn)  │
             │             │  1 Railway Service       │
             │             │  :5000                   │
             │             └──────────┬───────────────┘
             │                        │
             │        ┌───────────────┼───────────────┐
             │        ├─ reads/writes orders, users,  │
             │        │  inventory, payments, etc.    │
             │        │                                │
             │        ├─ publishes async jobs to      │
             │        │  Celery message queue         │
             │        │                                │
             │        └─ manages WebSocket (Channels) │
             │           for real-time updates
             │
             │
             ├────────────────────────────────────────────┐
             │                                            │
             │   ┌──────────────────────────────────┐     │
             │   │   PostgreSQL 15 + PostGIS        │     │
             │   │   Railway Managed Database       │     │
             │   │   (shared by all backend services)     │
             │   └──────────────────────────────────┘     │
             │                                            │
             │   ┌──────────────────────────────────┐     │
             │   │   Redis (message broker)         │     │
             │   │   Railway Managed Redis          │     │
             │   │   (Celery queue + Django cache)  │     │
             │   └──────────────────────────────────┘     │
             │                                            │
             └────────────────────────────────────────────┘
             
             ┌──────────────────────────────────────────┐
             │  CELERY WORKER                           │
             │  1+ Railway Service(s)                   │
             │  celery -A config.celery worker          │
             │  --concurrency=2                          │
             │                                          │
             │  ├─ SMS notifications                   │
             │  ├─ Email alerts                         │
             │  ├─ Rider auto-assignment                │
             │  ├─ Payment processing                   │
             │  ├─ Inventory reconciliation             │
             │  └─ Stuck order detection                │
             └──────────────────────────────────────────┘
             
             ┌──────────────────────────────────────────┐
             │  CELERY BEAT (Singleton)                 │
             │  1 Railway Service (max instances = 1)   │
             │  celery -A config.celery beat            │
             │                                          │
             │  ├─ Schedules periodic tasks every 5min │
             │  ├─ Runs daily payout processor at 1 AM │
             │  └─ Health check heartbeat every minute  │
             └──────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  EXTERNAL SERVICES (referenced in code, not deployed)           │
├─────────────────────────────────────────────────────────────────┤
│  • Razorpay (payment gateway)                                    │
│  • Google Maps API (geolocation, distance matrix)                │
│  • Sentry (error tracking, optional)                             │
│  • AWS S3 (media storage, optional, currently disabled)          │
└─────────────────────────────────────────────────────────────────┘
```

---

## KEY TAKEAWAYS

✅ **QuickDash is production-ready for Railway**
- Django backend with modern async/real-time support
- Modular architecture (15+ apps)
- Containerized with Docker best practices
- All dependencies pinned in requirements.txt

✅ **Railway Free Tier Supports:**
- 100 hours compute/month
- Managed PostgreSQL + Redis
- Auto-scaling services
- GitHub auto-deployment

⚠️ **Railway Free Tier Limitations:**
- Ephemeral disk (media files lost on restart)
- Cold starts (~10 seconds)
- 512MB RAM per service (fine for MVP)
- HTTP only without custom domain + SSL

✅ **Deployment is Straightforward:**
- 4 custom services (backend, worker, beat, frontend)
- 2 managed services (PostgreSQL, Redis)
- Auto-builds from GitHub
- Env vars for configuration

**Estimated Cost: $24-29/month** for full production setup on Railway.

---

**Ready to deploy? Start with Step 9.2 (Exact Deployment Steps) above.** ✨
