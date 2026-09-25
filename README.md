# EVE Healthcare — Diagnostic Booking API

A production-quality backend service for booking diagnostic tests and simulating payments. Built as part of the EVE Healthcare SDE Intern assignment.

## Tech Stack

| Layer | Choice |
|---|---|
| Framework | FastAPI (Python 3.11) |
| Database | PostgreSQL + SQLAlchemy (async) |
| Migrations | Alembic |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Caching | Redis (optional, graceful fallback) |
| Rate limiting | slowapi |
| Logging | python-json-logger (structured JSON) |
| Testing | Pytest + httpx (async) |
| CI | GitHub Actions |
| Container | Docker + docker-compose |

---

## Running Locally

### Without Docker

**Prerequisites:** Python 3.11+, PostgreSQL running, Redis (optional)

```bash
# 1. Clone and enter the repo
git clone https://github.com/your-username/diagnostic-booking-api
cd diagnostic-booking-api

# 2. Create and activate a virtualenv
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Edit .env — set DATABASE_URL to your local Postgres instance

# 5. Run migrations
alembic upgrade head

# 6. Start the server
uvicorn app.main:app --reload --port 8000
```

The API will be at `http://localhost:8000` and the Swagger docs at `http://localhost:8000/docs`.

### With Docker

```bash
cp .env.example .env
docker compose up --build
```

This starts Postgres, Redis, and the app. Migrations run automatically on startup.

---

## Running Tests

Tests use **SQLite** (via `aiosqlite`) instead of PostgreSQL for speed and zero-infrastructure convenience. The full test suite runs without any running services.

```bash
source venv/bin/activate
pytest -v
```

**SQLite vs Postgres tradeoff:** SQLite doesn't support `UUID` columns natively, PostgreSQL ENUM types, or some FK cascade behaviours. In a production CI setup, you'd use a real Postgres container (e.g., via GitHub Actions `services:` or `docker-compose -f docker-compose.test.yml up`). The idempotency guarantee (UNIQUE constraint + IntegrityError catch) still works correctly under SQLite.

---

## API Endpoints

### Auth

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/signup` | No | Create account |
| POST | `/auth/login` | No | Get JWT token |

**Signup:**
```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "john@example.com", "password": "mypassword1", "full_name": "John Doe"}'
```
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "email": "john@example.com",
  "full_name": "John Doe",
  "created_at": "2026-09-25T10:00:00Z"
}
```

**Login:**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "john@example.com", "password": "mypassword1"}'
```
```json
{ "access_token": "eyJ...", "token_type": "bearer" }
```

---

### Diagnostic Centres

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/centres/` | No | List all centres (paginated) |
| GET | `/centres/{id}` | No | Get single centre |
| POST | `/centres/` | Required | Create centre |
| GET | `/centres/{id}/tests` | No | List tests at a centre (paginated) |
| POST | `/centres/{id}/tests` | Required | Add test to centre |

**List centres:**
```bash
curl "http://localhost:8000/centres/?page=1&page_size=10"
```
```json
{
  "total": 2,
  "page": 1,
  "page_size": 10,
  "items": [
    { "id": "...", "name": "City Diagnostics", "location": "Mumbai", "created_at": "..." }
  ]
}
```

**Create centre:**
```bash
curl -X POST http://localhost:8000/centres/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "City Diagnostics", "location": "Mumbai, Maharashtra"}'
```

**Add test to centre:**
```bash
curl -X POST http://localhost:8000/centres/<centre_id>/tests \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Complete Blood Count", "price": 350.00}'
```

---

### Bookings

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/bookings/` | Required | Create booking (PENDING) |
| GET | `/bookings/` | Required | List own bookings (paginated) |
| GET | `/bookings/{id}` | Required | Get booking detail |
| PATCH | `/bookings/{id}/cancel` | Required | Cancel booking |

**Create booking:**
```bash
curl -X POST http://localhost:8000/bookings/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "test_id": "<test_uuid>",
    "centre_id": "<centre_uuid>",
    "appointment_datetime": "2030-01-15T10:30:00Z"
  }'
```
```json
{
  "id": "...",
  "user_id": "...",
  "test_id": "...",
  "centre_id": "...",
  "appointment_datetime": "2030-01-15T10:30:00Z",
  "amount": "350.00",
  "status": "PENDING",
  "created_at": "...",
  "updated_at": "..."
}
```

**Cancel booking:**
```bash
curl -X PATCH http://localhost:8000/bookings/<booking_id>/cancel \
  -H "Authorization: Bearer <token>"
```

---

### Payments

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/payments/` | Required | Simulate payment for a booking |
| POST | `/payments/webhook/` | No | Idempotent webhook handler |

**Simulate payment:**
```bash
curl -X POST http://localhost:8000/payments/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"booking_id": "<booking_uuid>"}'
```
```json
{
  "id": "...",
  "booking_id": "...",
  "amount": "350.00",
  "status": "SUCCESS",
  "provider_ref": "sim-a3f9c12e4b7d",
  "created_at": "..."
}
```

> Pass `"force_result": "success"` or `"force_result": "fail"` in the request body to control the outcome deterministically (useful for testing).

**Payment webhook (idempotent):**
```bash
# First call — processes the event
curl -X POST http://localhost:8000/payments/webhook/ \
  -H "Content-Type: application/json" \
  -d '{"event_id": "evt-12345", "booking_id": "<uuid>", "status": "SUCCESS"}'
# → {"event_id": "evt-12345", "result": "processed"}

# Identical second call — ignored safely
curl -X POST http://localhost:8000/payments/webhook/ \
  -d '{"event_id": "evt-12345", "booking_id": "<uuid>", "status": "SUCCESS"}'
# → {"event_id": "evt-12345", "result": "duplicate_ignored"}
```

---

## Database Schema

```
users
  id (UUID PK)
  email (VARCHAR unique, indexed)
  hashed_password (VARCHAR)
  full_name (VARCHAR)
  created_at (TIMESTAMPTZ)

diagnostic_centres
  id (UUID PK)
  name (VARCHAR)
  location (VARCHAR)
  created_at (TIMESTAMPTZ)

diagnostic_tests
  id (UUID PK)
  name (VARCHAR)
  price (NUMERIC 10,2)
  centre_id (UUID FK → diagnostic_centres, indexed)
  created_at (TIMESTAMPTZ)

bookings
  id (UUID PK)
  user_id (UUID FK → users, indexed)
  test_id (UUID FK → diagnostic_tests)
  centre_id (UUID FK → diagnostic_centres)
  appointment_datetime (TIMESTAMPTZ)
  amount (NUMERIC 10,2)  -- snapshot of test.price at booking time
  status (ENUM: PENDING | CONFIRMED | FAILED | CANCELLED)
  created_at (TIMESTAMPTZ)
  updated_at (TIMESTAMPTZ)

payments
  id (UUID PK)
  booking_id (UUID FK → bookings, unique)  -- one payment per booking
  amount (NUMERIC 10,2)
  status (ENUM: SUCCESS | FAILED)
  provider_ref (VARCHAR)
  created_at (TIMESTAMPTZ)

webhook_events
  id (UUID PK)
  event_id (VARCHAR unique)  -- idempotency key
  booking_id (UUID FK → bookings)
  status (VARCHAR)
  processed_at (TIMESTAMPTZ)
```

**Booking state machine:**
```
PENDING → CONFIRMED  (payment success / webhook SUCCESS)
PENDING → FAILED     (payment failure / webhook FAILED)
PENDING → CANCELLED  (user cancels)
CONFIRMED, FAILED, CANCELLED → (terminal, no further transitions)
```

---

## Assumptions

1. **Centre/test creation is open to any authenticated user** — the assignment says "admin-style, but keep simple." There's no admin role. A real system would add RBAC.

2. **Payment simulation:** By default, payments succeed with 80% probability. Pass `force_result: "success"/"fail"` in the request body for deterministic outcomes (test-friendly).

3. **`appointment_datetime` validation:** Must be a future timestamp (validated in Pydantic). No business-hours or slot-availability logic — that would require a scheduling subsystem.

4. **`amount` is snapshotted at booking time** from `diagnostic_test.price`. If the price changes later, existing bookings are unaffected.

5. **Webhook idempotency relies on a DB UNIQUE constraint**, not a SELECT-then-INSERT check, to be safe under concurrent requests. The `IntegrityError` from a duplicate `event_id` INSERT is the signal to return "duplicate_ignored".

6. **Redis caching is optional** — the app starts and works fully without Redis. Cache misses just hit the DB.

7. **Rate limits:** Auth endpoints at 10–20 req/min per IP. Payment at 30/min. Webhook at 60/min. These are starting points; a production system needs tuning based on real traffic.

8. **JWT tokens expire in 60 minutes** (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`). No refresh token mechanism is implemented.

---

## What I'd Improve With More Time

- **Celery + Redis for async webhook retries** — current webhook processing is synchronous. If the DB is slow or the service crashes mid-processing, the event could be lost. A Celery task queue would handle retries with exponential backoff.

- **Real payment gateway integration** — replace the random simulator with a Stripe or Razorpay integration, including proper signature verification on webhooks.

- **Admin role / RBAC** — add an `is_admin` flag or a roles table so only admins can create centres/tests.

- **Appointment slot management** — prevent double-bookings for the same test + timeslot at a centre.

- **Refresh tokens** — current JWTs are short-lived with no way to refresh; users get logged out after 60 min.

- **Better rate limiting** — use Redis-backed rate limiting (slowapi supports this) so limits work across multiple app replicas, not just per-process.

- **Pagination cursor-based** — the current page/offset approach has drift issues on large datasets. Keyset pagination would be more robust.

- **Health checks with DB connectivity** — the `/health` endpoint currently just returns OK; it should check that DB and Redis are reachable.

- **Soft deletes** — rather than hard-deleting users or centres, add `deleted_at` columns.

- **OpenTelemetry tracing** — structured logs are a start, but distributed tracing (Jaeger/Tempo) would make debugging production issues much faster.
