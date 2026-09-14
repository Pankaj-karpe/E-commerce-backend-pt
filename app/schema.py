from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional, List
from decimal import Decimal


######################### PRODUCTS #########################
class ProductBase(BaseModel):
    title: str
    description: Optional[str] = None
    price: Decimal
    stock: int


class prd_create(ProductBase):
    pass


class prd_out(prd_create):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class prd_update(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    stock: Optional[int] = None


######################### ORDER_ITEMS #########################
class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int


class OrderItemOut(BaseModel):
    id: int
    quantity: int
    created_at: datetime
    product: prd_out

    model_config = ConfigDict(from_attributes=True)


######################### ORDERS #########################
class OrderBase(BaseModel):
    total_amount: Decimal


class ord_create(BaseModel):
    items: List[OrderItemCreate]


class ord_out(ord_create):
    id: int
    total_amount: Decimal
    items: List[OrderItemOut]
    user: "UserResponse"
    status: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ord_update(BaseModel):
    status: Optional[str] = None
    total_amount: Optional[Decimal] = None
    items: Optional[List[OrderItemCreate]] = None

# Schema for status payload
class OrderStatusUpdate(BaseModel):
    status: str
    
######################### USER #########################
class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str
    role: str = "customer"


class UserResponse(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreateResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


######################### AUTH #########################
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    id: Optional[str] = None

ord_out.model_rebuild()