# EventMate MVP - Complete Verification Guide

## Pre-flight Setup

```cmd
REM Set your backend URL
set BASE_URL=http://localhost:8000

REM Create migrations and seed data
docker compose exec backend python manage.py makemigrations billing
docker compose exec backend python manage.py makemigrations payments
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_plans
```

## Authentication Setup

```cmd
REM Register Provider
curl -X POST %BASE_URL%/api/v1/auth/register/ ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"provider@test.com\",\"password\":\"Test1234\",\"role\":\"provider\"}"

REM Register Client  
curl -X POST %BASE_URL%/api/v1/auth/register/ ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"client@test.com\",\"password\":\"Test1234\",\"role\":\"client\"}"

REM Login Provider - save access token
curl -X POST %BASE_URL%/api/v1/auth/login/ ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"provider@test.com\",\"password\":\"Test1234\"}"

REM Save token: set PROVIDER_TOKEN=eyJ...

REM Login Client - save access token
curl -X POST %BASE_URL%/api/v1/auth/login/ ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"client@test.com\",\"password\":\"Test1234\"}"

REM Save token: set CLIENT_TOKEN=eyJ...

REM Get Admin Token (Create superuser first if needed)
REM docker compose exec backend python manage.py createsuperuser
curl -X POST %BASE_URL%/api/v1/auth/login/ ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"admin@test.com\",\"password\":\"Admin123\"}"

REM Save token: set ADMIN_TOKEN=eyJ...
```

---

## 1. Billing & Plans

### View Available Plans (Public)

```cmd
curl %BASE_URL%/api/v1/plans/
```

**Expected:** 200 OK - 3 plans (Free, Pro, Enterprise)

### Check Current Subscription

```cmd
curl -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  %BASE_URL%/api/v1/billing/subscription/
```

**Expected:** 200 OK - Free plan (default)

### Subscribe to Free Plan (Immediate activation)

```cmd
curl -X POST ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"plan_id\":1}" ^
  %BASE_URL%/api/v1/billing/subscribe/
```

**Expected:** 201 Created - `is_active: true`

### Subscribe to Pro Plan (Requires payment)

```cmd
curl -X POST ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"plan_id\":2}" ^
  %BASE_URL%/api/v1/billing/subscribe/
```

**Expected:** 201 Created - `is_active: false`

---

## 2. Payments (Mock)

### Create Payment for Pro Subscription

```cmd
REM Use subscription_id from previous response
curl -X POST ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"subscription_id\":2}" ^
  %BASE_URL%/api/v1/payments/create/
```

**Expected:** 201 Created - `status: "pending"`

### Mark Payment as Paid (Activates subscription)

```cmd
REM Use payment_id from previous response
curl -X POST ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  %BASE_URL%/api/v1/payments/1/mark-paid/
```

**Expected:** 200 OK - `status: "paid"`, subscription now active.

### Security: Test Duplicate Mark-Paid (400)

```cmd
curl -X POST ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  %BASE_URL%/api/v1/payments/1/mark-paid/
```

**Expected:** `400 Bad Request` - "Payment is not pending"

---

## 3. Service Limits

### Create Services (Free limit = 3)

```cmd
REM Subscribe back to Free (plan_id=1) for testing
curl -X POST -H "Authorization: Bearer %PROVIDER_TOKEN%" -H "Content-Type: application/json" -d "{\"plan_id\":1}" %BASE_URL%/api/v1/billing/subscribe/

REM Service 1-3 (201 Created)
REM Service 4 (should fail)
curl -X POST ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"category\":1,\"title\":\"Service 4\",\"description\":\"Test\",\"price_type\":\"fixed\",\"price_amount\":10000,\"city\":\"Almaty\",\"is_active\":true}" ^
  %BASE_URL%/api/v1/services/
```

**Expected:** `403 Forbidden` - "Plan limit reached: max_services"

---

## 4. Offers & Security

### View My Offers (Provider)

```cmd
curl -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  %BASE_URL%/api/v1/offers/my/
```

**Expected:** 200 OK - List of provider's offers

### View Offers by Request (Client)

```cmd
REM Replace 1 with actual request ID
curl -H "Authorization: Bearer %CLIENT_TOKEN%" ^
  %BASE_URL%/api/v1/offers/by-request/1/
```

**Expected:** 200 OK - List of offers for that request

### Security: Access Control (403)

```cmd
REM Provider trying to view client's request offers
curl -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  %BASE_URL%/api/v1/offers/by-request/1/
```

**Expected:** `403 Forbidden` - "You can only view offers for your own requests"

### Security: Non-existent Request (404)

```cmd
curl -H "Authorization: Bearer %CLIENT_TOKEN%" ^
  %BASE_URL%/api/v1/offers/by-request/99999/
```

**Expected:** `404 Not Found` - "Request not found"

---

## 5. Moderation (Provider Blocking)

### 1. Apply Migrations
```cmd
REM Generate and apply migrations universally
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
```

### 2. Verify Blocking (403 Forbidden)

**Preparation:**
1. Identify a Request ID and Service ID for testing.
```cmd
set REQUEST_ID=1
set SERVICE_ID=1
```
2. As Provider (**before blocking**), create a paid subscription:
```cmd
curl -X POST %BASE_URL%/api/v1/billing/subscribe/ ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"plan_id\":2}"
```
3. Save the returned subscription ID from the response:
```cmd
set SUBSCRIPTION_ID=...
```
4. In Django Admin (`/admin/accounts/providerprofile/`), find your provider and set **is_blocked = True**.

**Checklist:**
- [x] Admin can toggle **is_blocked** in `ProviderProfile`
- [ ] Blocked provider operations return **403 Forbidden**
- [ ] Detail message: `"Your provider profile is blocked."`

**Test Service Creation (Blocked Provider):**
```cmd
curl -X POST %BASE_URL%/api/v1/services/ ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"category\":1,\"title\":\"Blocked Service\",\"description\":\"Test\",\"price_type\":\"fixed\",\"price_amount\":10000,\"city\":\"Almaty\",\"is_active\":true}"
```
**Expected:** `403 Forbidden`

**Test Offer Creation (Blocked Provider):**
```cmd
curl -X POST %BASE_URL%/api/v1/offers/ ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"request\":%REQUEST_ID%,\"service\":%SERVICE_ID%,\"price\":50000,\"cover_letter\":\"Blocked offer\"}"
```
**Expected:** `403 Forbidden`

**Test Subscription (Blocked Provider):**
```cmd
curl -X POST %BASE_URL%/api/v1/billing/subscribe/ ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"plan_id\":1}"
```
**Expected:** `403 Forbidden`

**Test Payment Creation (Blocked Provider):**
```cmd
curl -X POST %BASE_URL%/api/v1/payments/create/ ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"subscription_id\":%SUBSCRIPTION_ID%}"
```
**Expected:** `403 Forbidden`

---

## 6. QR Security Flow

### Generate QR (Start)

```cmd
curl -H "Authorization: Bearer %CLIENT_TOKEN%" ^
  %BASE_URL%/api/v1/orders/1/qr-code/?type=start
```

**Expected:** 200 OK - JWT Token

### Provider Scan (Check-in)

```cmd
curl -X POST ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"token\":\"%TOKEN%\"}" ^
  %BASE_URL%/api/v1/orders/1/actions/check-in/
```

**Expected:** Order status -> `in_progress`

---

## Phase 6: Reviews & Ratings

### 1. Apply Migrations
```cmd
docker compose exec backend python manage.py makemigrations marketplace
docker compose exec backend python manage.py migrate
```

### 2. Preparation (Complete an Order)
Ensure you have an order with status **COMPLETED**.
```cmd
REM 1. Get client orders list
curl -H "Authorization: Bearer %CLIENT_TOKEN%" %BASE_URL%/api/v1/orders/

REM 2. Identify an order with status "completed" and set its ID
set ORDER_ID=...
```

### 3. Create Review (POST)
```cmd
curl -X POST %BASE_URL%/api/v1/reviews/ ^
  -H "Authorization: Bearer %CLIENT_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"order\":%ORDER_ID%,\"rating\":5,\"text\":\"Perfect service!\"}"
```
**Expected:** 201 Created

**Security Check (403):** Try creating a review using a provider token or for someone else's order.
**Status Check (400):** Try creating a review for an order that is not **COMPLETED**.

### 4. View Provider Reviews (Public)
```cmd
REM Get the provider_profile ID from the order or provider search
set PROVIDER_PROFILE_ID=...

curl %BASE_URL%/api/v1/providers/%PROVIDER_PROFILE_ID%/reviews/
```
**Expected:** 200 OK - List of reviews for this provider.

### 5. Verify Provider Rating
Check in **Django Admin** -> `ProviderProfile` (`rating_avg`, `reviews_count`) or via a provider profile API. The values should be updated automatically based on existing reviews.

---

## Phase 7: Notifications (Mock API)

### 1. Apply Migrations
```cmd
docker compose exec backend python manage.py makemigrations notifications
docker compose exec backend python manage.py migrate
```

### 2. Verify NEW_OFFER Trigger
**Action:** `POST /api/v1/offers/` (Provider creates an offer).
Then, as a **Client**:
```cmd
curl -H "Authorization: Bearer %CLIENT_TOKEN%" %BASE_URL%/api/v1/notifications/
```
**Expected:** 200 OK - Notification with `type: "NEW_OFFER"`.

### 3. Verify OFFER_ACCEPTED Trigger
**Action:** `POST /api/v1/offers/{id}/accept/` (Client accepts an offer).
Then, as a **Provider**:
```cmd
curl -H "Authorization: Bearer %PROVIDER_TOKEN%" %BASE_URL%/api/v1/notifications/
```
**Expected:** 200 OK - Notification with `type: "OFFER_ACCEPTED"`.

### 4. Verify PAYMENT_CONFIRMED Trigger
**Action:** `POST /api/v1/payments/{id}/mark-paid/` (Payment confirmed).
Then, as a **Provider**:
```cmd
curl -H "Authorization: Bearer %PROVIDER_TOKEN%" %BASE_URL%/api/v1/notifications/
```
**Expected:** 200 OK - Notification with `type: "PAYMENT_CONFIRMED"`.

### 5. Mark Notification as Read
**Note:** You can only read and mark your **own** notifications.
```cmd
REM Identify notification ID from list response
set NOTIF_ID=...
curl -X POST -H "Authorization: Bearer %CLIENT_TOKEN%" %BASE_URL%/api/v1/notifications/%NOTIF_ID%/read/
```
**Expected:** `{"status": "read"}`. Verify `is_read` is now `true` in details.

**Security Check:** Attempt to mark a notification belonging to another user.
**Expected:** `403 Forbidden` - Only the owner can mark it as read.

### 6. Admin Panel
Access `/admin/notifications/notification/` to view the audit log of all system notifications (Read-only).
---

## Phase 8: Portfolio (Provider Cases)

### 1. Apply Migrations
```cmd
docker compose exec backend python manage.py makemigrations portfolio
docker compose exec backend python manage.py migrate
```

### 2. Create Portfolio Item (Provider Only)
```cmd
curl -X POST %BASE_URL%/api/v1/portfolio/items/ ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"title\":\"Wedding in Almaty 2025\",\"description\":\"Amazing summer wedding photoshoot\"}"
```
**Expected:** 201 Created. 
**Save IDs:** 
```cmd
set ITEM_ID=<id_from_response>
```

### 3. Add Media to Item (Owner Only)
```cmd
curl -X POST %BASE_URL%/api/v1/portfolio/items/%ITEM_ID%/media/ ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"file_url\":\"https://example.com/photo1.jpg\",\"media_type\":\"image\"}"
```
**Expected:** 201 Created. 
> [!NOTE]
> Maximum 10 media items are allowed per portfolio item (returns 400 Bad Request if exceeded).

### 4. Delete Media (Owner Only)
```cmd
set MEDIA_ID=<id_from_previous_step>
curl -X DELETE %BASE_URL%/api/v1/portfolio/media/%MEDIA_ID%/ ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%"
```
**Expected:** 204 No Content.

### 5. Public View Portfolio
```cmd
REM Identify your target provider_profile_id
set PROVIDER_PROFILE_ID=1
curl %BASE_URL%/api/v1/providers/%PROVIDER_PROFILE_ID%/portfolio/
```
**Expected:** 200 OK - List of items with nested media arrays.

### 6. Security & Permissions
- **Anonymous/Client Create**: Try `POST /portfolio/items/` without provider token. (Expected: 403)
- **Stranger Edit**: Try `PATCH /portfolio/items/%ITEM_ID%/` with a different provider. (Expected: 403)

---

## Phase 9: Favorites (Services & Providers)

### 1. Apply Migrations
```cmd
docker compose exec backend python manage.py makemigrations favorites
docker compose exec backend python manage.py migrate
```

### 2. Preparation (Identify Targets)
```cmd
REM 1. Get a service to favorite
curl %BASE_URL%/api/v1/services/
set SERVICE_ID=...

REM 2. Identify a provider profile ID (from service response or admin)
set PROVIDER_PROFILE_ID=...
```

### 3. Toggle Favorite (Client Only)
**Action:** `POST /api/v1/favorites/toggle/`
```cmd
REM Add service to favorites
curl -X POST %BASE_URL%/api/v1/favorites/toggle/ ^
  -H "Authorization: Bearer %CLIENT_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"content_type\":\"service\",\"object_id\":%SERVICE_ID%}"
```
**Expected:** `{"status": "added"}` (201 Created). Repeating deletes it -> `{"status": "removed"}` (200 OK).

### 4. List My Favorites (Hydrated)
```cmd
curl -H "Authorization: Bearer %CLIENT_TOKEN%" %BASE_URL%/api/v1/favorites/?type=all
```
**Expected:** 200 OK - List of items where `object_data` is fully populated with service/provider details.

### 5. Check is_favorite flag
```cmd
curl %BASE_URL%/api/v1/services/%SERVICE_ID%/ -H "Authorization: Bearer %CLIENT_TOKEN%"
```
**Expected:** Result contains `"is_favorite": true`.

### 6. Security & Status Checks
- **Provider Role**: Try toggling as provider. (Expected: `403 Forbidden` - "Only users with 'client' role...")
- **Favorite Self**: Try to favorite self (as provider-client). (Expected: `403 Forbidden` - "You cannot add yourself to favorites.")
- **Invalid Object**: Use %SERVICE_ID%=9999. (Expected: `404 Not Found` - "Service with id 9999 not found.")
- **Invalid Type**: Use `content_type: "invalid"`. (Expected: `400 Bad Request` - "Invalid content_type.")
- **Guest Access**: Try GET /favorites/ without token. (Expected: `403 Forbidden` or `401 Unauthorized`)

---

## Phase 10A: Q&A Comments

### 1. Apply Migrations
```cmd
docker compose exec backend python manage.py makemigrations comments
docker compose exec backend python manage.py migrate
```

### 2. Ask a Question (Any Authenticated User)
**Action:** `POST /api/v1/services/{id}/comments/`
```cmd
REM Get service ID
curl %BASE_URL%/api/v1/services/
set SERVICE_ID=...

curl -X POST %BASE_URL%/api/v1/services/%SERVICE_ID%/comments/ ^
  -H "Authorization: Bearer %CLIENT_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"Is this service available on Sundays?\"}"
```
**Expected:** 201 Created. `set COMMENT_ID=<id_from_response>`

### 3. Reply to Question (Service Provider Only)
**Action:** `POST /api/v1/services/{id}/comments/` with `parent`
```cmd
curl -X POST %BASE_URL%/api/v1/services/%SERVICE_ID%/comments/ ^
  -H "Authorization: Bearer %PROVIDER_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"Yes, we are open 24/7!\",\"parent\":%COMMENT_ID%}"
```
**Expected:** 201 Created.

### 4. View Q&A Tree
```cmd
curl %BASE_URL%/api/v1/services/%SERVICE_ID%/comments/
```
**Expected:** Root comment includes `replies` array with the provider's answer.

### 5. Soft Delete
```cmd
curl -X DELETE %BASE_URL%/api/v1/comments/%COMMENT_ID%/ ^
  -H "Authorization: Bearer %CLIENT_TOKEN%"
```
**Expected:** 204 No Content. Verify `text` is now `[deleted]` in the list.

### 6. Security Checks
- **Stranger Reply**: Try to reply to a comment for another provider's service. (Expected: 403)
- **Edit Forbidden**: Try to PATCH root comment (`%COMMENT_ID%`) after provider replied. (Expected: `403 Forbidden` - "Cannot edit a root comment that already has replies.")
- **Guest Post**: Try to post without token. (Expected: 401)
- **Reply to Reply**: Try to use a reply ID as `parent`. (Expected: 400 - Depth limit 1)

---

## Phase 10B: Reports (Complaints)

### 1. Apply Migrations
```cmd
docker compose exec backend python manage.py makemigrations reports
docker compose exec backend python manage.py migrate
```

### 2. File a Report
**Action:** `POST /api/v1/reports/`
```cmd
curl -X POST %BASE_URL%/api/v1/reports/ ^
  -H "Authorization: Bearer %CLIENT_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"content_type\":\"service\",\"object_id\":%SERVICE_ID%,\"reason\":\"fraud\",\"message\":\"This service looks suspicious.\"}"
```
**Expected:** 201 Created. `set REPORT_ID=...`

### 3. View My Reports
```cmd
curl -H "Authorization: Bearer %CLIENT_TOKEN%" %BASE_URL%/api/v1/reports/my/
```
**Expected:** Status is `open`.

### 4. Admin Resolution (Require Admin Token)
```cmd
REM 1. Set in-review
curl -X POST %BASE_URL%/api/v1/reports/%REPORT_ID%/set-in-review/ ^
  -H "Authorization: Bearer %ADMIN_TOKEN%"

REM 2. Resolve
curl -X POST %BASE_URL%/api/v1/reports/%REPORT_ID%/resolve/ ^
  -H "Authorization: Bearer %ADMIN_TOKEN%" ^
  -H "Content-Type: application/json" ^
  -d "{\"resolution_note\":\"The service was checked and verified.\"}"
```
**Expected:** Status updated to `resolved`.

### 5. Security Checks
- **Self-Report**: Try to report your own service or profile. (Expected: 400 validation error)
- **Object Missing**: List reports (`/my/`) after the reported object (e.g., a comment) has been deleted. (Expected: 200 OK - `object_missing: true`, `object_summary: null`)
- **Duplicate Report**: Try to report the same service again while previous is `open`. (Expected: 400)
- **Guest Access**: Try to filter a report without login. (Expected: 401)

---

## 11. Production Deployment & Security Guidelines

When deploying to Render (or other production hosting), enforce these configurations to maintain the Tech Stack safety:

### CORS & CSRF Hardening
* **Wildcards**: Do **NOT** set `CORS_ALLOWED_ORIGINS` or `CSRF_TRUSTED_ORIGINS` to `*` wildcard. Doing so leaks session credentials.
* **HTTPS**: All origins listed in `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` must use `https://`.
* **Cookie SameSite Constraint**:
  - The refresh token HttpOnly cookie is configured with `SameSite='Lax'`.
  - In a production setup where frontend and backend use completely different domains (e.g., `eventmate.netlify.app` and `eventmate-api.onrender.com`), browsers will reject sending Lax cookies on cross-origin requests.
  - **Recommended Mitigation**: Map custom domains so both frontend and backend share the same base domain name (e.g., `app.eventmate.com` for the UI, and `api.eventmate.com` for the backend).

### SSL Proxy configuration on Render
* Django settings must include `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` so it understands requests coming through the SSL-terminating Render proxy are secure.
* Ensure `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` are enabled in production (`not DEBUG`) to protect session data.

### SECRET_KEY Production Safety
* Under `DEBUG = False`, the server will block execution and raise `ImproperlyConfigured` if `SECRET_KEY` is not provided or equals the fallback dev string. Ensure a secure key is injected via Render environment variables.

---

## 12. Geographic Bounding Box & Radius Filters (Stage 29.2D)

This stage adds geographic database and distance filtering capabilities to the Service Catalog endpoint (`GET /api/v1/services/`).

### Database Index Verification

Verify that the composite B-tree coordinate index `service_lat_lng_idx` has been applied to the `Service` model:
```cmd
python manage.py showmigrations catalog
```
**Expected:** The migration `0006_service_service_lat_lng_idx` is marked as applied.

---

### Bounding Box Filtering (QuerySet Mode)

Find services located inside a bounding box (Almaty region):
```cmd
curl "%BASE_URL%/api/v1/services/?bbox=76.80,43.15,77.05,43.35"
```
**Expected:** 200 OK. Returns a paginated list of services with coordinates inside the rectangle. The `distance_m` field is omitted.

#### Validation Error Checks:
* Reversed bounds (`min_lat > max_lat` or `min_lng > max_lng`):
  ```cmd
  curl "%BASE_URL%/api/v1/services/?bbox=77.05,43.15,76.80,43.35"
  ```
  **Expected:** `400 Bad Request` validation message.
* Latitude/longitude out of range:
  ```cmd
  curl "%BASE_URL%/api/v1/services/?bbox=76.80,-95.0,77.05,43.35"
  ```
  **Expected:** `400 Bad Request`.
* NaN or Infinity parameters:
  ```cmd
  curl "%BASE_URL%/api/v1/services/?bbox=76.80,NaN,77.05,43.35"
  ```
  **Expected:** `400 Bad Request`.

---

### Center-Radius Distance Filtering (Radial Mode)

Find services within 5km of a specific coordinate in Almaty:
```cmd
curl "%BASE_URL%/api/v1/services/?lat=43.238949&lng=76.889709&radius=5000"
```
**Expected:** 200 OK. Returns a paginated list of services ordered nearest-first (by `distance_m`), with stable tie-break by primary key if distances are equal.
Each service inside the radius will include the dynamic read-only field:
`"distance_m": <integer>`

#### Validation Error Checks:
* Partial coordinates (lat/lng provided without radius):
  ```cmd
  curl "%BASE_URL%/api/v1/services/?lat=43.238949&lng=76.889709"
  ```
  **Expected:** `400 Bad Request`.
* Radius outside range (under 100m or over 100,000m):
  ```cmd
  curl "%BASE_URL%/api/v1/services/?lat=43.238949&lng=76.889709&radius=50"
  ```
  **Expected:** `400 Bad Request`.
* Conflicting filters (bbox + lat/lng/radius):
  ```cmd
  curl "%BASE_URL%/api/v1/services/?bbox=76.8,43.1,77.0,43.3&lat=43.2&lng=76.8&radius=1000"
  ```
  **Expected:** `400 Bad Request` detailing that only one geographic filter mode may be used.

---

### Automated QA Results

* **Catalog Tests**: 80/80 passed.
* **Full Backend Suite**: 224/224 passed.
* **Frontend Builds & Lints**: Next.js linting and production build compiles with 0 errors.

