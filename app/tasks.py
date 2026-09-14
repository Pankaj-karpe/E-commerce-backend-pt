from app.redis import celery_app
from app.database import SessionLocal
from app import models
from datetime import datetime, timedelta, timezone
 
@celery_app.task
def send_order_confirmation_email(user_email: str, order_id: int):
    #Asynchronous email or background logic
    """Triggered right after checkout"""
    print(f"✉️ [EMAIL_QUEUE] Sent receipt for Order #{order_id} to email {user_email}")
    return True
 
@celery_app.task()
def process_order_shipped_email(user_email: str, order_id: int):
    """ Triggered when seller updates order status to SHIPPED"""
    print(f"🚚 [EMAIL_QUEUE] Sent dispatch notification for Order #{order_id} to email {user_email}")
    return True
 
@celery_app.task(bind=True, max_retries=3)
def process_order_cancellation(self, user_email: str, order_id: int):
    """Triggered on order cancel: Restores product stock and notifies buyer"""
    db = SessionLocal()
    try:
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            print(f"❌ Order #{order_id} not found.")
            return False
 
        # 1. Restore product stock in DB
        for item in order.items:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
            if product:
                product.stock += item.quantity
        db.commit()
 
        # 2. Notify buyer
        print(f"🔄 [EMAIL_QUEUE] Stock restored & refund confirmation sent for Order #{order_id} to {user_email}")
        return True
 
    except Exception as e:
        db.rollback()
        # FIX: Celery's Task.retry() expects the exception via `exc=`, not `e=`.
        # The original `self.retry(e=e, countdown=10)` raised a TypeError instead
        # of scheduling a retry, so failures were never actually retried.
        raise self.retry(exc=e, countdown=10)
    finally:
        db.close()
 
@celery_app.task
def notify_users_new_product(product_title: str, price: float):
    """Broadcasting alert when a new product is added"""
    print(f"📢 [NOTIFICATION_QUEUE] Broadcast: New item {product_title} listed at ₹{price}!")
    return True
 
@celery_app.task
def send_price_drop_alert(product_title: str, old_price: float, new_price: float):
    """Alerting users on price reductions"""
    print(f"📢 [NOTIFICATION_QUEUE] Alert: '{product_title}' price dropped from ${old_price} to ${new_price}!")
    return True
 
@celery_app.task
def check_low_stock_inventory():
    """Scans DB for low stock items (stock < 5) and alerts sellers"""
    db = SessionLocal()
    try:
        low_stock_inventory = db.query(models.Product).filter(models.Product.stock < 5).all()
        if not low_stock_inventory:
            print("📦 [ADMIN_QUEUE] All products stock levels are healthy.")
            return True
 
        print(f"⚠️ [ADMIN_QUEUE] Found {len(low_stock_inventory)} low stock products: ")
        for product in low_stock_inventory:
            print(f"  - '{product.title}' (ID: {product.id}) -> Only {product.stock} units.")
        # FIX: `return True` was previously indented inside the loop body, so the
        # function returned after printing only the FIRST low-stock product.
        # It's now outside the loop so every product gets reported.
        return True
    finally:
        db.close()
 
@celery_app.task
def send_abandoned_cart_reminders():
    """Identifies pending orders older than 1 week and notifies users"""
    db = SessionLocal()
    try:
        # Calculate cut-off timestamp (7 days ago from UTC now)
        one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
 
        # Query pending orders created before the 7-day threshold
        abandoned_orders = db.query(models.Order).filter(models.Order.status == "pending⏳", models.Order.created_at <= one_week_ago).all()
        if not abandoned_orders:
            print("🛒 [NOTIFICATION_QUEUE] No abandoned pending orders older than 7 days found.")
            return True
        
        for order in abandoned_orders:
            # Query user email dynamically via existing ORM relationship
            user_email = order.user.email if order.user else "Unknown"
            print(f"   - Order #{order.id} (Placed on {order.created_at.strftime('%Y-%m-%d')}) -> Sent reminder to {user_email}")
 
        return True
    except Exception as e:
        print(f"❌ Failed to process abandoned carts: {e}")
        return False
    finally:
        db.close()
 
