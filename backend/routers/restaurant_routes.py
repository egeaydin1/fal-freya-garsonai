from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from core.database import get_db
from core.auth import get_current_restaurant
from models.models import Restaurant, Table, Order, OrderItem, OrderStatus
from websocket.manager import manager
import secrets

router = APIRouter(prefix="/api/restaurant", tags=["restaurant"])

class TableCreate(BaseModel):
    table_number: int

class TableResponse(BaseModel):
    id: int
    table_number: int
    qr_token: str
    is_active: bool
    
    class Config:
        from_attributes = True

class OrderItemResponse(BaseModel):
    id: int
    product_name: str
    quantity: int
    price: float
    
    class Config:
        from_attributes = True

class OrderResponse(BaseModel):
    id: int
    table_number: int
    status: str
    total_price: float
    items: List[dict]
    created_at: str
    
    class Config:
        from_attributes = True

@router.get("/tables", response_model=List[TableResponse])
def get_tables(
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    return restaurant.tables

@router.post("/tables", response_model=TableResponse)
def create_table(
    request: TableCreate,
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    # Check if table number exists
    existing = db.query(Table).filter(
        Table.restaurant_id == restaurant.id,
        Table.table_number == request.table_number
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Table number already exists")
    
    # Create table with unique QR token
    qr_token = secrets.token_urlsafe(16)
    
    table = Table(
        restaurant_id=restaurant.id,
        table_number=request.table_number,
        qr_token=qr_token
    )
    db.add(table)
    db.commit()
    db.refresh(table)
    
    return table

@router.delete("/tables/{table_id}")
def delete_table(
    table_id: int,
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    table = db.query(Table).filter(
        Table.id == table_id,
        Table.restaurant_id == restaurant.id
    ).first()
    
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    db.delete(table)
    db.commit()
    
    return {"success": True}

@router.get("/orders", response_model=List[OrderResponse])
def get_orders(
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    orders = db.query(Order).filter(
        Order.restaurant_id == restaurant.id
    ).order_by(Order.created_at.desc()).all()
    
    result = []
    for order in orders:
        result.append({
            "id": order.id,
            "table_number": order.table.table_number,
            "status": order.status.value,
            "total_price": order.total_price,
            "items": [
                {
                    "id": item.id,
                    "product_name": item.product.name,
                    "quantity": item.quantity,
                    "price": item.price
                }
                for item in order.items
            ],
            "created_at": order.created_at.isoformat()
        })
    
    return result

class OrderStatusUpdate(BaseModel):
    status: str

@router.patch("/orders/{order_id}/status")
async def update_order_status(
    order_id: int,
    request: OrderStatusUpdate,
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.restaurant_id == restaurant.id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Update status
    order.status = OrderStatus(request.status)
    db.commit()
    
    # Notify via WebSocket
    await manager.send_to_restaurant(restaurant.id, {
        "type": "order_update",
        "order_id": order.id,
        "status": order.status.value
    })
    
    await manager.send_to_table(order.table.qr_token, {
        "type": "order_status",
        "order_id": order.id,
        "status": order.status.value
    })
    
    return {"success": True}
