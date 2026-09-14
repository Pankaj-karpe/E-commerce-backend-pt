from typing import List, Optional
from decimal import Decimal
from fastapi import status, HTTPException, Depends, APIRouter, Response, Query
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schema, oauth2
from app.tasks import send_order_confirmation_email, process_order_cancellation, process_order_shipped_email

router = APIRouter(
    prefix="/orders",
    tags=["orders"]
)

# GET ALL ORDERS (User gets their own orders; admin/seller gets all)
@router.get("/", response_model=List[schema.ord_out])
async def list_all_orders(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Max records to return"),
    user_id: Optional[int] = Query(None, description="Admin/Seller filter by specific User ID")
):
    query = db.query(models.Order)

    if current_user.role in ["admin", "seller"]:
        if user_id:
            query = query.filter(models.Order.user_id == user_id)
        else:
            query = query.filter(models.Order.user_id == current_user.id)

    orders = query.offset(skip).limit(limit).all()

    return orders


# CREATE ORDER
@router.post("/", response_model=schema.ord_out, status_code=status.HTTP_201_CREATED)
async def create_ord(
    ord: schema.ord_create, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    calculated_total = Decimal("0.00")
    items_to_create = []

    try:
        # 1. Create main Order record tied to authenticated user && check stock && total amount
        for item in ord.items:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()

            # Check product existence
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, 
                    detail=f"Product with id {item.product_id} not found"
                )
            
            # Check stock availability
            if product.stock < item.quantity:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Product '{product.title}' is out of stock or has insufficient quantity (Availabel stock: {product.stock})")

            # Decrement product stock in database session
            product.stock -= item.quantity
            
            # Calculate subtotal: price * quantity
            calculated_total += Decimal(str(product.price)) * item.quantity
            items_to_create.append(item)

        # 2. Create Order with backend-calculated total_amount
        new_ord = models.Order(
            user_id = current_user.id,
            total_amount = calculated_total
        )
        db.add(new_ord)
        db.commit()
        db.refresh(new_ord)

        # 3. Add each line item linked to new_ord.id
        for item in items_to_create:
            new_item = models.Order_item(
                order_id=new_ord.id,
                product_id=item.product_id,
                quantity=item.quantity
            )
            db.add(new_item)

        db.commit()
        db.refresh(new_ord, attribute_names=["user", "items"])
        
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Order processing failed due to a database error.")

    send_order_confirmation_email.delay(current_user.email, new_ord.id)
    return new_ord

# READ ONE ORDER
@router.get("/{id}", response_model=schema.ord_out)
async def get_one_ord(
    id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    ord = db.query(models.Order).filter(models.Order.id == id).first()

    if not ord:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Order with id {id} not found")

    if ord.user_id != current_user.id and current_user.role not in ["admin", "seller"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this order")

    return ord


# UPDATE ORDER
@router.put("/{id}", response_model=schema.ord_out)
async def update_ord(
    id: int, 
    ord: schema.ord_update, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    exist_ord = db.query(models.Order).filter(models.Order.id == id).first()

    if not exist_ord:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Order with id {id} not found")

    if exist_ord.user_id != current_user.id and current_user.role not in ["admin", "seller"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this order")

    # Extract non-relational fields and update Order
    update_data = ord.model_dump(exclude_unset=True)
    items_data = update_data.pop("items", None)

    try:
        for key, value in update_data.items():
            setattr(exist_ord, key, value)

        # Replace child items if new items array is provided
        if items_data is not None:
            db.query(models.Order_item).filter(models.Order_item.order_id == id).delete()
            for item in items_data:
                new_item = models.Order_item(
                    order_id=id,
                    product_id=item["product_id"],
                    quantity=item["quantity"]
                )
                db.add(new_item)
        
        db.commit()
        db.refresh(exist_ord)
            
        return exist_ord
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update order.")


### Update Order Status & Trigger Tasks
@router.patch("/{id}/status", response_model=schema.ord_out)
async def update_order_status(
    id: int,
    status: schema.OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    exist_ord = db.query(models.Order).filter(models.Order.id == id).first()
    if not exist_ord:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Order with id {id} not found")

    if exist_ord.user_id != current_user.id and current_user.role not in ["admin", "seller"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this order")

    # Update status in DB
    new_status = status.status
    exist_ord.status = new_status
    db.commit()
    db.refresh(exist_ord, attribute_names=["user", "items"])

    # Dispatch Celery background tasks based on updated status
    if new_status.upper() == "SHIPPED":
        process_order_shipped_email.delay(current_user.email, exist_ord.id)
    elif new_status.upper() == "CANCELLED":
        process_order_cancellation.delay(current_user.email, exist_ord.id)

    return exist_ord
    

# DELETE ORDER
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ord(
    id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    ord_query = db.query(models.Order).filter(models.Order.id == id)
    exist_ord = ord_query.first()
    
    if not exist_ord:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Order with id {id} not found")

    if exist_ord.user_id != current_user.id and current_user.role not in ["admin", "seller"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this order")

    try:
        # Restore product inventory stock before deleting order
        for item in exist_ord.items:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
            if product:
                product.stock += item.quantiy
        db.delete(exist_ord)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to cancel and delete order.")