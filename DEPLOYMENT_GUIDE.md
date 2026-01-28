# DEPLOYMENT GUIDE
# ================
# Step-by-step instructions for deploying to Railway, AWS ECS, and Docker

## PART 1: LOCAL DOCKER TESTING
## ==============================

### Step 1: Build and Test Locally

```bash
cd /path/to/Myapp

# Build the Docker image
docker build -f backend/Dockerfile -t quickdash:latest .

# Or use docker-compose to test everything
docker-compose up --build
```

### Step 2: Verify Services

```bash
# Check if backend is running
curl http://localhost:5000/health/

# Check if Celery is working
docker-compose logs celery_worker | grep "ready to accept"

# Check database connection
docker-compose exec backend python manage.py dbshell
```

### Step 3: Test API Endpoints

```bash
# Test health check
curl http://localhost:5000/health/

# Test app config endpoint
curl http://localhost:5000/api/config/

# Test authentication (should be 403 Forbidden without token)
curl http://localhost:5000/api/v1/auth/
```

---

## PART 2: RAILWAY DEPLOYMENT
## =============================

### Step 1: Create Railway Project

```bash
# Install Railway CLI
curl -fsSL https://railway.app/install.sh | sh

# Login to Railway
railway login

# Initialize Railway project
railway init

# Choose "Create a new project"
```

### Step 2: Add Services to Railway

```bash
# Add PostgreSQL
railway add
# Select PostgreSQL

# Add Redis
railway add
# Select Redis

# The backend service is auto-detected from Dockerfile
```

### Step 3: Configure Environment Variables

In Railway Dashboard, go to **Variables** tab and set:

```
DJANGO_ENV=production
DEBUG=false
DJANGO_SECRET_KEY=<generate-new-secret-key>
ALLOWED_HOSTS=your-railway-domain.railway.app,api.your-domain.com
CORS_ALLOWED_ORIGINS=https://your-domain.com,https://app.your-domain.com
PORT=5000
IS_PRIMARY=1
RUN_GUNICORN=1
```

**Note:** DATABASE_URL and REDIS_URL are automatically set by Railway plugins.

### Step 4: Deploy

```bash
# Push to Railway
git push

# Or deploy directly
railway deploy

# Monitor logs
railway logs -f
```

### Step 5: Verify Deployment

```bash
# Get your Railway domain from dashboard
RAILWAY_URL=https://your-project.railway.app

# Test health endpoint
curl $RAILWAY_URL/health/

# Test API
curl $RAILWAY_URL/api/config/
```

### Step 6: Run Celery Worker on Secondary Process

In Railway Dashboard:

1. Go to **Services**
2. Add another deployment with:
   - Command: `celery -A config.celery worker -l info --concurrency=2`
   - Environment: `RUN_GUNICORN=0`

---

## PART 3: AWS ECS DEPLOYMENT
## ============================

### Step 1: Push Image to ECR

```bash
# Create ECR repository
aws ecr create-repository --repository-name quickdash-backend

# Get login token
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -f backend/Dockerfile -t <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/quickdash-backend:latest .
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/quickdash-backend:latest
```

### Step 2: Create ECS Task Definition

```json
{
  "family": "quickdash-web",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "web",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/quickdash-backend:latest",
      "portMappings": [
        {
          "containerPort": 5000,
          "hostPort": 5000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "DJANGO_ENV",
          "value": "production"
        },
        {
          "name": "DEBUG",
          "value": "false"
        },
        {
          "name": "PORT",
          "value": "5000"
        },
        {
          "name": "IS_PRIMARY",
          "value": "1"
        },
        {
          "name": "RUN_GUNICORN",
          "value": "1"
        }
      ],
      "secrets": [
        {
          "name": "DJANGO_SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:quickdash/DJANGO_SECRET_KEY"
        },
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:quickdash/DATABASE_URL"
        },
        {
          "name": "REDIS_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:quickdash/REDIS_URL"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/quickdash-web",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:5000/health/ || exit 1"],
        "interval": 30,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ],
  "executionRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/ecsTaskRole"
}
```

### Step 3: Create ALB Target Group

```bash
aws elbv2 create-target-group \
  --name quickdash-web \
  --protocol HTTP \
  --port 5000 \
  --vpc-id vpc-xxxxx \
  --target-type ip \
  --health-check-path /health/ \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 10 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3
```

### Step 4: Create ECS Service

```bash
aws ecs create-service \
  --cluster quickdash-cluster \
  --service-name quickdash-web \
  --task-definition quickdash-web:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxx,subnet-yyyyy],securityGroups=[sg-xxxxx],assignPublicIp=DISABLED}" \
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=web,containerPort=5000
```

### Step 5: Create Celery Worker Service

Create separate task definition with `RUN_GUNICORN=0` and run as background service (no load balancer).

### Step 6: Monitor Deployment

```bash
# Check service status
aws ecs describe-services --cluster quickdash-cluster --services quickdash-web

# View logs
aws logs tail /ecs/quickdash-web --follow
```

---

## PART 4: KUBERNETES DEPLOYMENT (Optional)
## =========================================

### Step 1: Create ConfigMap for Environment Variables

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: quickdash-config
  namespace: production
data:
  DJANGO_ENV: "production"
  DEBUG: "false"
  ALLOWED_HOSTS: "api.example.com,quickdash.example.com"
  CORS_ALLOWED_ORIGINS: "https://example.com,https://app.example.com"
  PORT: "5000"
  IS_PRIMARY: "1"
  RUN_GUNICORN: "1"
```

### Step 2: Create Secret for Sensitive Data

```bash
kubectl create secret generic quickdash-secrets \
  --from-literal=DJANGO_SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())') \
  --from-literal=DATABASE_URL=postgis://user:pass@postgres.default.svc.cluster.local:5432/quickdash \
  --from-literal=REDIS_URL=redis://redis.default.svc.cluster.local:6379/0 \
  -n production
```

### Step 3: Create Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: quickdash-web
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: quickdash-web
  template:
    metadata:
      labels:
        app: quickdash-web
    spec:
      containers:
      - name: web
        image: <REGISTRY>/quickdash-backend:latest
        ports:
        - containerPort: 5000
        envFrom:
        - configMapRef:
            name: quickdash-config
        - secretRef:
            name: quickdash-secrets
        livenessProbe:
          httpGet:
            path: /health/
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health/
            port: 5000
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "1000m"
            memory: "1Gi"
```

---

## PART 5: POST-DEPLOYMENT CHECKS
## ================================

### Immediate Checks (First 5 minutes)

```bash
# 1. Check service is up
curl https://your-domain.com/health/

# 2. Check logs for startup errors
# Railway: railway logs
# ECS: aws logs tail /ecs/quickdash-web
# K8s: kubectl logs -f deployment/quickdash-web

# 3. Verify database connection
# You should see "Database configured" in logs

# 4. Verify Redis connection
# You should see "Redis configured" in logs
```

### Functional Tests (First 30 minutes)

```bash
# 1. Test authentication endpoint
curl -X POST https://your-domain.com/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"phone": "1234567890", "password": "password"}'

# 2. Test orders endpoint (requires auth)
curl https://your-domain.com/api/v1/orders/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# 3. Test WebSocket connection
wscat -c wss://your-domain.com/ws/delivery/tracking/

# 4. Monitor Celery tasks
# Check logs for task execution
# Look for: "[CELERY] Worker is ready"
```

### Production Verification (Hour 1)

- [x] All health checks passing
- [x] No errors in logs
- [x] Database migrations completed successfully
- [x] Static files served correctly
- [x] WebSocket connections working
- [x] Celery tasks executing
- [x] Payment webhooks receiving (if applicable)
- [x] SMS notifications sending (if applicable)

---

## PART 6: SCALING & MONITORING
## ==============================

### Railway Scaling

In Railway Dashboard:
- Go to **Settings** → **Scale**
- Increase **Compute** (CPU/RAM) as needed
- Increase **Replicas** for horizontal scaling

### AWS ECS Scaling

```bash
# Enable auto-scaling
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/quickdash-cluster/quickdash-web \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10

# Create scaling policy
aws application-autoscaling put-scaling-policy \
  --policy-name cpu-scaling \
  --service-namespace ecs \
  --resource-id service/quickdash-cluster/quickdash-web \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration TargetValue=70.0,PredefinedMetricSpecification={PredefinedMetricType=ECSServiceAverageCPUUtilization}
```

### K8s Scaling

```bash
# Horizontal Pod Autoscaler
kubectl autoscale deployment quickdash-web \
  --min=3 --max=20 \
  --cpu-percent=80 \
  -n production
```

### Monitoring with Prometheus

```bash
# Access metrics
curl https://your-domain.com/metrics

# Common metrics to monitor:
# - http_requests_total (request count)
# - http_request_duration_seconds (response time)
# - django_http_requests_latency_seconds (Django latency)
# - celery_task_total (task count)
# - celery_task_failed_total (failed tasks)
```

---

## TROUBLESHOOTING GUIDE
## ====================

### Issue: Startup fails with "DJANGO_SECRET_KEY is required"

**Solution:**
```bash
# Generate new secret key
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Set in your environment (Railway/ECS dashboard or K8s secret)
DJANGO_SECRET_KEY=<generated-value>
```

### Issue: Database connection timeout

**Solution:**
```bash
# Check DATABASE_URL format
# Correct: postgis://user:pass@host:5432/db

# Check database is running and accessible
psql -h <host> -U <user> -d <db>

# Increase connection timeout in settings
GUNICORN_TIMEOUT=300  # 5 minutes
```

### Issue: Redis connection refused

**Solution:**
```bash
# Check REDIS_URL
# Correct: redis://[:password]@host:6379/0

# Check Redis is running
redis-cli -u $REDIS_URL ping

# In-memory cache will be used as fallback (non-production)
```

### Issue: Migrations not running

**Solution:**
```bash
# Ensure IS_PRIMARY=1 for primary instance
# Check logs for migration errors
# Logs should show: "Migrations completed successfully"

# Manually run migrations if needed:
python manage.py migrate --noinput
```

### Issue: Static files 404

**Solution:**
```bash
# Ensure IS_PRIMARY=1 instance runs collectstatic
# Check logs for: "Static files collected"

# If using WhiteNoise (recommended):
# Served automatically in production

# If using S3 (optional):
# Configure AWS_STORAGE_BUCKET_NAME and related settings
```

---

## ROLLBACK PROCEDURE
## ===================

### Railway Rollback

```bash
# View deployment history
railway environment

# Redeploy previous version
git revert HEAD
git push
railway deploy
```

### ECS Rollback

```bash
# Update service with previous task definition
aws ecs update-service \
  --cluster quickdash-cluster \
  --service quickdash-web \
  --task-definition quickdash-web:1  # Previous version number
```

### K8s Rollback

```bash
# View rollout history
kubectl rollout history deployment/quickdash-web

# Rollback to previous version
kubectl rollout undo deployment/quickdash-web
```

---

**Ready to deploy? You're all set!** 🚀
