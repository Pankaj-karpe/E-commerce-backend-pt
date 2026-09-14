from typing import List, Optional
from fastapi import Response, status, HTTPException, Depends, APIRouter, Query
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schema, oauth2
from app.tasks import send_price_drop_alert, notify_users_new_product


router = APIRouter(
    prefix="/products",
    tags=["products"]
)


# GET ALL PRODUCTS (Public Access)
@router.get("/", response_model=List[schema.prd_out])
async def list_all_products(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Max records to return"),
    search: Optional[str] = Query(None, description="Seach product titles"),
    min_price: Optional[float] = Query(None, ge=0,description="Filter by minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Filter by maximum price")
):
    query = db.query(models.Product)
    if search:
        query.query.filter(models.Product.title.ilike(f"%{search}"))
    if min_price is not None:
        query.query.filter(models.Product.price >= min_price)
    if max_price is not None:
        query.query.filter(models.Product.price <= max_price)

    products = db.query(models.Product).all()
    return products


# READ ONE PRODUCT (Public Access)
@router.get("/{id}", response_model=schema.prd_out)
async def get_one_prd(id: int, db: Session = Depends(get_db)):
    prd = db.query(models.Product).filter(models.Product.id == id).first()

    if not prd:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with id {id} not found")

    return prd


# CREATE PRODUCT (Requires Seller Role)
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=List[schema.prd_out])
async def create_prd(
    prds: List[schema.prd_create], 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(oauth2.get_current_seller)
):
    new_prd = [models.Product(**prd.model_dump()) for prd in prds]

    try:
        db.add_all(new_prd)
        db.commit()
        for prd in new_prd:
            db.refresh(prd)
            notify_users_new_product.delay(prd.title, float(prd.price))
        return new_prd
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to insert products due to a database error.")


# UPDATE PRODUCT (Requires Seller Role)
@router.put("/{id}", response_model=schema.prd_out)
async def update_prd(
    id: int, 
    prd: schema.prd_update, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(oauth2.get_current_seller)
):
    exist_prd = db.query(models.Product).filter(models.Product.id == id).first()

    if not exist_prd:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with id {id} not found")

    # 1. Capture original price as float before modifying model
    old_price = float(exist_prd.price)

    try:
        # 2. Extract input payload and apply update to existing ORM instance
        update_data = prd.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(exist_prd, key, value)

        db.commit()
        db.refresh(exist_prd)

        # 3. Check for price reduction and trigger notification task
        new_price = float(exist_prd.price)
        try: 
            if new_price < old_price:
                send_price_drop_alert.delay(exist_prd.title, float(old_price), float(exist_prd.price))
        except Exception as e:
            print(f"⚠️ Celery broker unreachable: {e}")
            
        return exist_prd
    
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update product.")


# DELETE PRODUCT (Requires Seller Role)
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prd(
    id: int, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(oauth2.get_current_seller)
):
    prd_query = db.query(models.Product).filter(models.Product.id == id)
    exist_prd = prd_query.first()
    
    if not exist_prd:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product with id {id} not found")
    try:
        prd_query.delete(synchronize_session=False)
        db.commit()
        
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete product.")
