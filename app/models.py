from .database import Base
from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, ForeignKey, Numeric
from sqlalchemy.orm import relationship



class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String)
    role = Column(String, default="customer")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    orders = relationship("Order", back_populates="user")
    

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(String)
    price = Column(Numeric, nullable=False)
    stock = Column(Integer)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False, default="pending⏳")
    total_amount = Column(Numeric, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="orders")
    items = relationship("Order_item", back_populates="order", cascade="all, delete-orphan")
    
class Order_item(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product")