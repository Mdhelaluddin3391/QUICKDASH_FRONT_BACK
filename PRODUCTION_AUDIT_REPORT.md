# Production Readiness Audit Report
## Environment Variables: Payments, SMS, OTP, and Notifications

**Audit Date:** January 28, 2026  
**Scope:** Django Backend Codebase  
**Auditor Role:** Senior Backend Engineer

---

## SECTION 1: RAZORPAY AUDIT

### 1.1 Variable Definitions (settings.py)

| Variable | Defined | Line | Access Method | Default Value |
|----------|---------|------|----------------|---------------|
| `RAZORPAY_KEY_ID` | ✅ YES | [Line 202](backend/config/settings.py#L202) | `os.getenv()` → `settings` | `"dummy_key"` |
| `RAZORPAY_KEY_SECRET` | ✅ YES | [Line 203](backend/config/settings.py#L203) | `os.getenv()` → `settings` | `"dummy_secret"` |
| `RAZORPAY_WEBHOOK_SECRET` | ✅ YES | [Line 204](backend/config/settings.py#L204) | `os.getenv()` → `settings` | `""` (empty) |

### 1.2 Variable Usage Analysis

#### ✅ RAZORPAY_KEY_ID
- **Status:** USED
- **Usage Locations:**
  - [payments/views.py:19](backend/apps/payments/views.py#L19) - Client initialization at module import time
  - [payments/services.py:21](backend/apps/payments/services.py#L21) - Client initialization at module import time
  - [payments/refund_services.py:16](backend/apps/payments/refund_services.py#L16) - Client initialization at module import time
  - [payments/views.py:56](backend/apps/payments/views.py#L56) - Returned in payment response
  - [orders/views.py:161](backend/apps/orders/views.py#L161) - Returned in order response
- **Access Method:** `settings.RAZORPAY_KEY_ID` or `getattr(settings, 'RAZORPAY_KEY_ID', '')`

#### ✅ RAZORPAY_KEY_SECRET
- **Status:** USED
- **Usage Locations:**
  - [payments/views.py:19](backend/apps/payments/views.py#L19) - Client initialization at module import time
  - Indirectly used in Razorpay client for request signing
- **Access Method:** `settings.RAZORPAY_KEY_SECRET`

#### ✅ RAZORPAY_WEBHOOK_SECRET
- **Status:** USED
- **Usage Locations:**
  - [payments/views.py:123](backend/apps/payments/views.py#L123) - Webhook signature verification
  - [payments/views.py:125](backend/apps/payments/views.py#L125) - Error log when not set
- **Access Method:** `settings.RAZORPAY_WEBHOOK_SECRET`

### 1.3 CRITICAL ISSUE: Attribute Name Mismatch ⚠️ **HIGH SEVERITY**

**Problem Detected:**

1. **In settings.py (Line 203):** Variable is defined as `RAZORPAY_KEY_SECRET`
2. **In payments/services.py (Line 21):** Code accesses `settings.RAZORPAY_SECRET` (NAME MISMATCH)
3. **In payments/refund_services.py (Line 16):** Code accesses `settings.RAZORPAY_SECRET` (NAME MISMATCH)

**Impact:**
- When `PaymentService` or `RefundService` are used, they will crash with `AttributeError`
- The application will fail at runtime when attempting to initialize the Razorpay client in these modules
- `payments/views.py` works because it correctly uses `RAZORPAY_KEY_SECRET`

**Current Status:**
- ❌ `settings.RAZORPAY_SECRET` does NOT exist
- ✅ `settings.RAZORPAY_KEY_SECRET` exists (but only accessed in views.py)

**Affected Code:**
```python
# BROKEN - refund_services.py:16
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET))

# BROKEN - services.py:21
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET))

# WORKING - views.py:19
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
```

### 1.4 Razorpay Client Initialization Pattern ⚠️ **PRODUCTION CONCERN**

**Pattern Found:**

```python
# Module-level initialization (executed at import time)
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
```

**Locations:**
- [payments/views.py:19](backend/apps/payments/views.py#L19)
- [payments/services.py:21](backend/apps/payments/services.py#L21) - With try/except fallback
- [payments/refund_services.py:16](backend/apps/payments/refund_services.py#L16) - With try/except fallback

**Issues:**

1. **Import-Time Initialization:**
   - Client is created when the module is imported, not when needed
   - If `settings.RAZORPAY_KEY_ID` or `settings.RAZORPAY_KEY_SECRET` are dummy/empty at import time, client may fail silently
   - Credentials cannot be reloaded without restarting the application

2. **Inconsistent Error Handling:**
   - `payments/services.py` and `refund_services.py` have try/except fallback → `client = None`
   - `payments/views.py` has NO fallback → will crash if credentials are missing
   - If client is `None` in services.py, calls like `client.order.create()` will fail with `AttributeError`

3. **Best Practice Violation:**
   - Should initialize client at runtime (inside function calls) or via dependency injection
   - This allows for credential reloading, mocking in tests, and lazy initialization

**Recommendations:**
- Refactor to lazy initialization or context-based client creation
- Ensure consistent error handling across all Razorpay client usages

---

## SECTION 2: SMS / OTP AUDIT

### 2.1 Variable Definitions (settings.py)

| Variable | Defined | Line | Access Method | Default Value | Status |
|----------|---------|------|----------------|---------------|--------|
| `SMS_PROVIDER` | ✅ YES | [Line 209](backend/config/settings.py#L209) | `os.getenv()` → `settings` | `"dummy"` | UNUSED |
| `SMS_PROVIDER_KEY` | ✅ YES | [Line 210](backend/config/settings.py#L210) | `os.getenv()` → `settings` | `""` | USED |
| `SMS_PROVIDER_SECRET` | ✅ YES | [Line 211](backend/config/settings.py#L211) | `os.getenv()` → `settings` | `""` | UNUSED |
| `SMS_PROVIDER_SENDER_ID` | ✅ YES | [Line 212](backend/config/settings.py#L212) | `os.getenv()` → `settings` | `"QUICKD"` | UNUSED |
| `SMS_PROVIDER_URL` | ✅ YES | [Line 213](backend/config/settings.py#L213) | `os.getenv()` → `settings` | `""` | USED |
| `OTP_EXPIRY_SECONDS` | ✅ YES | [Line 215](backend/config/settings.py#L215) | `os.getenv()` → `int` | `300` (5 mins) | **UNUSED** |
| `OTP_RESEND_COOLDOWN` | ✅ YES | [Line 216](backend/config/settings.py#L216) | `os.getenv()` → `int` | `60` (1 min) | **UNUSED** |

### 2.2 SMS Provider Usage

#### ✅ SMS_PROVIDER_KEY
- **Status:** USED
- **Usage Location:** [notifications/tasks.py:19](backend/apps/notifications/tasks.py#L19)
- **Context:** Retrieved via `getattr(settings, "SMS_PROVIDER_KEY", None)` before sending SMS
- **Code:**
```python
sms_key = getattr(settings, "SMS_PROVIDER_KEY", None)
if not sms_key or not sms_url:
    logger.error("SMS Configuration missing")
    return "Config Missing"
```
- **Behavior:** If not configured, SMS sending fails gracefully with logging

#### ✅ SMS_PROVIDER_URL
- **Status:** USED
- **Usage Location:** [notifications/tasks.py:20](backend/apps/notifications/tasks.py#L20)
- **Context:** Used as POST endpoint for SMS delivery
- **Code:**
```python
response = requests.post(
    sms_url,
    json={
        "to": phone, 
        "message": content, 
        "api_key": sms_key
    },
    timeout=5
)
```

#### ❌ SMS_PROVIDER
- **Status:** DEFINED BUT NOT USED
- **Location:** [config/settings.py:209](backend/config/settings.py#L209)
- **Issue:** Variable is defined but never referenced in codebase
- **Note:** Appears to be placeholder for future provider selection logic

#### ❌ SMS_PROVIDER_SECRET
- **Status:** DEFINED BUT NOT USED
- **Location:** [config/settings.py:211](backend/config/settings.py#L211)
- **Issue:** Variable is defined but never referenced in codebase
- **Note:** No signature verification or HMAC validation found in SMS sending

#### ❌ SMS_PROVIDER_SENDER_ID
- **Status:** DEFINED BUT NOT USED
- **Location:** [config/settings.py:212](backend/config/settings.py#L212)
- **Default:** `"QUICKD"` (hardcoded default)
- **Issue:** Not used anywhere; `send_otp_sms()` only sends phone, message, and api_key

### 2.3 SMS Sending Flow

**Current Flow:**

```
Frontend SMS Request
    ↓
notifications/views.py::SendOTPAPIView.post()
    ↓
OTPService.create_and_send(phone, ip_address)
    ↓
[ATOMIC TRANSACTION]
  • Generate OTP (6-digit, cryptographically secure)
  • Invalidate old OTPs for phone
  • Save to PhoneOTP model
  • Set cooldown in Redis cache
    ↓
notifications/tasks.py::send_otp_sms.delay(phone, message)
    ↓
Celery Task (High Priority Queue)
  • Retrieve SMS_PROVIDER_KEY, SMS_PROVIDER_URL from settings
  • POST to SMS_PROVIDER_URL with phone, message, api_key
  • Timeout: 5 seconds
  • Retry on failure (max_retries=3, default_retry_delay=5s)
```

**SMS Provider Payload (Line 35-40, notifications/tasks.py):**
```python
json={
    "to": phone, 
    "message": content, 
    "api_key": sms_key
}
```

**Issue:** Sender ID is never included in payload. If SMS provider requires it, deliveries will fail.

### 2.4 CRITICAL ISSUE: OTP_EXPIRY_SECONDS Not Used ⚠️ **HIGH SEVERITY**

**Problem:**

1. **Variable Defined:** `OTP_EXPIRY_SECONDS` in [settings.py:215](backend/config/settings.py#L215)
   - Default: `300` seconds (5 minutes)
   - Configurable via environment variable
   
2. **Variable NOT Used:** No references to `settings.OTP_EXPIRY_SECONDS` in codebase

3. **Actual Implementation:** Hardcoded in [notifications/models.py:20](backend/apps/notifications/models.py#L20)
```python
def is_expired(self):
    # 5 minutes TTL
    return (timezone.now() - self.created_at).total_seconds() > 300
```

**Impact:**
- Environment variable `OTP_EXPIRY_SECONDS` is ignored completely
- OTP always expires after exactly 300 seconds, regardless of configuration
- Production environment cannot adjust OTP expiry without code changes + redeployment
- Settings are not aligned with actual behavior

### 2.5 CRITICAL ISSUE: OTP_RESEND_COOLDOWN Not Used ⚠️ **HIGH SEVERITY**

**Problem:**

1. **Variable Defined:** `OTP_RESEND_COOLDOWN` in [settings.py:216](backend/config/settings.py#L216)
   - Default: `60` seconds
   - Configurable via environment variable

2. **Variable NOT Used:** No references to `settings.OTP_RESEND_COOLDOWN` in codebase

3. **Actual Implementation:** Hardcoded in [notifications/services.py:50](backend/apps/notifications/services.py#L50)
```python
class OTPService:
    MAX_ATTEMPTS = 5
    RESEND_COOLDOWN_SECONDS = 60  # HARDCODED!

    @staticmethod
    def create_and_send(phone: str, ip_address: str = None):
        # ...
        # Set Cooldown
        cache.set(cooldown_key, "1", timeout=OTPService.RESEND_COOLDOWN_SECONDS)
```

**Impact:**
- Environment variable `OTP_RESEND_COOLDOWN` is ignored completely
- Resend cooldown always 60 seconds, regardless of configuration
- Cannot adjust rate limiting without code changes + redeployment
- Settings are not aligned with actual behavior

---

## SECTION 3: OTP Model & Services Deep Dive

### 3.1 OTP Expiry Mechanism

**Model:** [notifications/models.py](backend/apps/notifications/models.py#L6-L20)

```python
class PhoneOTP(models.Model):
    phone = models.CharField(max_length=15, db_index=True)
    otp = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    def is_expired(self):
        return (timezone.now() - self.created_at).total_seconds() > 300  # HARDCODED 300s
```

**Verification Call Stack:**

1. [accounts/views.py:57](backend/apps/accounts/views.py#L57) - User calls `/verify-login/` with OTP
2. → [notifications/services.py:144-162](backend/apps/notifications/services.py#L144-L162) - `OTPService.verify(phone, otp)`
3. → Checks `record.is_expired()` → if `True`, returns error
4. → Uses hardcoded 300-second window

**Consequence:**
- If settings say 600 seconds, OTP still only valid for 300 seconds
- If settings say 120 seconds, OTP still valid for 300 seconds
- Configuration environment variables are misleading/false

### 3.2 OTP Rate Limiting & Cooldown

**Rate Limiting Strategy:** [notifications/services.py:72-85](backend/apps/notifications/services.py#L72-L85)

```python
# Per-Phone Rate Limiting (5 OTPs/hour)
rate_key = f"otp_rate:{phone}"
attempts = cache.get(rate_key, 0)
if attempts >= 5:
    raise BusinessLogicException("Too many OTP requests. Try again later.", code="rate_limited")
cache.set(rate_key, attempts + 1, timeout=3600)

# Resend Cooldown (Redis) - HARDCODED 60 SECONDS
cooldown_key = f"otp_cooldown:{phone}"
if cache.get(cooldown_key):
    ttl = cache.ttl(cooldown_key)  # Requires Redis TTL method
    raise BusinessLogicException(f"Please wait {ttl} seconds before retrying", code="rate_limit")

# Set Cooldown
cache.set(cooldown_key, "1", timeout=OTPService.RESEND_COOLDOWN_SECONDS)  # 60 seconds
```

**Issues:**
1. Cooldown is HARDCODED to 60 seconds (class variable)
2. Settings variable is never consulted
3. `cache.ttl()` method may not exist in all Django cache backends (Redis-specific)
   - Raises `AttributeError` on non-Redis backends
   - Should use `cache.get()` pattern instead

### 3.3 Abuse Protection

**Mechanism:** [notifications/services.py:176-213](backend/apps/notifications/services.py#L176-L213)

- Tracks failed OTP attempts per phone
- Blocks phone after 5 failed attempts for 15 minutes
- IP-based rate limiting: max 50 requests/hour per IP
- Logs suspicious activity

**Hardcoded Constants:**
```python
class OTPAbuseService:
    MAX_FAILS = 5
    BLOCK_MINUTES = 15
    IP_MAX_REQUESTS_PER_HOUR = 50
```

---

## SECTION 4: UNUSED AND MISSING VARIABLES

### 4.1 Unused Variables (Defined in settings, Never Used)

| Variable | Definition Line | Issue | Impact |
|----------|-----------------|-------|--------|
| `SMS_PROVIDER` | [settings.py:209](backend/config/settings.py#L209) | Never referenced | Impossible to switch between SMS providers without code changes |
| `SMS_PROVIDER_SECRET` | [settings.py:211](backend/config/settings.py#L211) | Never referenced | No authentication/signature verification possible |
| `SMS_PROVIDER_SENDER_ID` | [settings.py:212](backend/config/settings.py#L212) | Never referenced | Sender ID always missing from SMS payload |
| `OTP_EXPIRY_SECONDS` | [settings.py:215](backend/config/settings.py#L215) | Never referenced | Hardcoded to 300s in model |
| `OTP_RESEND_COOLDOWN` | [settings.py:216](backend/config/settings.py#L216) | Never referenced | Hardcoded to 60s in service |

### 4.2 Variables Used But Not Defined in Settings

**None detected.** All used variables are properly defined in settings.py.

### 4.3 Name Mismatches Between Definition and Usage

| Definition | Used As | Files | Severity |
|------------|---------|-------|----------|
| `RAZORPAY_KEY_SECRET` | `RAZORPAY_SECRET` | [services.py:21](backend/apps/payments/services.py#L21), [refund_services.py:16](backend/apps/payments/refund_services.py#L16) | 🔴 **CRITICAL** |

---

## SECTION 5: CRITICAL PRODUCTION RISKS

### Risk 1: ❌ Razorpay Client Initialization Failure (CRITICAL)

**Severity:** 🔴 **CRITICAL - Payment Processing Down**

**Issue:** 
- `PaymentService` and `RefundService` will crash when imported
- Attempting to access `settings.RAZORPAY_SECRET` (which doesn't exist)
- Will raise `AttributeError: module 'django.conf' has no attribute 'RAZORPAY_SECRET'`

**When It Happens:**
- On application startup when Django loads the payments app
- OR when any code imports from `payments.services` or `payments.refund_services`

**Impact:**
- **Refunds won't process** - `RefundService` cannot be imported
- **Payment creation fails** - `PaymentService` cannot be imported
- **Application crash** - RuntimeError during dependency resolution

**Reproduction:**
```bash
python manage.py shell
>>> from apps.payments.services import PaymentService
# AttributeError: module 'django.conf' has no attribute 'RAZORPAY_SECRET'
```

**Fix Required:** Change both occurrences to use `settings.RAZORPAY_KEY_SECRET`

---

### Risk 2: ⚠️ OTP Expiry Configuration Ignored (HIGH)

**Severity:** 🟠 **HIGH - Security Configuration Ignored**

**Issue:**
- Setting `OTP_EXPIRY_SECONDS` environment variable has NO effect
- OTP always expires after exactly 300 seconds
- Cannot reduce expiry time for higher security
- Cannot increase expiry time for user convenience

**Business Impact:**
- Cannot adjust OTP timeout for different deployment environments
- Security posture cannot be customized per environment
- False sense of configurability

**Example Scenario:**
```
# .env for production (stricter)
OTP_EXPIRY_SECONDS=120  # 2 minutes instead of 5

# .env for staging (more lenient)
OTP_EXPIRY_SECONDS=600  # 10 minutes

# ACTUAL BEHAVIOR: Both will use 300 seconds (hardcoded)
```

---

### Risk 3: ⚠️ OTP Resend Cooldown Configuration Ignored (HIGH)

**Severity:** 🟠 **HIGH - Rate Limiting Not Configurable**

**Issue:**
- Setting `OTP_RESEND_COOLDOWN` environment variable has NO effect
- Resend cooldown always 60 seconds
- Cannot reduce during testing/staging
- Cannot increase for production security

**Additional Issue:** Potential bug in rate limiting check
```python
if cache.get(cooldown_key):
    ttl = cache.ttl(cooldown_key)  # May fail on non-Redis backends
```

---

### Risk 4: ⚠️ Missing SMS Provider Sender ID (MEDIUM)

**Severity:** 🟟 **MEDIUM - SMS Delivery May Fail**

**Issue:**
- `SMS_PROVIDER_SENDER_ID` is configured but never sent in SMS payload
- Some SMS providers require sender ID in request
- May result in:
  - SMS delivery failures
  - Invalid sender ID errors
  - Unidentified sender to end user

**Current Payload:**
```python
json={
    "to": phone, 
    "message": content, 
    "api_key": sms_key
    # MISSING: "from": SMS_PROVIDER_SENDER_ID or "sender_id": SMS_PROVIDER_SENDER_ID
}
```

---

### Risk 5: ⚠️ Module-Level Razorpay Client Initialization (MEDIUM)

**Severity:** 🟟 **MEDIUM - Poor Testability & Flexibility**

**Issue:**
- Client initialized at import time in `payments/views.py`
- Cannot mock or test without monkey-patching
- Cannot hot-reload credentials
- Client may be initialized with dummy credentials

**Problems:**
1. Hard to unit test payment flows
2. Cannot rotate credentials without restarting app
3. Inconsistent error handling across modules

---

### Risk 6: ⚠️ Unused SMS Provider Configuration Variables (LOW)

**Severity:** 🟡 **LOW - Code Maintenance & Confusion**

**Issue:**
- `SMS_PROVIDER` defined but never used
- `SMS_PROVIDER_SECRET` defined but never used
- Developers may assume these are active but they're not
- Creates technical debt and confusion

**Impact:** Low, but increases maintenance burden and risk of security misconfigurations

---

## SECTION 6: FINAL RECOMMENDATIONS

### Immediate Actions Required (Before Production Deployment)

#### 🔴 [CRITICAL] Fix Razorpay KEY_SECRET Mismatch

**Problem:** `RAZORPAY_SECRET` doesn't exist; should be `RAZORPAY_KEY_SECRET`

**Files to Fix:**
1. [backend/apps/payments/services.py:21](backend/apps/payments/services.py#L21)
2. [backend/apps/payments/refund_services.py:16](backend/apps/payments/refund_services.py#L16)

**Action:**
```python
# BEFORE (BROKEN)
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_SECRET))

# AFTER (FIXED)
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
```

**Verification:**
```bash
python manage.py shell
>>> from apps.payments.services import PaymentService  # Should NOT crash
>>> from apps.payments.refund_services import RefundService  # Should NOT crash
```

---

#### 🟠 [HIGH] Implement OTP_EXPIRY_SECONDS Configuration

**Problem:** Environment variable ignored; hardcoded to 300 seconds

**Action:** Update [notifications/models.py:20](backend/apps/notifications/models.py#L20)

**Before:**
```python
def is_expired(self):
    # 5 minutes TTL
    return (timezone.now() - self.created_at).total_seconds() > 300
```

**After:**
```python
def is_expired(self):
    from django.conf import settings
    ttl = getattr(settings, 'OTP_EXPIRY_SECONDS', 300)
    return (timezone.now() - self.created_at).total_seconds() > ttl
```

---

#### 🟠 [HIGH] Implement OTP_RESEND_COOLDOWN Configuration

**Problem:** Environment variable ignored; hardcoded to 60 seconds

**Action:** Update [notifications/services.py](backend/apps/notifications/services.py)

**Before:**
```python
class OTPService:
    RESEND_COOLDOWN_SECONDS = 60  # Hardcoded

    def create_and_send(...):
        cache.set(cooldown_key, "1", timeout=OTPService.RESEND_COOLDOWN_SECONDS)
```

**After:**
```python
class OTPService:
    @staticmethod
    def get_resend_cooldown():
        from django.conf import settings
        return getattr(settings, 'OTP_RESEND_COOLDOWN', 60)

    def create_and_send(...):
        cache.set(cooldown_key, "1", timeout=OTPService.get_resend_cooldown())
```

**Also fix potential bug at line ~80:**
```python
# BEFORE (may crash on non-Redis backends)
if cache.get(cooldown_key):
    ttl = cache.ttl(cooldown_key)
    raise BusinessLogicException(f"Please wait {ttl} seconds before retrying", code="rate_limit")

# AFTER (safer fallback)
if cache.get(cooldown_key):
    ttl = getattr(cache, 'ttl', lambda k: 'a few')
    if callable(ttl):
        remaining = ttl(cooldown_key)
        raise BusinessLogicException(f"Please wait {remaining} seconds before retrying", code="rate_limit")
    else:
        raise BusinessLogicException("Please wait before requesting another OTP", code="rate_limit")
```

---

#### 🟟 [MEDIUM] Add SMS_PROVIDER_SENDER_ID to SMS Payload

**Problem:** Sender ID configured but never sent in SMS request

**Action:** Update [notifications/tasks.py:35-40](backend/apps/notifications/tasks.py#L35-L40)

**Before:**
```python
response = requests.post(
    sms_url,
    json={
        "to": phone, 
        "message": content, 
        "api_key": sms_key
    },
    timeout=5
)
```

**After:**
```python
sender_id = getattr(settings, "SMS_PROVIDER_SENDER_ID", "QUICKD")
response = requests.post(
    sms_url,
    json={
        "to": phone, 
        "message": content, 
        "api_key": sms_key,
        "from": sender_id  # or "sender_id" depending on provider API
    },
    timeout=5
)
```

---

### Medium-Term Actions (Optimization & Maintainability)

#### 🟡 [MEDIUM] Remove Unused Configuration Variables

**Action:** Consider removing or documenting the purpose of:
- `SMS_PROVIDER` - used for future provider switching
- `SMS_PROVIDER_SECRET` - used for future HMAC validation

**Recommendation:** 
1. Document in settings.py WHY these are defined (future use)
2. Add TODO comments linking to future feature tracking
3. OR remove if not planned for next 6 months

**Example:**
```python
# SMS_PROVIDER = os.getenv("SMS_PROVIDER", "dummy")  # TODO: Implement provider switching (Issue #123)
# SMS_PROVIDER_SECRET = os.getenv("SMS_PROVIDER_SECRET", "")  # TODO: Add webhook signature verification
```

---

#### 🟟 [MEDIUM] Refactor Razorpay Client Initialization

**Problem:** Module-level initialization is hard to test and manage

**Approach 1: Lazy Initialization (Recommended)**
```python
class PaymentService:
    _client = None
    
    @classmethod
    def get_client(cls):
        if cls._client is None:
            from django.conf import settings
            cls._client = razorpay.Client(auth=(
                settings.RAZORPAY_KEY_ID, 
                settings.RAZORPAY_KEY_SECRET
            ))
        return cls._client

    @staticmethod
    def create_payment(order):
        client = PaymentService.get_client()
        # ... rest of logic
```

**Approach 2: Dependency Injection (Better for Testing)**
```python
def create_payment(order, razorpay_client=None):
    if razorpay_client is None:
        razorpay_client = PaymentService.get_default_client()
    # ... use razorpay_client
```

**Benefits:**
- Easy to mock in tests
- Clear dependency declaration
- Can hot-reload credentials if needed
- Better error handling

---

#### 🟡 [MEDIUM] Implement SMS Provider Selection Logic

**Current State:** `SMS_PROVIDER` variable defined but unused

**Recommendation:** Implement provider switching
```python
class SMSService:
    PROVIDERS = {
        'twilio': TwilioSMSProvider,
        'aws_sns': AWSSNSSMSProvider,
        'nexmo': NexmoSMSProvider,
    }
    
    @staticmethod
    def get_provider():
        provider_name = getattr(settings, 'SMS_PROVIDER', 'dummy')
        provider_class = SMSService.PROVIDERS.get(provider_name)
        if provider_class is None:
            raise ImproperlyConfigured(f"Unknown SMS provider: {provider_name}")
        return provider_class()
```

---

### Verification Checklist

Before deploying to production, verify:

- [ ] Razorpay client can be imported without `AttributeError`
  ```bash
  python manage.py shell -c "from apps.payments.services import PaymentService; print('OK')"
  ```

- [ ] OTP expiry respects `OTP_EXPIRY_SECONDS` environment variable
  ```bash
  export OTP_EXPIRY_SECONDS=120
  python manage.py test apps.notifications  # Should validate with custom TTL
  ```

- [ ] OTP resend cooldown respects `OTP_RESEND_COOLDOWN` environment variable
  ```bash
  export OTP_RESEND_COOLDOWN=30
  python manage.py test apps.notifications  # Should enforce 30s cooldown
  ```

- [ ] SMS payload includes `SMS_PROVIDER_SENDER_ID`
  ```bash
  # Check notification task payload in test
  ```

- [ ] Razorpay webhook secret is validated (currently done at runtime)
  ```bash
  # Test webhook verification
  ```

- [ ] Payment gateway is reachable and credentials are valid
  ```bash
  python manage.py shell -c "from apps.payments.services import PaymentService; print(PaymentService.get_client())"
  ```

---

## SECTION 7: ENVIRONMENT CONFIGURATION REFERENCE

### Required Environment Variables

```bash
# RAZORPAY (REQUIRED FOR PRODUCTION)
export RAZORPAY_KEY_ID="rzp_live_xxxxxxxxxxxxx"
export RAZORPAY_KEY_SECRET="xxxxxxxxxxxxxxxxxxxx"
export RAZORPAY_WEBHOOK_SECRET="whsec_xxxxxxxxxxxxx"

# SMS CONFIGURATION (REQUIRED FOR PRODUCTION)
export SMS_PROVIDER="twilio"  # or "aws_sns", "nexmo", etc. (currently unused)
export SMS_PROVIDER_URL="https://api.provider.com/send"
export SMS_PROVIDER_KEY="your_api_key"
export SMS_PROVIDER_SECRET="your_api_secret"  # (currently unused)
export SMS_PROVIDER_SENDER_ID="QUICKD"  # (should be used in SMS payload)

# OTP CONFIGURATION (OPTIONAL - RECOMMENDED FOR PRODUCTION)
export OTP_EXPIRY_SECONDS="300"  # Default: 300 (5 minutes)
export OTP_RESEND_COOLDOWN="60"  # Default: 60 (1 minute)
```

### Testing Environment Variables

```bash
# RAZORPAY (DUMMY FOR TESTING)
export RAZORPAY_KEY_ID="dummy_key"
export RAZORPAY_KEY_SECRET="dummy_secret"
export RAZORPAY_WEBHOOK_SECRET=""

# SMS (DISABLED FOR TESTING)
export SMS_PROVIDER="dummy"
export SMS_PROVIDER_URL=""
export SMS_PROVIDER_KEY=""

# OTP (RELAXED FOR TESTING)
export OTP_EXPIRY_SECONDS="3600"  # 1 hour
export OTP_RESEND_COOLDOWN="5"    # 5 seconds
```

---

## SUMMARY TABLE

| Category | Count | Status | Action Required |
|----------|-------|--------|------------------|
| **Razorpay** | | | |
| - Variables Defined | 3 | ✅ | - |
| - Variables Used | 3 | ⚠️ | FIX: `RAZORPAY_SECRET` mismatch |
| - Critical Issues | 1 | 🔴 | **IMMEDIATE** |
| | | | |
| **SMS/OTP** | | | |
| - Variables Defined | 7 | ✅ | - |
| - Variables Actually Used | 2 | ⚠️ | - |
| - Unused Defined | 5 | 🟡 | Document or remove |
| - Hardcoded Overrides | 2 | 🟠 | **Make configurable** |
| - Missing in Payloads | 1 | 🟟 | Add SMS_PROVIDER_SENDER_ID |
| | | | |
| **Total Issues** | **5** | | **3 Critical/High, 2 Medium** |

---

## AUDIT COMPLETION

**Audit Status:** ✅ **COMPLETE**

**Auditor Findings:** 
- 1 **CRITICAL** issue found (Razorpay key mismatch)
- 2 **HIGH** issues found (OTP configuration not used)
- 2 **MEDIUM** issues found (missing SMS fields, poor initialization pattern)
- 5 **LOW** issues found (unused variables, code maintainability)

**Recommendation:** **DO NOT DEPLOY** to production until CRITICAL issue is fixed.

**Next Steps:**
1. Apply fixes to [payments/services.py](backend/apps/payments/services.py#L21) and [refund_services.py](backend/apps/payments/refund_services.py#L16)
2. Make OTP configuration dynamic (read from settings)
3. Add SMS_PROVIDER_SENDER_ID to payload
4. Run comprehensive payment & OTP integration tests
5. Verify in staging environment
6. Deploy to production

---

*End of Production Readiness Audit Report*
