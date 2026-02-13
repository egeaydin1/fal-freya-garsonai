from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import List, Optional
from core.database import get_db
from core.auth import get_current_restaurant
from models.models import Restaurant, Product, Table, Order, OrderItem, OrderStatus, Allergen, product_allergens
from websocket.manager import manager
from datetime import datetime
import os, uuid, shutil

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

router = APIRouter(prefix="/api/menu", tags=["menu"])

# ── Allergen Schemas ──

class AllergenCreate(BaseModel):
    name: str
    icon: Optional[str] = None

class AllergenResponse(BaseModel):
    id: int
    name: str
    icon: Optional[str]
    
    class Config:
        from_attributes = True

# ── Allergen CRUD ──

@router.get("/allergens", response_model=List[AllergenResponse])
def get_allergens(
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    return db.query(Allergen).filter(Allergen.restaurant_id == restaurant.id).all()

@router.post("/allergens", response_model=AllergenResponse)
def create_allergen(
    request: AllergenCreate,
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    allergen = Allergen(
        restaurant_id=restaurant.id,
        name=request.name,
        icon=request.icon
    )
    db.add(allergen)
    db.commit()
    db.refresh(allergen)
    return allergen

@router.delete("/allergens/{allergen_id}")
def delete_allergen(
    allergen_id: int,
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    allergen = db.query(Allergen).filter(
        Allergen.id == allergen_id,
        Allergen.restaurant_id == restaurant.id
    ).first()
    if not allergen:
        raise HTTPException(status_code=404, detail="Allergen not found")
    db.delete(allergen)
    db.commit()
    return {"success": True}

# ── Image Upload ──

@router.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    restaurant: Restaurant = Depends(get_current_restaurant),
):
    # Validate file type
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Invalid image type")
    
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"image_url": f"/uploads/{filename}"}

# ── Product Schemas ──

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    category: Optional[str] = None
    image_url: Optional[str] = None
    allergen_ids: Optional[List[int]] = []

class ProductResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    price: float
    category: Optional[str]
    image_url: Optional[str]
    is_available: bool
    allergens: List[AllergenResponse] = []
    
    class Config:
        from_attributes = True

# Restaurant endpoints (protected)
@router.get("/products", response_model=List[ProductResponse])
def get_products(
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    products = db.query(Product).options(
        joinedload(Product.allergens)
    ).filter(Product.restaurant_id == restaurant.id).all()
    return products

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
    
    # Attach allergens
    if request.allergen_ids:
        allergens = db.query(Allergen).filter(
            Allergen.id.in_(request.allergen_ids),
            Allergen.restaurant_id == restaurant.id
        ).all()
        product.allergens = allergens
    
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return product

@router.patch("/products/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    request: ProductCreate,
    restaurant: Restaurant = Depends(get_current_restaurant),
    db: Session = Depends(get_db)
):
    product = db.query(Product).options(
        joinedload(Product.allergens)
    ).filter(
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
    
    # Update allergens
    if request.allergen_ids is not None:
        allergens = db.query(Allergen).filter(
            Allergen.id.in_(request.allergen_ids),
            Allergen.restaurant_id == restaurant.id
        ).all()
        product.allergens = allergens
    
    db.commit()
    db.refresh(product)
    
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
    
    products = db.query(Product).options(
        joinedload(Product.allergens)
    ).filter(
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
async def checkout(
    qr_token: str,
    request: CheckoutRequest,
    db: Session = Depends(get_db)
):
    table = db.query(Table).filter(Table.qr_token == qr_token).first()
    
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    if not request.items:
        raise HTTPException(status_code=400, detail="Cart is empty")
    
    # Create order
    order = Order(
        restaurant_id=table.restaurant_id,
        table_id=table.id,
        status=OrderStatus.preparing
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
    
    # Notify restaurant via WebSocket
    await manager.send_to_restaurant(table.restaurant_id, {
        "type": "new_order",
        "order_id": order.id,
        "table_number": table.table_number,
        "total_price": total
    })
    
    return {
        "success": True,
        "order_id": order.id,
        "total": total,
        "message": "Siparişiniz alındı!"
    }

@router.post("/{qr_token}/request-check")
async def request_check(
    qr_token: str,
    db: Session = Depends(get_db)
):
    """Customer requests the check for their table"""
    table = db.query(Table).filter(Table.qr_token == qr_token).first()
    
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    # Mark table as requesting check
    table.check_requested = True
    table.check_requested_at = datetime.utcnow()
    db.commit()
    
    # Notify restaurant via WebSocket
    await manager.send_to_restaurant(table.restaurant_id, {
        "type": "check_requested",
        "table_number": table.table_number,
        "table_id": table.id
    })
    
    return {
        "success": True,
        "message": "Hesap isteğiniz iletildi!"
    }
