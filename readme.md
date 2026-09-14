# 🛒 E-Commerce API (FastAPI + Celery + PostgreSQL)

A production-ready **e-commerce backend** built with **FastAPI**, **SQLAlchemy**, **PostgreSQL**, and **Celery + RabbitMQ** for asynchronous background tasks (order emails, notifications, and inventory alerts). It supports JWT-based authentication with role-based access control for **customers** and **sellers**.

---

## ✨ Features

- 🔐 **JWT Authentication** — secure login/register flow using OAuth2 password bearer tokens
- 👥 **Role-Based Access Control** — separate permissions for `customer` and `seller` roles
- 📦 **Product Management** — create, read, update, and track product stock
- 🧾 **Order Management** — place orders with multiple items, track order status, auto-calculate totals
- ⚙️ **Async Background Processing** — Celery workers with RabbitMQ broker for:
  - Order confirmation & shipment emails
  - Order cancellation with automatic stock restoration
  - New product broadcast notifications
  - Price-drop alerts
  - Abandoned cart reminders (orders pending 7+ days)
  - Low-stock inventory monitoring (scheduled via Celery Beat)
- 🗃️ **Dead-Letter Queue (DLQ)** support for failed task handling
- 🔑 **Password Hashing** via `bcrypt` (passlib)
- 🌐 **CORS enabled** for cross-origin frontend integration

---

## 🧱 Tech Stack

| Layer              | Technology                          |
|--------------------|--------------------------------------|
| Web Framework      | FastAPI                              |
| ORM / Database     | SQLAlchemy + PostgreSQL              |
| Auth               | python-jose (JWT), OAuth2, passlib   |
| Task Queue         | Celery                               |
| Message Broker     | RabbitMQ                             |
| Config Management  | pydantic-settings                    |
| Migrations         | Alembic                              |
| Server             | Uvicorn                              |

---

## 📁 Project Structure

```
app/
├── main.py            # FastAPI app entrypoint & router registration
├── config.py          # Environment-based settings (pydantic-settings)
├── database.py        # SQLAlchemy engine, session, and Base
├── models.py           # ORM models: User, Product, Order, Order_item
├── schema.py            # Pydantic request/response schemas
├── oauth2.py           # JWT creation & current-user/role dependencies
├── utiles.py           # Password hashing helpers
├── redis.py            # Celery app config (broker, queues, beat schedule)
├── tasks.py            # Celery background tasks
└── routers/
    ├── auth.py
    ├── users.py
    ├── products.py
    └── orders.py
requirements.txt
```

> **Note:** File names `schema.py`, `utiles.py`, and `redis.py` (which actually configures Celery/RabbitMQ) are preserved as-is from the current codebase.

---

## 🗂️ Data Models

| Model        | Key Fields                                                        |
|--------------|---------------------------------------------------------------------|
| `User`       | `id`, `email`, `password`, `role` (`customer`/`seller`), `created_at` |
| `Product`    | `id`, `title`, `description`, `price`, `stock`, `created_at`        |
| `Order`      | `id`, `user_id`, `status`, `total_amount`, `created_at`             |
| `Order_item` | `id`, `order_id`, `product_id`, `quantity`, `created_at`            |

Relationships:
- A `User` has many `Order`s.
- An `Order` has many `Order_item`s (cascade delete).
- Each `Order_item` references one `Product`.

---

## ⚙️ Environment Variables

Create a `.env` file in the project root:

```env
# Required
SECRET_KEY=your_super_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Database — use ONE of the following approaches:

# Option 1: Full connection string (e.g. Supabase / hosted Postgres)
DATABASE_URL=postgresql://user:password@host:port/dbname
# or
SUPABASE_DB_URL=postgres://user:password@host:port/dbname

# Option 2: Local dev — individual DB fields (used only if DATABASE_URL/SUPABASE_DB_URL is unset)
DB_HOST=localhost
DB_NAME=ecommerce
DB_USER=postgres
DB_PASSWORD=your_password
DB_PORT=5432

# RabbitMQ (required for Celery)
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
```

> ⚠️ `postgres://` URLs are automatically normalized to `postgresql://` for SQLAlchemy compatibility.

---

## 🚀 Getting Started

### 1. Clone & install dependencies
```bash
git clone <your-repo-url>
cd <project-folder>
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment
Set up your `.env` file as shown above.

### 3. Run database migrations
```bash
alembic upgrade head
```

### 4. Start the API server
```bash
uvicorn app.main:app --reload
```
API will be available at: `http://127.0.0.1:8000`
Interactive docs (Swagger UI): `http://127.0.0.1:8000/docs`

### 5. Start RabbitMQ
Make sure RabbitMQ is running locally (or update `RABBITMQ_HOST`/`RABBITMQ_PORT` for a remote broker):
```bash
# Example via Docker
docker run -d --hostname rabbitmq -p 5672:5672 rabbitmq:3-management
```

### 6. Start the Celery worker
```bash
celery -A app.redis.celery_app worker --loglevel=info
```

### 7. Start Celery Beat (for scheduled tasks)
```bash
celery -A app.redis.celery_app beat --loglevel=info
```

---

## 📬 Background Task Queues

| Queue                 | Tasks                                                                 |
|------------------------|------------------------------------------------------------------------|
| `email_queue`           | Order confirmation, shipment, cancellation/refund emails               |
| `notification_queue`    | New product alerts, price-drop alerts, abandoned cart reminders        |
| `analytics_queue`       | Low-stock inventory checks                                             |
| `dead_letter_queue`     | Captures failed/rejected messages from all queues above                |

**Scheduled jobs (Celery Beat):**
- `check_low_stock_inventory` — runs every 30 seconds *(intended for local testing — swap to a daily crontab in production)*
- `send_abandoned_cart_reminders` — runs daily at midnight

---

## 🔑 Authentication Flow

1. Register a user (`role`: `customer` or `seller`, defaults to `customer`).
2. Log in to receive a JWT access token (`Bearer` scheme).
3. Include the token in the `Authorization` header for protected routes:
   ```
   Authorization: Bearer <your_token>
   ```
4. Seller-only endpoints are protected via a `get_current_seller` dependency that checks `role == "seller"`.

---

## 🛡️ Security Notes

- Passwords are hashed using **bcrypt** before storage — plaintext passwords are never saved.
- JWT tokens are signed using `SECRET_KEY` and `ALGORITHM` from environment config — **never commit real secrets to version control**.
- CORS is currently configured to allow all origins (`*`) — restrict this in production.

---

## 📌 Roadmap Ideas

- Add refresh token support
- Add pagination & filtering on product/order listing endpoints
- Add automated tests (pytest)
- Containerize with Docker Compose (API + Postgres + RabbitMQ + Celery worker/beat)

---

## 📄 License

This project is open for personal or educational use. Add a formal license (e.g., MIT) if distributing publicly.
