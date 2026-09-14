from typing import List
from fastapi import FastAPI, Response, status, HTTPException, Depends, APIRouter
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schema, utils, oauth2

router = APIRouter(
    prefix="/users",
    tags=['users_docs']
)

# GET ALL USERS
@router.get("/", response_model=List[schema.UserResponse])
async def list_all_users(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    return users

# CRUD Operations:

# 1. C - Creating a user (Generates JWT on registration)
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schema.UserCreateResponse)
def create_user(user: schema.UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email {user.email} already exists"
        )

    # Hash the password
    hashed_pwd = utils.hash(user.password)

    # Store hashed password in database
    new_user = models.User(
        email=user.email,
        password=hashed_pwd,
        role=user.role
    )
    try: 
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to register user due to a database error.")

    # Create access token
    access_token = oauth2.create_access_token(data={"user_id": new_user.id})
                                               
    return {
        "user": new_user, 
        "access_token": access_token,
        "token_type": "bearer"
    }

# 2. R - Reading a user by ID
@router.get("/{id}", response_model=schema.UserResponse)
def get_user(id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {id} was not found"
        )

    return user