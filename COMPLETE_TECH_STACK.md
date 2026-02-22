# 🚀 QuickDash Complete Tech Stack Breakdown

---

## 📋 Project Overview
**QuickDash** is a full-stack delivery management system with:
- Frontend (Customer Portal)
- Rider App (Delivery Partner App)  
- Backend API (REST + WebSocket)
- Database & Caching System
- Task Queue & Scheduling

---

## 1️⃣ FRONTEND (Customer Portal)

### Technology Stack:
- **HTML5** - Page structure and templates
- **CSS3** - Styling and responsive design
- **Vanilla JavaScript** - Client-side logic
- **http-server** - Local development server

### Key Features:
- Static HTML pages (No framework)
- **Playwright** - E2E testing framework
- Integration with Backend API (REST calls)
- Pages: 
  - `index.html` - Home/Landing
  - `auth.html` - Login/Registration
  - `addresses.html` - Delivery addresses
  - `cart.html` - Shopping cart
  - `orders.html` - Order tracking
  - `product.html` - Product listing
  - `checkout.html` - Payment checkout
  - `order_detail.html` - Order details
  - `track_order.html` - Live order tracking
  - `profile.html` - User profile
  - And more...

### Setup:
```bash
cd frontend
npm install
npm start  # Runs on http://localhost:8080
```

---

## 2️⃣ RIDER APP (Delivery Partner Portal)

### Technology Stack:
- **HTML5** - Page structure
- **CSS3** - Styling
- **Vanilla JavaScript** - App logic
- **http-server** - Dev server (Port 2000)

### Key Features:
- Rider dashboard
- Delivery assignments
- Real-time location tracking
- Earnings tracking
- **CORS enabled** for API communication

### Setup:
```bash
cd rider_app
npm install
npm start  # Runs on http://localhost:2000
```

---

## 3️⃣ BACKEND API (Django + DRF)

### Core Framework:
- **Django 5.1+** - Web framework
- **Django REST Framework (DRF)** - REST API
- **Python 3.12** - Runtime

### API Features:
```
Backend Apps Structure:
├── accounts/          # User authentication & authorization
├── customers/         # Customer data management
├── orders/           # Order management
├── delivery/         # Delivery logistics
├── riders/           # Rider management
├── inventory/        # Stock management
├── payments/         # Payment processing
├── notifications/    # Email & SMS notifications
├── audit/           # Activity logging
├── catalog/         # Products & categories
├── locations/       # Geographic locations
├── warehouse/       # Warehouse management
├── pricing/         # Dynamic pricing
├── assistant/       # AI assistant
└── core/           # Global utilities
```

### Authentication & Authorization:
- **JWT (json Web Tokens)** - `djangorestframework-simplejwt`
  - Token-based authentication
  - Access & Refresh tokens
  - Secure user sessions

### API Documentation:
- **drf-spectacular** - Auto-generated OpenAPI schema
- Swagger UI for testing
- Schema version: OpenAPI 3.0

### Database Interactions:
- **Django ORM** - Object-relational mapping
- Query optimization
- Migrations system

---

## 4️⃣ DATABASE LAYER 🗄️

### Primary Database:
**PostgreSQL 15 + PostGIS Extension**

```
Container: quickdash_db
Image: postgis/postgis:15-3.3
```

### Features:
- ✅ **PostGIS** - Geographic/Spatial data
  - Store rider & delivery locations
  - Distance calculations
  - Location-based queries
- ✅ **JSONB** - JSON data type
- ✅ **Full-text search** support
- ✅ **Transaction support** - ACID compliant
- ✅ **Connection pooling** - `conn_max_age=600`
- ✅ **Health checks** - Automatic connection validation

### Database Models:
```
Users → Orders → Deliveries → Riders
   ↓
Customers, Products, Inventory
   ↓
Payments, Notifications
   ↓
Audit Logs, Location Data
```

### Configuration:
- Engine: `django.contrib.gis.db.backends.postgis`
- Connection: Via `dj_database_url` package
- Environment variables:
  - `POSTGRES_DB`
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD`
  - `POSTGRES_HOST`
  - `POSTGRES_PORT` (default: 5432)

---

## 5️⃣ CACHING & SESSION MANAGEMENT 💾

### Redis 7.2 (Alpine)
```
Container: quickdash_redis
Image: redis:7.2-alpine
Port: 6379 (default)
```

### Uses:
- ✅ **Session storage** - User sessions
- ✅ **Cache backend** - `django-redis`
- ✅ **Message broker** - Celery task queue
- ✅ **WebSocket channel layer** - `channels-redis`
- ✅ **Real-time notifications** - Live updates
- ✅ **Rate limiting** - API throttling

### Cache Configuration:
```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://redis:6379/1",
    }
}
```

---

## 6️⃣ REAL-TIME COMMUNICATION 🔌

### Django Channels:
- **WebSocket support** - Live updates
- **ASGI server** - Async application gateway
- **Daphne** - ASGI HTTP/WebSocket server
- **channels-redis** - Channel layer backend

### Features:
- Live order updates
- Rider location tracking
- Real-time notifications
- Chat support (if enabled)
- Live delivery status

### ASGI Application:
```python
ASGI_APPLICATION = "config.asgi.application"
```

---

## 7️⃣ TASK QUEUE & ASYNC PROCESSING ⚙️

### Celery:
```
Version: 5.3+
Broker: Redis (6379)
Backend: Redis
```

### Components:

#### A) Celery Worker:
```bash
# Command run in Docker:
celery -A config.celery worker -l info --concurrency=2
```
- Processes async tasks
- 2 concurrent processes
- Auto-restart on failure

#### B) Celery Beat (Scheduler):
- **django-celery-beat** - Periodic task scheduling
- Runs scheduled jobs
- File: `celerybeat-schedule`
- Typical tasks:
  - Daily digest emails
  - Cleanup expired tokens
  - Update delivery status
  - Generate reports
  - Sync external APIs

### Task Examples:
- Send email notifications
- Process payments
- Update rider locations
- Generate invoices
- Cleanup temporary files

---

## 8️⃣ PAYMENT INTEGRATION 💳

### Razorpay Integration:
```python
# Package: razorpay>=1.4
from razorpay import Client

Features:
- Online payment processing
- Order tracking
- Refund management
- Multiple payment methods
```

### Workflow:
1. Create Razorpay order
2. Get payment link
3. Process payment
4. Webhook confirmation
5. Update order status

---

## 9️⃣ FILE STORAGE 📁

### AWS S3 Integration:
```python
# Packages: boto3>=1.28, django-storages>=1.14
```

### Features:
- Profile images
- Product photos
- Invoices/receipts
- Delivery proofs
- Static files in production

### Configuration:
```python
STORAGES = {
    "default": "storages.backends.s3boto3.S3Boto3Storage",
    "staticfiles": "storages.backends.s3boto3.S3StaticStorage",
}
```

---

## 🔟 SECURITY & MONITORING

### A) CORS (Cross-Origin Resource Sharing):
```python
# django-cors-headers
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "https://quickdash.com",
]
```

### B) Error Tracking (Sentry):
```python
# sentry-sdk>=1.30
import sentry_sdk

sentry_sdk.init(
    dsn="https://...",
    integrations=[
        DjangoIntegration(),
        RedisIntegration(),
        CeleryIntegration(),
    ],
)
```
- Track errors in production
- Monitor performance
- Alert on critical issues
- Version tracking

### C) Metrics & Monitoring (Prometheus):
```python
# django-prometheus
INSTALLED_APPS = [
    "django_prometheus",
]
MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    ...
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]
```
- Request/response metrics
- Database query metrics
- Cache hit/miss rates
- Error tracking

### D) API Documentation:
```python
# drf-spectacular
SPECTACULAR_SETTINGS = {
    "TITLE": "QuickDash API",
    "VERSION": "1.0.0",
    "SCHEMA_PATH_PREFIX": "/api/v1/",
}
```

---

## 1️⃣1️⃣ GEOLOCATION & MAPPING 🗺️

### Geopy:
```python
# geopy>=2.4
- Reverse geocoding (coords → addresses)
- Distance calculations
- Location lookup
```

### Django-Leaflet:
```python
# django-leaflet>=0.29.0
- OpenStreetMap integration
- Interactive maps
- Rider location display
- Delivery area visualization
```

---

## 1️⃣2️⃣ ADDITIONAL UTILITIES

### A) Image Processing:
```python
# Pillow>=10.0
- Image compression
- Thumbnail generation
- Format conversion
```

### B) Environment Configuration:
```python
# python-decouple>=3.8
- Load .env variables
- Type conversion
- Default values
```

### C) HTTP Requests:
```python
# requests>=2.31
- External API calls
- Webhooks
- Data fetching
```

### D) IP Detection:
```python
# django-ipware>=5.0
- Get client IP
- Filter by IP range
- Fraud detection
```

### E) File Type Detection:
```python
# python-magic==0.4.27
- Identify file types
- Validate uploads
- Security checks
```

### F) Fake Data Generation:
```python
# Faker>=19.0.0
- Generate test data
- Development fixtures
- Performance testing
```

---

## 1️⃣3️⃣ WEB SERVERS & DEPLOYMENT

### A) WSGI Servers:
```
Gunicorn (Production):
- WSGI server for Django
- Multi-worker support
- Configuration: gunicorn_conf.py
- Workers per CPU: 2-4x
- Threads per worker: 2-4
- Timeout: 30-120 seconds
```

### B) ASGI Servers:
```
Uvicorn (Production):
- ASGI server
- WebSocket support
- Async support
- Used with Channels
```

### C) Static File Serving:
```python
# whitenoise>=6.6.0
- Serve static files efficiently
- Compression (gzip)
- Cache busting
- No separate Nginx needed (optional)
```

### D) Reverse Proxy (Frontend):
```
Nginx Configuration:
- Port 80 (HTTP)
- Serve static files
- Proxy to backend
- SSL termination (optional)
```

---

## 1️⃣4️⃣ DOCKER & CONTAINERIZATION 🐳

### Docker Compose Services:

#### 1. Database Service:
```yaml
db:
  image: postgis/postgis:15-3.3
  container_name: quickdash_db
  env_file: .env
  volumes: postgres_data
  healthcheck: Running
```

#### 2. Redis Service:
```yaml
redis:
  image: redis:7.2-alpine
  container_name: quickdash_redis
  healthcheck: Running
```

#### 3. Backend Service:
```yaml
backend:
  build: ./backend
  depends_on: [db, redis]
  volumes: [staticfiles, media]
  env_file: .env
  port: 8000
```

#### 4. Celery Worker Service:
```yaml
celery_worker:
  build: ./backend
  command: celery -A config.celery worker -l info
  depends_on: backend
  concurrency: 2
```

#### 5. Frontend Service:
```yaml
frontend:
  build: ./frontend
  ports: [80:80]
  depends_on: backend
  env: API_BASE_URL
```

### Docker Features:
- Multi-stage builds (optimize image size)
- Non-root user (security)
- Health checks
- Volume mounting
- Dependency ordering
- Environment file support

---

## 1️⃣5️⃣ MIDDLEWARE PIPELINE

```
Request Flow:
1. Prometheus Before Middleware (metrics start)
2. CORS Middleware (origin check)
3. Common Middleware (URL normalization)
4. Security Middleware (X-Frame-Options, etc)
5. Session Middleware (session loading)
6. CSRF Middleware (CSRF token check)
7. Authentication Middleware (user loading)
8. Messages Middleware (temporary messages)
9. Custom Middleware:
   - CorrelationIDMiddleware (request tracking)
   - GlobalKillSwitchMiddleware (feature flags)
   - LocationContextMiddleware (geolocation)
10. Clickjacking Protection
11. Prometheus After Middleware (metrics end)
```

---

## 1️⃣6️⃣ DEPLOYMENT CONFIGURATION

### Server: Railway.app
```
Domain: quickdash-backend.up.railway.app
Protocol: HTTPS
Load Balancing: Automatic
Auto-scaling: Enabled
```

### Security Settings:
```python
SECURE_SSL_REDIRECT = True          # Force HTTPS
SECURE_HSTS_SECONDS = 31536000      # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
```

### Allowed Hosts:
```python
ALLOWED_HOSTS = [
    ".railway.app",
    "quickdash.up.railway.app",
    "quickdashbackend.up.railway.app",
    ".railway.internal",
]
```

---

## 1️⃣7️⃣ API STRUCTURE & VERSIONING

### Base URL:
```
https://quickdash-backend.up.railway.app/api/v1
```

### REST Framework Configuration:
```python
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "...",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
```

### Endpoints (Examples):
```
GET    /api/v1/users/                    # List users
POST   /api/v1/users/                    # Create user
GET    /api/v1/users/{id}/               # Get user
PUT    /api/v1/users/{id}/               # Update user
DELETE /api/v1/users/{id}/               # Delete user

GET    /api/v1/orders/                   # List orders
POST   /api/v1/orders/                   # Create order
GET    /api/v1/orders/{id}/              # Get order
PATCH  /api/v1/orders/{id}/              # Update order status

WebSocket:
WS     /ws/orders/{id}/                  # Real-time order updates
WS     /ws/riders/{id}/location/         # Rider location updates
```

---

## 1️⃣8️⃣ COMPLETE DATA FLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERACTIONS                        │
├────────────────┬──────────────────┬─────────────────────────┤
│  Customer Web  │  Rider App       │  Admin Panel            │
│  (Frontend)    │  (Port 2000)     │  (Management)           │
└────────────────┴──────────────────┴─────────────────────────┘
                         │
                    ▼ ▼ ▼ (REST + WebSocket)
         ┌──────────────────────────────┐
         │   Django DRF Backend         │
         │   (Port 8000)                │
         ├──────────────────────────────┤
         │ ✓ Authentication (JWT)       │
         │ ✓ Rate Limiting              │
         │ ✓ CORS Handling              │
         │ ✓ Input Validation           │
         │ ✓ Business Logic             │
         └──────────────────────────────┘
        ▼            ▼            ▼ 
    ┌─────────┐  ┌─────────┐  ┌──────────┐
    │PostgreSQL│  │ Redis  │  │Celery    │
    │+ PostGIS │  │ Cache  │  │Worker    │
    │Database  │  │ Layer  │  │Queue     │
    └─────────┘  └─────────┘  └──────────┘
        │            │              │
        ▼            ▼              ▼
    ┌─ Order  ├─ Sessions      ├─ Tasks
    │ Data    │ Notifications  └─ Email
    │ Users   │ Real-time      └─ Reports
    │ Riders  │ Updates        └─ Webhooks
    │ Products│ Cache Store    └─ External APIs
    └─────────┘─────────────────────────────
        │
        ▼ (Async)
    ┌──────────────────────┐
    │ External Services    │
    ├──────────────────────┤
    │ ✓ AWS S3             │
    │ ✓ Razorpay Payments  │
    │ ✓ Sentry Monitoring  │
    │ ✓ Email Services     │
    └──────────────────────┘
```

---

## 1️⃣9️⃣ ENVIRONMENT VARIABLES NEEDED

```bash
# Database
POSTGRES_DB=quickdash_db
POSTGRES_USER=quickdash_user
POSTGRES_PASSWORD=secure_password
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Django
DJANGO_ENV=production
DJANGO_SECRET_KEY=your-secret-key
DEBUG=false

# Security
ALLOWED_HOSTS=quickdash.app,www.quickdash.app
CSRF_TRUSTED_ORIGINS=https://quickdash.app,https://www.quickdash.app
CORS_ALLOWED_ORIGINS=https://quickdash.app,https://www.quickdash.app

# Redis
REDIS_URL=redis://redis:6379/0
CACHES_LOCATION=redis://redis:6379/1

# AWS S3
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_STORAGE_BUCKET_NAME=quickdash-bucket
AWS_S3_REGION_NAME=us-east-1

# Razorpay
RAZORPAY_KEY_ID=your-key
RAZORPAY_KEY_SECRET=your-secret

# Sentry
SENTRY_DSN=https://...

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=your-email
EMAIL_HOST_PASSWORD=your-password

# API
API_BASE_URL=https://quickdash-backend.up.railway.app/api/v1
```

---

## 2️⃣0️⃣ QUICK START COMMANDS

```bash
# 1. Clone & Setup
git clone <repo>
cd QUICKDASH_FRONT_BACK

# 2. Create Environment File
cp .env.example .env
# Edit .env with your values

# 3. Start with Docker Compose
docker-compose up -d

# 4. Run Migrations
docker-compose exec backend python manage.py migrate

# 5. Create Superuser
docker-compose exec backend python manage.py createsuperuser

# 6. Create Test Data
docker-compose exec backend python manage.py shell < scripts/seed_data.py

# 7. Access Services
Frontend:      http://localhost:80
Backend API:   http://localhost:8000/api/v1
Admin:         http://localhost:8000/admin
API Docs:      http://localhost:8000/api/v1/schema/swagger-ui
Rider App:     http://localhost:2000
Redis CLI:     docker-compose exec redis redis-cli
DB Access:     psql -h localhost -U quickdash_user -d quickdash_db
```

---

## 2️⃣1️⃣ TECH STACK SUMMARY TABLE

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Frontend** | HTML5/CSS3/JS | - | Customer portal |
| **Rider App** | HTML5/CSS3/JS | - | Delivery partner app |
| **Backend Framework** | Django | 5.1+ | Web framework |
| **REST API** | DRF | 3.14+ | API endpoints |
| **Authentication** | JWT | 5.3+ | User sessions |
| **WebSocket** | Django Channels | 4.0+ | Real-time updates |
| **Task Queue** | Celery | 5.3+ | Async processing |
| **Task Scheduler** | Celery Beat | 2.5+ | Cron jobs |
| **Database** | PostgreSQL + PostGIS | 15 | Data storage + mapping |
| **Cache/Broker** | Redis | 7.2 | Caching & queuing |
| **WSGI Server** | Gunicorn | 21.2+ | Production server |
| **ASGI Server** | Uvicorn/Daphne | 0.23+ | Async server |
| **Static Files** | WhiteNoise | 6.6+ | CDN alternative |
| **Payments** | Razorpay | 1.4+ | Payment processing |
| **File Storage** | AWS S3 | boto3 | Cloud storage |
| **Monitoring** | Sentry | 1.30+ | Error tracking |
| **Metrics** | Prometheus | 2.3+ | Performance metrics |
| **API Docs** | drf-spectacular | 0.26+ | OpenAPI schema |
| **Geolocation** | Geopy | 2.4+ | Location services |
| **Maps** | Django-Leaflet | 0.29+ | Map rendering |
| **Image Processing** | Pillow | 10.0+ | Image handling |
| **Testing** | Playwright | 1.37+ | E2E testing |
| **Containerization** | Docker/Compose | Latest | DevOps |
| **Deployment** | Railway.app | - | Hosting |

---

## 2️⃣2️⃣ HOW IT ALL WORKS TOGETHER

```
1. USER MAKES REQUEST
   ↓
2. Frontend sends HTTP/WebSocket message
   ↓
3. Django Backend receives request
   ↓
4. JWT Authentication validates user
   ↓
5. CORS Middleware allows the request
   ↓
6. View processes business logic
   ↓
7. Database query via Django ORM
   ↓
8. PostgreSQL returns data (or hits Redis cache)
   ↓
9. Async task? → Send to Celery Queue → Redis stores task
   ↓
10. Celery Worker picks up task
   ↓
11. Sends email/update via external service
   ↓
12. Response sent back as JSON (REST) or WebSocket event
   ↓
13. Frontend updates UI
   ↓
14. Event logged to Sentry (if error)
   ↓
15. Metrics tracked in Prometheus
   ↓
16. USER SEES RESULT
```

---

## 2️⃣3️⃣ PERFORMANCE OPTIMIZATION FEATURES

✅ **Caching** - Redis layer  
✅ **Connection Pooling** - PostgreSQL (conn_max_age=600)  
✅ **Pagination** - DRF pagination  
✅ **Filtering** - Django-filter  
✅ **Compression** - Gzip via WhiteNoise  
✅ **CDN Ready** - AWS S3 integration  
✅ **Monitoring** - Prometheus + Sentry  
✅ **Load Balancing** - Railway auto-scaling  
✅ **Async Tasks** - Celery workers  
✅ **Real-time Updates** - WebSocket channels  

---

**That's your complete tech stack! 🎉**  
Every technology has a specific purpose in this delivery management system.

