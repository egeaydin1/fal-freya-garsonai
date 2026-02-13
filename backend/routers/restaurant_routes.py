from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from core.database import get_db
from core.auth import get_current_restaurant
from models.models import Restaurant, Table, Order, OrderItem, OrderStatus
from websocket.manager import manager
from datetime import datetime, date
from sqlalchemy import func
import secrets

router = APIRouter(prefix="/api/restaurant", tags=["restaurant"])

class TableCreate(BaseModel):
    table_number: int

class TableResponse(BaseModel):
    id: int
    table_number: int
    qr_token: str
    is_active: bool
    check_requested: bool
    check_requested_at: Optional[str] = None
    current_total: float = 0.0
    active_orders_count: int = 0
    
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
    tables_data = []
    for table in restaurant.tables:
        # Calculate current total from active orders (not paid)
        active_orders = db.query(Order).filter(
            Order.table_id == table.id,
            Order.status != OrderStatus.paid
        ).all()
        
        current_total = sum(order.total_price for order in active_orders)
        active_orders_count = len(active_orders)
        
        tables_data.append({
            "id": table.id,
            "table_number": table.table_number,
            "qr_token": table.qr_token,
            "is_active": table.is_active,
            "check_requested": table.check_requested,
            "check_requested_at": table.check_requested_at.isoformat() if table.check_requested_at else None,
            "current_total": current_total,
            "active_orders_count": active_orders_count
        })
    
    return tables_data

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
@router.post("/orders/{order_id}/paid")
async def mark_order_paid(
    order_id: int,
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    """Mark order as paid and clear table"""
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.restaurant_id == restaurant.id
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Update order status to paid
    order.status = OrderStatus.paid
    
    # Clear table check request
    table = order.table
    table.check_requested = False
    table.check_requested_at = None
    
    db.commit()
    
    # Notify via WebSocket
    await manager.send_to_restaurant(restaurant.id, {
        "type": "order_paid",
        "order_id": order.id,
        "table_number": table.table_number
    })
    
    await manager.send_to_table(table.qr_token, {
        "type": "payment_completed",
        "message": "Ödemeniz alındı. Teşekkür ederiz!"
    })
    
    return {"success": True}

@router.post("/tables/{table_id}/pay-all")
async def pay_all_table_orders(
    table_id: int,
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    """Mark all active orders for a table as paid"""
    table = db.query(Table).filter(
        Table.id == table_id,
        Table.restaurant_id == restaurant.id
    ).first()
    
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    active_orders = db.query(Order).filter(
        Order.table_id == table.id,
        Order.status != OrderStatus.paid
    ).all()
    
    if not active_orders:
        raise HTTPException(status_code=400, detail="No active orders for this table")
    
    total_paid = 0.0
    for order in active_orders:
        order.status = OrderStatus.paid
        total_paid += order.total_price
    
    table.check_requested = False
    table.check_requested_at = None
    db.commit()
    
    await manager.send_to_restaurant(restaurant.id, {
        "type": "table_paid",
        "table_id": table.id,
        "table_number": table.table_number,
        "total_paid": total_paid
    })
    
    await manager.send_to_table(table.qr_token, {
        "type": "payment_completed",
        "message": "Ödemeniz alındı. Teşekkür ederiz!"
    })
    
    return {"success": True, "total_paid": total_paid, "orders_count": len(active_orders)}

@router.get("/revenue/daily")
def get_daily_revenue(
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    """Get today's revenue statistics"""
    today = date.today()
    
    # Get all paid orders from today
    daily_orders = db.query(Order).filter(
        Order.restaurant_id == restaurant.id,
        Order.status == OrderStatus.paid,
        func.date(Order.updated_at) == today
    ).all()
    
    total_revenue = sum(order.total_price for order in daily_orders)
    total_orders = len(daily_orders)
    
    return {
        "date": today.isoformat(),
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "average_order": total_revenue / total_orders if total_orders > 0 else 0
    }