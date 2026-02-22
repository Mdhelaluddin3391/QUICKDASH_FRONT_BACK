# API Request/Response Reference

## Complete Rider Delivery Flow

---

## 1. Rider Login
```
POST /riders/login/
Content-Type: application/json

{
  "phone": "9876543210",
  "password": "rider_password"
}

RESPONSE 200:
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user_id": 5,
  "name": "John Rider"
}
```

---

## 2. Check Rider Status (on dashboard load)
```
GET /riders/me/
Authorization: Bearer eyJ0eXAi...

RESPONSE 200:
{
  "id": 5,
  "user": {
    "id": 5,
    "phone": "9876543210",
    "email": "rider@example.com"
  },
  "is_active": true,
  "is_available": true,
  "current_warehouse": {
    "id": 2,
    "code": "WH_MUMBAI_01",
    "name": "Mumbai Central Warehouse",
    "address": "123 Industrial Zone, Mumbai"
  },
  "todays_earnings": "850.00",
  "kyc_verified": true,
  "documents_status": {
    "license": "verified",
    "rc": "verified",
    "pan": "pending"
  }
}
```

---

## 3. Go Online (Toggle switch)
```
POST /riders/availability/
Authorization: Bearer eyJ0eXAi...
Content-Type: application/json

{
  "is_available": true
}

RESPONSE 200:
{
  "is_available": true,
  "status": "You are now online"
}
```

---

## 4. Fetch My Deliveries (Auto-refresh every 10 seconds)
```
GET /delivery/me/
Authorization: Bearer eyJ0eXAi...

RESPONSE 200:
[
  {
    "id": 42,
    "order": {
      "id": 1001,
      "final_amount": "599.50",
      "payment_method": "COD",
      "delivery_address_json": {
        "receiver_name": "Rajesh Kumar",
        "full_address": "Flat 301, Tower A, Prestige Heights, Bandra West, Mumbai 400050",
        "receiver_phone": "9123456789",
        "lat": 19.0596,
        "lng": 72.8295
      },
      "items": [
        {
          "product_name": "Wireless Earbuds",
          "quantity": 1,
          "price": "299.00"
        },
        {
          "product_name": "Phone Case",
          "quantity": 2,
          "price": "149.75"
        }
      ]
    },
    "rider": 5,
    "status": "assigned",           ← ← ← NEW ORDER
    "job_status": "assigned",
    "otp": "782945",
    "created_at": "2026-02-22T14:23:10Z",
    "updated_at": "2026-02-22T14:23:10Z"
  }
]

RESPONSE 200 (No orders):
[]
```

---

## 5. Accept Order (NEW - Called when rider clicks "Accept Order" button)
```
POST /delivery/42/respond/
Authorization: Bearer eyJ0eXAi...
Content-Type: application/json

{
  "action": "accept"
}

RESPONSE 200:
{
  "status": "accepted"
}

ERROR 400 (Order already taken/expired):
{
  "error": "Delivery no longer available",
  "detail": "Another rider already accepted or order was reassigned"
}

ERROR 403 (Unauthorized):
{
  "error": "This delivery is not assigned to you",
  "detail": "Delivery is assigned to rider 10"
}
```

**Frontend Toast on Success:** ✅ "Order Accepted! Go to warehouse to pick up."

---

## 6. Reject Order (NEW - Called when rider clicks "Reject" button)
```
POST /delivery/42/respond/
Authorization: Bearer eyJ0eXAi...
Content-Type: application/json

{
  "action": "reject"
}

RESPONSE 200:
{
  "status": "rejected"
}

ERROR 400 (Invalid action):
{
  "error": "Invalid action",
  "detail": "action must be 'accept' or 'reject'"
}

ERROR 403 (Unauthorized):
{
  "error": "This delivery is not assigned to you"
}
```

**Frontend Toast on Success:** ✅ "Order Rejected. Looking for next delivery..."

**Backend Action:** 
- Sets `delivery.rider = None`
- Changes `delivery.job_status = 'searching'`
- Keeps `delivery.status = 'assigned'`
- Triggers Celery task: `retry_auto_assign_rider(order_id)` to find next rider

---

## 7. Go to Warehouse & Scan QR (User clicks "Pick Up from Warehouse")
```
POST /delivery/verify-handover/
Authorization: Bearer eyJ0eXAi...
Content-Type: application/json

{
  "order_id": 1001
}

RESPONSE 200:
{
  "status": "verified",
  "order_id": 1001,
  "message": "Pickup Successful"
}

RESPONSE 400 (Order not ready):
{
  "error": "Order is confirmed, not ready for handover",
  "detail": "Order must be in 'packed' or 'confirmed' status"
}
```

**Result:**
- Delivery status changes from `assigned` → `picked_up`
- Order status changes to `out_for_delivery`
- OTP gets printed for delivery (see debug logs)
- Frontend shows OTP input box for customer verification

---

## 8. Send Location Update (Every 5 seconds while online)
```
POST /riders/location/
Authorization: Bearer eyJ0eXAi...
Content-Type: application/json

{
  "lat": 19.0596,
  "lng": 72.8295
}

RESPONSE 200:
{
  "status": "location_synced"
}
```

**Purpose:** Tracks rider's real-time location for delivery monitoring

---

## 9. Complete Delivery (Ask customer for OTP)
```
POST /delivery/42/complete/
Authorization: Bearer eyJ0eXAi...
Content-Type: application/json

{
  "otp": "782945"
}

RESPONSE 200:
{
  "status": "delivered"
}

ERROR 400 (Wrong OTP):
{
  "error": "OTP verification failed",
  "detail": "Invalid OTP. Try again. Error: 3 attempts remaining"
}

ERROR 400 (No proof image):
{
  "error": "Proof image required",
  "detail": "Please upload a delivery proof before marking complete"
}
```

**Result:**
- Delivery status changes to `delivered`
- Order marked as completed
- Payment settlement (if COD) initiated
- Rider earnings updated
- Customer receives delivery confirmation SMS/email

---

## 10. Logout
```
POST /riders/logout/
Authorization: Bearer eyJ0eXAi...

RESPONSE 200:
{
  "status": "logged_out"
}

RESULT:
- Token invalidated
- location tracking stopped
- Rider status set to offline
```

---

## Error Response Format (All 4xx/5xx errors use this format)

```json
{
  "error": "Short error title",
  "detail": "Detailed explanation of what went wrong and how to fix it"
}
```

---

## Status Codes Cheat Sheet

| Code | Meaning | Action |
|------|---------|---------|
| 200 | Success | Continue normally |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Check input data, show error to user |
| 401 | Unauthorized | Token expired, redirect to login |
| 403 | Forbidden | Access denied, user doesn't have permission |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Invalid state transition (e.g., accept already accepted order) |
| 500 | Server Error | Unexpected backend failure, check logs |
| 503 | Service Unavailable | Backend service down |

---

## Delivery Status State Machine

```
Order Created
    ↓
    [WAREHOUSE PHASE]
Order packed → Rider Assigned (status: "assigned")
    ↓
    [RIDER PHASE]
Accept/Reject
    ├→ Reject: Go back to searching for another rider
    └→ Accept: Ready to pick up
         ↓
         Scan QR at warehouse (status: "picked_up")
         ↓
         Travel to customer (status: "out_for_delivery")
         ↓
         Get OTP from customer ✓ (status: "delivered")
         ↓
    [COMPLETE]
    Payment settled, Earnings updated
```

---

## Frontend to Backend Flow (Accept Button Click)

```
USER CLICKS "Accept Order"
    ↓
JavaScript: acceptOrder(42)
    ↓
Show loading spinner on button
    ↓
POST /delivery/42/respond/ { "action": "accept" }
    ↓
BACKEND PROCESSES:
├── Verify delivery exists (id=42)
├── Verify rider owns delivery
├── Verify status is "assigned" (not already accepted)
├── Return 200 success OR error
    ↓
Frontend receives response
    ├→ Success: Show "✅ Accepted!" toast
    │           Call checkActiveJobs() to refresh
    └→ Error:   Show "❌ Error: message" toast
                Keep button enabled
    ↓
REPEAT: Job card refreshes every 10 seconds
    ↓
Next UI shown (warehouse pickup button or next delivery)
```

---

## Testing with cURL

Save your token to environment:
```bash
TOKEN="eyJ0eXAi..."
DELIVERY_ID=42

# Accept order
curl -X POST http://localhost:8000/delivery/$DELIVERY_ID/respond/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "accept"}'

# Reject order
curl -X POST http://localhost:8000/delivery/$DELIVERY_ID/respond/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "reject"}'

# Get deliveries
curl -X GET http://localhost:8000/delivery/me/ \
  -H "Authorization: Bearer $TOKEN"
```

---

## WebSocket Events (Real-time updates)

When rider goes online (`is_available=true`), they connect to WebSocket:

**Channel:** `deliveries_{rider_id}`

**Event: New Delivery Assigned**
```json
{
  "type": "delivery_assigned",
  "delivery_id": 42,
  "order_id": 1001,
  "warehouse_id": 2,
  "message": "New delivery assigned to you"
}
```

**Event: Delivery Rejected by Another Rider (if you were next in queue)**
```json
{
  "type": "delivery_rejected",
  "delivery_id": 42,
  "reason": "Previous rider rejected"
}
```

Note: Current implementation might not use WebSockets. Check if your backend has `channels` and `daphne` configured.

---

## Debug Mode - View Full Request/Response

In browser console:
```javascript
// Intercept all API calls
const originalFetch = window.fetch;
window.fetch = function(...args) {
  console.log('REQUEST:', args[0], args[1]);
  return originalFetch.apply(this, args)
    .then(r => {
      console.log('RESPONSE:', r.status, r.statusText);
      return r;
    });
};
```

