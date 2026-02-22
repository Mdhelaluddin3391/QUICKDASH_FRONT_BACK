# Rider Dashboard Update Summary

## Changes Made to `rider-dashboard.js`

### 1. Updated Order Card Rendering for New Assignments

**New UI for `status='assigned'` (newly assigned orders):**
- Shows a prominent "🆕 New Order - Action Required" badge
- Displays two action buttons:
  - **Accept Order** (green button) - Rider confirms they'll take the delivery
  - **Reject** (red button) - Rider declines the order for another rider
- Shows helper text: "After accepting, you'll pick up from the warehouse"

### 2. New Functions Added

#### `acceptOrder(deliveryId)`
```javascript
// Makes POST request to: /delivery/{deliveryId}/respond/
// Payload: { "action": "accept" }
// On success: Shows toast and refreshes job list
```

**Features:**
- Loading spinner during request
- Error handling with user-friendly messages
- Auto-refresh to show next available order or pickup screen
- Button disabled during request

**Toast Messages:**
- ✅ Success: "Order Accepted! Go to warehouse to pick up."
- ❌ Error: Shows backend error message

#### `rejectOrder(deliveryId)`
```javascript
// Makes POST request to: /delivery/{deliveryId}/respond/
// Payload: { "action": "reject" }
// On success: System finds next rider via auto-assignment
```

**Features:**
- Confirmation dialog before rejection
- Loading spinner during request
- Auto-triggers system to reassign to another rider
- Refreshes to show next available order
- Button disabled during request

**Toast Messages:**
- ✅ Success: "Order Rejected. Looking for next delivery..."
- ❌ Error: Shows backend error message

### 3. Status Filter (Unchanged but Validated)

The filter still uses: `['assigned', 'picked_up', 'out_for_delivery']`

This is correct because:
- `assigned` = Newly assigned (rider hasn't accepted yet, OR has just accepted)
- `picked_up` = Rider has picked up from warehouse
- `out_for_delivery` = Rider is on the way to customer

---

## Complete Workflow After Updates

### For New Order:
1. Admin assigns order to rider → Delivery status = "assigned"
2. Rider goes online → `/delivery/me/` returns delivery with status "assigned"
3. Rider sees card with:
   - Order details
   - **Accept/Reject buttons** ← NEW
   - "After accepting, you'll pick up from the warehouse" message
4. Rider clicks **Accept** → Sends `{"action": "accept"}` to backend
5. Backend accepts (may update internal state - check your implementation)
6. Frontend shows success toast and refreshes
7. Next UI depends on your backend logic:
   - If status stays "assigned": Show warehouse pickup button
   - If status changes: Show appropriate next step

### For Rejection:
1. Rider clicks **Reject**
2. Confirmation dialog appears
3. Backend unmarked rider from delivery: `delivery.rider = None`
4. Backend re-triggers auto-assignment: `retry_auto_assign_rider.delay()`
5. System finds next available rider and assigns
6. Original rider sees "Scanning for orders..."

---

## Code Structure

### Key Components:

**renderJobCard(job, container)**
```
├── Extracts order data (address, items, etc.)
├── Determines status ('assigned', 'picked_up', 'out_for_delivery')
├── Builds appropriate UI:
│   ├── For 'assigned': Accept/Reject buttons
│   └── For others: OTP input for delivery completion
└── Renders to DOM
```

**acceptOrder(deliveryId)**
```
├── Get Accept button element
├── Show loading spinner
├── POST /delivery/{deliveryId}/respond/ with {"action": "accept"}
├── Show success/error toast
└── Refresh job list via checkActiveJobs()
```

**rejectOrder(deliveryId)**
```
├── Confirm with user dialog
├── Get Reject button element
├── Show loading spinner
├── POST /delivery/{deliveryId}/respond/ with {"action": "reject"}
├── Show success or error toast
└── Refresh job list via checkActiveJobs()
```

---

## API Endpoints Used

### Accept/Reject Endpoint
```
POST /delivery/{delivery_id}/respond/

Request Body:
{
  "action": "accept"  // or "reject"
}

Response (on success):
{
  "status": "accepted"  // or "rejected"
}

Error (409 Conflict):
{
  "error": "Delivery no longer available",
  "detail": "..."
}
```

---

## Error Handling

The code handles:
- **Network errors**: "Failed to accept order"
- **Backend validation errors**: Shows `error.message` from API
- **Invalid delivery**: "This delivery is not assigned to you"
- **Invalid status**: "Delivery no longer available"
- **Unauthorized (401)**: Auto-logout via ApiService

---

## Styling

Buttons use inline styles for quick styling:
- **Accept button**: Green (`background: #10b981`) with flex: 1
- **Reject button**: Red (`background: #ef4444`) with flex: 1
- **Acceptance box**: Flex row with 10px gap

These can be moved to CSS classes in your stylesheet for consistency.

---

## Testing Checklist

- [ ] Rider logs in and goes online
- [ ] New order appears with status "assigned"
- [ ] Card shows Accept/Reject buttons (not warehouse pickup)
- [ ] Click Accept → Loading spinner shows
- [ ] On success → Toast shows "Order Accepted!"
- [ ] Card refreshes to next state
- [ ] Click Reject → Confirmation dialog appears
- [ ] On reject → Toast shows "Order Rejected"
- [ ] Next rider gets the order (check backend logs)
- [ ] Original rider sees "Scanning for orders..."

---

## Notes on Backend State

**Current backend behavior (RiderAcceptDeliveryAPIView):**

```python
if action == 'accept':
    if delivery.status != 'assigned':
        return Response({"error": "Delivery no longer available"})
    return Response({"status": "accepted"})  # ← Doesn't update DB
```

**Issue**: The accept action doesn't actually update the Delivery model. Consider:
- Adding a new field like `rider_accepted_at` timestamp
- Or changing status to `"accepted"` (new status)
- This would help track acceptance state

**Current rejection behavior (working as expected):**
```python
elif action == 'reject':
    delivery.rider = None
    delivery.job_status = 'searching'
    delivery.status = 'assigned'
    delivery.save()
    retry_auto_assign_rider.delay(delivery.order.id)
    return Response({"status": "rejected"})
```

---

## Future Enhancements

1. **Timeout for acceptance**: If rider doesn't accept within 30s, auto-reassign
2. **Batch orders**: Show multiple orders in a list instead of one-by-one
3. **Acceptance analytics**: Track which riders accept/reject most
4. **Smart routing**: Suggest nearest warehouse based on GPS

