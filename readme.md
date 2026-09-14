# 🛒 E-Commerce API — Asynchronous FastAPI Backend

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/PostgreSQL-Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white" alt="Supabase"/>
  <img src="https://img.shields.io/badge/RabbitMQ-CloudAMQP-FF6600?style=for-the-badge&logo=rabbitmq&logoColor=white" alt="RabbitMQ"/>
  <img src="https://img.shields.io/badge/Celery-Task%20Queue-37814A?style=for-the-badge&logo=celery&logoColor=white" alt="Celery"/>
  <img src="https://img.shields.io/badge/Deployed%20on-Render-46E3B7?style=for-the-badge&logo=render&logoColor=white" alt="Render"/>
</p>

<p align="center">
  <b>A fault-tolerant, JWT-secured REST backend for a multi-role e-commerce platform</b><br/>
  built to keep core transactions alive even when downstream infrastructure isn't.
</p>

---

## 📖 Executive Summary

This is a production-deployed e-commerce backend built with **FastAPI**, backed by **Supabase PostgreSQL** for transactional data and **CloudAMQP (hosted RabbitMQ)** for asynchronous side-effects. It was architected around a single core principle: **a user's order should never fail because a notification couldn't be sent.** Database writes and background task dispatch are deliberately decoupled, so broker downtime, network blips, or worker outages degrade gracefully instead of surfacing as client-facing `500` errors.

---

## 🏗️ System Architecture & Request Lifecycle

```mermaid
graph TD
    A[Client / Swagger UI] -->|HTTPS Request + JWT| B[FastAPI Web Service on Render]
    B -->|SQLAlchemy Session| C[(Supabase PostgreSQL)]
    B -->|"task.delay() — fire & forget"| D{CloudAMQP RabbitMQ Broker}
    D -->|email_queue| E[Celery Worker]
    D -->|notification_queue| E
    D -->|analytics_queue| E
    E -->|Restores stock / reads orders| C
    D -.->|Unacked / rejected messages| F[(Dead-Letter Queue)]
    G[Celery Beat Scheduler] -.->|Periodic trigger| D

    style B fill:#009688,color:#fff
    style C fill:#3ECF8E,color:#fff
    style D fill:#FF6600,color:#fff
    style E fill:#37814A,color:#fff
    style F fill:#333,color:#fff
```

### Data Lifecycle Breakdown

| Stage | What Happens |
|---|---|
| **1. Request Parsing** | FastAPI validates the incoming payload against a Pydantic schema and resolves the caller's identity via a JWT bearer token (`OAuth2PasswordBearer`). |
| **2. DB Transaction** | Business logic runs inside an explicit `try/except` block — stock checks, total calculation, row inserts — committed to Supabase Postgres via SQLAlchemy's `Session`. |
| **3. Response Commit Point** | Once the transaction is committed and refreshed, the primary business object (order, product, user) is considered **durably saved**, independent of anything that follows. |
| **4. Async Task Dispatch** | A *separate*, isolated `try/except` wraps the `task.delay(...)` call. If CloudAMQP is unreachable, the exception is caught, logged, and swallowed — it never propagates into the HTTP response. |
| **5. Worker Execution** | An independently deployed Celery worker process, long-polling the broker, picks up the message, opens its own DB session, and executes the side effect (email log, stock restore, alert). |

---

## ⚙️ Core API Features & Capabilities

### 🔐 Authentication & Authorization
- OAuth2 **Password Flow** login (`/login`) issuing signed **JWT** access tokens (HS256).
- Passwords hashed with **Passlib + Bcrypt** — plaintext credentials are never persisted.
- Role-based access control across two tiers: `customer` and `seller`, enforced via FastAPI dependency injection (`get_current_user`, `get_current_seller`).
- Stateless token verification — no server-side session store required.

### 📦 Product & Catalog Management
- Public, unauthenticated product browsing and single-product lookup.
- Seller-gated product creation (**bulk insert supported**), update, and deletion.
- Automatic **price-drop detection** on update, triggering a downstream notification task only when the new price is lower than the previous one.

### 🧾 Order Processing System
- Multi-item order creation with **backend-authoritative total calculation** — client-submitted prices are never trusted.
- Live stock validation and decrement at order time, with **automatic rollback** on insufficient inventory or invalid products.
- Order status transitions (`PENDING → SHIPPED / CANCELLED`) drive downstream Celery task routing.
- Ownership + role-based authorization on every read/update/delete — customers can only act on their own orders; `seller`/`admin` roles have elevated visibility.

### 📬 Asynchronous Notification Pipeline
- Dedicated Celery queues (`email_queue`, `notification_queue`, `analytics_queue`) with routing keys per task category.
- **Dead-Letter Exchange (DLX)** configured on every primary queue — failed or rejected messages are automatically rerouted rather than silently dropped.
- **Celery Beat** periodic jobs: low-stock inventory sweeps and abandoned-cart reminder scans, decoupled entirely from request/response cycles.
- Automatic Celery-level retries (`max_retries=3`) on transient task failures (e.g. order cancellation stock-restore).

---

## 🛡️ Fault-Tolerance & Resilience Design

The defining architectural decision in this codebase is the **isolation boundary between transactional and non-transactional work**:

```python
# 1. Transactional core — must succeed or the request fails cleanly
db.add(new_order)
db.commit()
db.refresh(new_order)

# 2. Non-transactional side-effect — isolated so broker issues can't fail the request
try:
    send_order_confirmation_email.delay(current_user.email, new_order.id)
except Exception as e:
    print(f"⚠️ Celery broker unreachable: {e}")
```

This means:
- ✅ A CloudAMQP outage, network partition, or expired broker credential **never** produces an HTTP `500` on the order/product endpoints.
- ✅ The order or product record is **always durably persisted** before any messaging is attempted.
- ✅ Failures in dispatch are logged for observability without blocking the caller.
- ⚠️ The trade-off: message delivery is **best-effort at dispatch time**. If you need guaranteed delivery, pair this with an outbox pattern or periodic reconciliation job — noted here deliberately as a known and accepted trade-off, not an oversight.

---

## 💻 Local Development Setup

### Prerequisites
- Python 3.11+
- A running PostgreSQL instance (local, Supabase, or Dockerized)
- A running RabbitMQ instance (local, or a CloudAMQP free-tier instance)

### 1. Clone & install dependencies
```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment
Create a `.env` file in the project root (see [Environment Variables](#-environment-variables-reference) below for the full reference).

### 3. Run database migrations
```bash
alembic upgrade head
```

### 4. Start the API server
```bash
uvicorn app.main:app --reload
```
- API: `http://127.0.0.1:8000`
- Interactive docs: `http://127.0.0.1:8000/docs`

### 5. Start the Celery worker (separate terminal)
```bash
celery -A app.redis.celery_app worker --loglevel=info
```

### 6. Start Celery Beat for scheduled jobs (separate terminal)
```bash
celery -A app.redis.celery_app beat --loglevel=info
```

### Optional: Docker Compose (Postgres + RabbitMQ only)
```yaml
# docker-compose.yml
version: "3.9"
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: shop
    ports:
      - "5432:5432"

  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "5672:5672"
      - "15672:15672"   # Management UI
```
```bash
docker-compose up -d
```

> ⚠️ **Production note:** the deployed Render **Web Service** only runs `uvicorn` — it does not execute Celery workers or beat. Those must be deployed as separate long-running processes (Render Background Workers, or any always-on host) pointed at the same `CELERY_BROKER_URL`. A worker process that isn't running will silently leave messages queued and unconsumed in CloudAMQP.

---

## 🔑 Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | Signing secret for JWT access tokens. Keep this out of version control. |
| `ALGORITHM` | ✅ (default `HS256`) | JWT signing algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ (default `60`) | Access token lifetime, in minutes. |
| `DATABASE_URL` / `SUPABASE_DB_URL` | ✅ (one of) | Full Postgres connection string. `postgres://` is auto-normalized to `postgresql://` for SQLAlchemy. |
| `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT` | Optional | Fallback discrete DB fields, used only if no connection string is set — intended for local dev. |
| `CELERY_BROKER_URL` | ✅ | Full AMQP(S) connection string (e.g. CloudAMQP `amqps://user:pass@host/vhost`). Falls back to `amqp://guest:guest@localhost:5672//` if unset. |
| `RABBITMQ_HOST`, `RABBITMQ_PORT` | Optional | Legacy discrete broker fields — superseded by `CELERY_BROKER_URL`. |
| `REDIS_HOST`, `REDIS_PORT` | Optional | Reserved for future caching/session use — not currently wired into the broker or backend. |

---

## 📡 API Endpoints Quick Reference

### Auth
| Method | Route | Auth | Description |
|---|---|---|---|
| `POST` | `/login` | Public | OAuth2 password-flow login; returns a signed JWT access token. |

### Users
| Method | Route | Auth | Description |
|---|---|---|---|
| `GET` | `/users/` | Public | List all registered users. |
| `POST` | `/users/` | Public | Register a new user; returns the user profile + access token. |
| `GET` | `/users/{id}` | Public | Fetch a single user by ID. |

### Products
| Method | Route | Auth | Description |
|---|---|---|---|
| `GET` | `/products/` | Public | List products with optional search/price filters. |
| `GET` | `/products/{id}` | Public | Fetch a single product by ID. |
| `POST` | `/products/` | Seller | Bulk-create one or more products; dispatches a new-product notification. |
| `PUT` | `/products/{id}` | Seller | Update a product; dispatches a price-drop alert if the price decreased. |
| `DELETE` | `/products/{id}` | Seller | Delete a product. |

### Orders
| Method | Route | Auth | Description |
|---|---|---|---|
| `GET` | `/orders/` | Authenticated | List the caller's own orders (or filter by `user_id` as seller/admin). |
| `POST` | `/orders/` | Authenticated | Place an order; validates stock, computes total server-side, dispatches a confirmation email task. |
| `GET` | `/orders/{id}` | Owner / Seller / Admin | Fetch a single order. |
| `PUT` | `/orders/{id}` | Owner / Seller / Admin | Replace order fields and/or line items. |
| `PATCH` | `/orders/{id}/status` | Owner / Seller / Admin | Update order status; dispatches shipment or cancellation tasks accordingly. |
| `DELETE` | `/orders/{id}` | Owner / Seller / Admin | Cancel and delete an order, restoring product stock. |

---

## 🧵 Background Task ↔ Queue Mapping

| Trigger | Queue | Task |
|---|---|---|
| Order placed | `email_queue` | `send_order_confirmation_email` |
| Order marked `SHIPPED` | `email_queue` | `process_order_shipped_email` |
| Order marked `CANCELLED` | `email_queue` | `process_order_cancellation` (restores stock, retries up to 3×) |
| New product listed | `notification_queue` | `notify_users_new_product` |
| Product price reduced | `notification_queue` | `send_price_drop_alert` |
| Scheduled — every 30s (dev) | `analytics_queue` | `check_low_stock_inventory` |
| Scheduled — daily @ midnight | `notification_queue` | `send_abandoned_cart_reminders` |

All queues are DLX-armed — failed or expired messages route to `dead_letter_queue` for later inspection instead of being silently dropped.

---

## 🗺️ Roadmap

- [ ] Deploy Celery worker & beat as dedicated Render Background Workers
- [ ] Add Flower dashboard for live task/queue observability
- [ ] Refresh-token support for longer-lived sessions
- [ ] Pagination + filtering on product/order listing (backend groundwork already present)
- [ ] Automated test suite (pytest + httpx AsyncClient)
- [ ] Outbox pattern for guaranteed-delivery messaging

---

## 📄 License

Open for personal and educational use. Add a formal license (MIT recommended) before public distribution.
