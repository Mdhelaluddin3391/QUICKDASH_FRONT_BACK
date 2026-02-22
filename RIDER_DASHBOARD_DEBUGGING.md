# Rider Dashboard Debugging Guide

## Issue: Orders Not Showing on Rider Dashboard

The frontend shows "Scanning for orders..." because `/delivery/me/` returns an empty array. This document provides step-by-step debugging instructions.

---

## Step 1: Verify Rider `is_available` Status

### 1.1 Django Shell Check
```bash
cd backend
python manage.py shell
```

```python
from apps.riders.models import RiderProfile
from django.contrib.auth import get_user_model

User = get_user_model()

# Replace with your test rider's phone/username
rider_user = User.objects.get(phone="9876543210")  # or username="rider_username"
rider = rider_user.rider_profile

print(f"Rider ID: {rider.id}")
print(f"Is Active: {rider.is_active}")
print(f"Is Available: {rider.is_available}")  # ← Should be True
print(f"Current Warehouse: {rider.current_warehouse}")
print(f"Warehouse Code: {rider.current_warehouse.code if rider.current_warehouse else 'None'}")
```

### 1.2 SQL Check
```sql
-- Check rider availability status
SELECT 
    r.id, 
    u.phone, 
    r.is_active, 
    r.is_available,
    r.current_warehouse_id,
    w.code as warehouse_code
FROM riders_riderprofile r
JOIN auth_user u ON r.user_id = u.id
LEFT JOIN warehouse_warehouse w ON r.current_warehouse_id = w.id
WHERE u.phone = '9876543210';
```

**Expected Result:**
- `is_active` = TRUE
- `is_available` = TRUE (logged in as Online)
- `current_warehouse_id` = NOT NULL
- `warehouse_code` = Valid code

---

## Step 2: Verify Order Exists & Warehouse Matching

### 2.1 Check if Order exists with rider's warehouse
```bash
python manage.py shell
```

```python
from apps.orders.models import Order
from apps.riders.models import RiderProfile
from django.contrib.auth import get_user_model

User = get_user_model()
rider_user = User.objects.get(phone="9876543210")
rider = rider_user.rider_profile

# Check for pending orders in the rider's warehouse
pending_orders = Order.objects.filter(
    warehouse=rider.current_warehouse,
    status__in=['packed', 'confirmed', 'ready']  # Check what statuses your system uses
)

print(f"Rider Warehouse: {rider.current_warehouse}")
print(f"Pending Orders in this warehouse: {pending_orders.count()}")
for order in pending_orders:
    print(f"  - Order #{order.id}, Status: {order.status}")
```

### 2.2 SQL Check
```sql
-- Find orders in the rider's warehouse that are ready for delivery
SELECT 
    o.id,
    o.status,
    o.warehouse_id,
    w.code,
    o.created_at
FROM orders_order o
JOIN warehouse_warehouse w ON o.warehouse_id = w.id
WHERE o.warehouse_id = (
    SELECT current_warehouse_id 
    FROM riders_riderprofile 
    WHERE id = 1  -- Replace with your rider ID
)
AND o.status IN ('packed', 'confirmed', 'ready')
LIMIT 10;
```

---

## Step 3: Verify Delivery Assignment & Status

### 3.1 Check Delivery Records
```bash
python manage.py shell
```

```python
from apps.delivery.models import Delivery
from apps.riders.models import RiderProfile
from django.contrib.auth import get_user_model

User = get_user_model()
rider_user = User.objects.get(phone="9876543210")
rider = rider_user.rider_profile

# Get ALL deliveries assigned to this rider
all_deliveries = Delivery.objects.filter(rider=rider).order_by('-created_at')

print(f"Total Deliveries for Rider {rider.id}: {all_deliveries.count()}")
print("\n--- Deliveries Status Breakdown ---")
for delivery in all_deliveries[:10]:  # Show last 10
    print(f"Delivery #{delivery.id}:")
    print(f"  - Status: {delivery.status}")
    print(f"  - Job Status: {delivery.job_status}")
    print(f"  - Order #{delivery.order.id}")
    print(f"  - Created: {delivery.created_at}")
    print()

# Check ACTIVE deliveries (that should appear on dashboard)
active = Delivery.objects.filter(
    rider=rider,
    status__in=['assigned', 'picked_up', 'out_for_delivery']
)
print(f"\n✓ ACTIVE Deliveries: {active.count()}")
for d in active:
    print(f"  - Delivery #{d.id}, Order #{d.order.id}, Status: {d.status}")
```

### 3.2 SQL Check
```sql
-- Get all deliveries for a specific rider
SELECT 
    d.id,
    d.order_id,
    d.status,
    d.job_status,
    d.rider_id,
    d.created_at
FROM delivery_delivery d
WHERE d.rider_id = 1  -- Replace with your rider ID
ORDER BY d.created_at DESC
LIMIT 20;

-- Count deliveries by status
SELECT 
    d.status,
    COUNT(*) as count
FROM delivery_delivery d
WHERE d.rider_id = 1
GROUP BY d.status;
```

---

## Step 4: Test the API Endpoint Directly

### 4.1 Using cURL
```bash
# Get rider's auth token first
curl -X POST http://localhost:8000/riders/login/ \
  -H "Content-Type: application/json" \
  -d '{"phone": "9876543210", "password": "rider_password"}'

# Response will include: {"token": "your_token_here"}

# Now test /delivery/me/
TOKEN="your_token_here"
curl -X GET http://localhost:8000/delivery/me/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# Expected: Array of delivery objects with status 'assigned', 'picked_up', or 'out_for_delivery'
```

### 4.2 Using Python Requests
```python
import requests
import json

BASE_URL = "http://localhost:8000"

# 1. Login
login_resp = requests.post(f"{BASE_URL}/riders/login/", json={
    "phone": "9876543210",
    "password": "your_password"
})

token = login_resp.json()["token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. Check rider status
profile_resp = requests.get(f"{BASE_URL}/riders/me/", headers=headers)
profile = profile_resp.json()
print(f"Rider is_available: {profile['is_available']}")
print(f"Rider warehouse: {profile['current_warehouse']}")

# 3. Get deliveries
delivery_resp = requests.get(f"{BASE_URL}/delivery/me/", headers=headers)
deliveries = delivery_resp.json()

print(f"\nDeliveries count: {len(deliveries)}")
for d in deliveries:
    print(f"  - Delivery #{d['id']}, Status: {d['status']}")
```

---

## Step 5: Simulate Order Assignment

If no orders exist, manually create and assign one:

```bash
python manage.py shell
```

```python
from apps.orders.models import Order
from apps.delivery.models import Delivery
from apps.delivery.services import DeliveryService
from apps.riders.models import RiderProfile
from django.contrib.auth import get_user_model

User = get_user_model()

# Get rider
rider_user = User.objects.get(phone="9876543210")
rider = rider_user.rider_profile

# Make sure rider is online and has a warehouse
rider.is_available = True
rider.is_active = True
rider.save()

print(f"✓ Rider {rider.id} set to available")
print(f"✓ Rider warehouse: {rider.current_warehouse}")

# Find or create an order in the rider's warehouse
order = Order.objects.filter(
    warehouse=rider.current_warehouse,
    status__in=['packed', 'confirmed', 'ready']
).first()

if not order:
    print("No orders found in rider's warehouse!")
    print("You need to create an order first via the admin or API")
else:
    print(f"\n✓ Found Order #{order.id} in warehouse {rider.current_warehouse.code}")
    
    # Assign delivery using the backend service
    delivery = DeliveryService.assign_rider(order, rider, actor=None)
    print(f"✓ Delivery #{delivery.id} assigned to Rider {rider.id}")
    print(f"  - OTP: {delivery.otp}")
    print(f"  - Status: {delivery.status}")
    
    # Verify it shows up in deliveries
    deliveries = Delivery.objects.filter(rider=rider, status='assigned')
    print(f"\n✓ Rider now has {deliveries.count()} assigned delivery(ies)")
```

---

## Step 6: Common Issues Checklist

| Issue | Debug Command | Expected Value |
|-------|---------------|-----------------|
| Rider not online | `rider.is_available` | `True` |
| Rider has no warehouse | `rider.current_warehouse` | NOT `None` |
| Order in wrong warehouse | `order.warehouse` | `== rider.current_warehouse` |
| Delivery status wrong | `delivery.status` | IN ('assigned', 'picked_up', 'out_for_delivery') |
| API returns 403 | Check `request.user.rider_profile` exists | User has rider_profile relation |
| API returns empty array | Check Delivery records exist | `Delivery.objects.filter(rider=rider).count() > 0` |

---

## Step 7: Frontend Debug (Chrome DevTools)

1. **Open DevTools**: F12 or Cmd+Option+I
2. **Check Network Tab**:
   - Request: `GET /delivery/me/`
   - Status: Should be `200`
   - Response: Should be an array `[{...}, {...}]`, not `[]`

3. **Browser Console**:
```javascript
// Test API directly from console
await ApiService.get('/delivery/me/')
  .then(deliveries => console.log("Deliveries:", deliveries))
  .catch(e => console.error("Error:", e));

// Check if rider is online
document.getElementById('online-toggle').checked
```

---

## Step 8: View Backend Logs

```bash
# Check Django logs (if configured)
tail -f backend/logs/django.log

# Run with debug output
cd backend
python manage.py runserver --verbosity 3

# Watch assignment service (if using Celery)
celery -A config worker -l debug
```

---

## Expected Flow After Fixes

1. ✅ Rider logs in → `is_available = True`
2. ✅ Order created in warehouse → warehouse matches rider's warehouse
3. ✅ Admin assigns order → Delivery created with `status='assigned'`
4. ✅ Rider dashboard calls `/delivery/me/` → Returns delivery array
5. ✅ Frontend shows job card with "Accept" & "Reject" buttons
6. ✅ Rider clicks "Accept" → POST to `/delivery/{id}/respond/` with `{"action": "accept"}`
7. ✅ Order refreshes and shows warehouse pickup button
8. ✅ Rider picks up → Shows OTP entry for final delivery

---

## Quick Network Test

Use Postman or Insomnia to test:

**Request:**
```
POST /delivery/1/respond/
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "action": "accept"
}
```

**Expected Response:**
```json
{
  "status": "accepted"
}
```

---

## Still Having Issues?

1. Check Django error logs: `python manage.py runserver` output
2. Add print statements in `views.py`:
   ```python
   def get(self, request):
       print(f"[DEBUG] User: {request.user}")
       print(f"[DEBUG] Has rider_profile: {hasattr(request.user, 'rider_profile')}")
       print(f"[DEBUG] Auth header: {request.headers.get('Authorization')}")
       # ... rest of code
   ```
3. Use `django-debug-toolbar` to inspect queries
4. Check if your database is loading initial warehouse data properly

---

## Database Fixtures (Optional)

If you need test data:

```bash
cd backend
python manage.py loaddata --seed=1  # If you have fixtures
```

Or manually create in Django admin:
1. Go to `/admin/`
2. Create Warehouse (e.g., "Mumbai Central")
3. Create RiderProfile with that warehouse
4. Create Order with that warehouse
5. Use admin interface to assign delivery

