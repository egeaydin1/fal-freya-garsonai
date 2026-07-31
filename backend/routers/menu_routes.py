from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from core.database import get_db
from core.auth import get_current_restaurant
from models.models import Restaurant, Product, Table, Order, OrderItem

router = APIRouter(prefix="/api/menu", tags=["menu"])

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    category: Optional[str] = None
    image_url: Optional[str] = None

class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    category: Optional[str]
    image_url: Optional[str]
    is_available: bool
    
    class Config:
        from_attributes = True

# Restaurant endpoints (protected)
@router.get("/products", response_model=List[ProductResponse])
def get_products(
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    return restaurant.products

@router.post("/products", response_model=ProductResponse)
def create_product(
    request: ProductCreate,
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    product = Product(
        restaurant_id=restaurant.id,
        name=request.name,
        description=request.description,
        price=request.price,
        category=request.category,
        image_url=request.image_url
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return product

@router.patch("/products/{product_id}")
def update_product(
    product_id: int,
    request: ProductCreate,
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.restaurant_id == restaurant.id
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product.name = request.name
    product.description = request.description
    product.price = request.price
    product.category = request.category
    product.image_url = request.image_url
    db.commit()
    
    return product

@router.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.restaurant_id == restaurant.id
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    db.delete(product)
    db.commit()
    
    return {"success": True}

# Public endpoints (by QR token)
@router.get("/{qr_token}", response_model=List[ProductResponse])
def get_menu_by_token(qr_token: str, db: Session = Depends(get_db)):
    table = db.query(Table).filter(Table.qr_token == qr_token).first()
    
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    products = db.query(Product).filter(
        Product.restaurant_id == table.restaurant_id,
        Product.is_available == True
    ).all()
    
    return products

class CartItem(BaseModel):
    product_id: int
    quantity: int

class CheckoutRequest(BaseModel):
    items: List[CartItem]

@router.post("/{qr_token}/checkout")
def checkout(
    qr_token: str,
    request: CheckoutRequest,
    db: Session = Depends(get_db)
):
    table = db.query(Table).filter(Table.qr_token == qr_token).first()
    
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    # Create order
    order = Order(
        restaurant_id=table.restaurant_id,
        table_id=table.id,
        status="preparing"
    )
    db.add(order)
    db.flush()
    
    # Add items
    total = 0
    for item in request.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=item.quantity,
                price=product.price
            )
            db.add(order_item)
            total += product.price * item.quantity
    
    order.total_price = total
    db.commit()
    db.refresh(order)
    
    return {"order_id": order.id, "total": total}
