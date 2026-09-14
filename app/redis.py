from app.config import settings
from celery import Celery
from kombu import Exchange, Queue
from celery.schedules import crontab

# For RabbitMQ: "amqp://guest:guest@localhost:5672//"
# FIX: was `BROKEN_URL` (typo) — renamed to `BROKER_URL` for clarity.
# This was cosmetic only (the variable was just referenced below), but the
# name was misleading enough to read as a bug on first glance.
BROKER_URL = f"amqp://guest:guest@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}//"

# RPC result backend (stores results back in RabbitMQ transiently)
BACKEND_URL = "rpc://"

celery_app = Celery(
    "worker",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["app.tasks"]
)

# 1. Define Exchanges
default_exchange = Exchange("tasks", type="direct")
dlx_exchange = Exchange("dlx", type="direct")

# Arguments to automatically send failed/rejected messages to DLX
dlx_arguments = {
    "x-dead-letter-exchange": "dlx",
    "x-dead-letter-routing-key": "dead_letter",
}

# 2. Define Queues
celery_app.conf.task_queues = (
    #Pritoity Queues
    Queue("email_queue", default_exchange, routing_key="email", queue_arguments=dlx_arguments),
    Queue("notification_queue", default_exchange, routing_key="notification" , queue_arguments=dlx_arguments),
    Queue("analytics_queue", default_exchange, routing_key="analytics", queue_arguments=dlx_arguments),

    # Dead-Letter-Queue
    Queue("dead_letter_queue", dlx_exchange, routing_key="dead_letter"),
)

# 3. Route specific task functions to specific queues
celery_app.conf.task_routes = {
    #email_queue
    "app.tasks.send_order_confirmation_email": {"queue": "email_queue", "routing_key": "email"},
    "app.tasks.send_order_shipped_email": {"queue": "email_queue", "routing_key": "email"},
    "app.tasks.process_order_cancellation": {"queue": "email_queue", "routing_key": "email"},

    #notification_queue
    "app.tasks.notify_users_new_product": {"queue": "notification_queue", "routing_key": "notification"},
    "app.tasks.send_price_drop_alert": {"queue": "notification_queue", "routing_key": "notification"},
    "app.tasks.send_abandoned_cart_reminders": {"queue": "notification_queue", "routing_key": "notification"},

    #analytics_queue
    "app.tasks.check_low_stock_inventory": {"queue": "analytics_queue", "routing_key": "analytics"},
}

# Celery Beat Periodic Schedule Definition
celery_app.conf.beat_schedule = {
    # Runs low-stock check every 30 seconds for local testing (use crontab(hour=0, minute=0) for midnight)
    "check-low-stock-every-30-seconds": {
        "task": "app.tasks.check_low_stock_inventory",
        "schedule": 30.0,
    },

    # Runs daily at midnight to scan for 7-day-old pending orders
    "abandoned-cart-every-minute": {
        "task": "app.tasks.send_abandoned_cart_reminders",
        "schedule": crontab(hour=0, minute=0),
    },
}

celery_app.conf.update(task_track_started=True)
