from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from core.database import get_db
from core.auth import get_password_hash, verify_password, create_access_token
from models.models import Restaurant

router = APIRouter(prefix="/api/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    restaurant_id: int
    restaurant_name: str

@router.post("/register", response_model=TokenResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    # Check if email exists
    existing = db.query(Restaurant).filter(Restaurant.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create restaurant
    restaurant = Restaurant(
        name=request.name,
        email=request.email,
        hashed_password=get_password_hash(request.password)
    )
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)
    
    # Create token
    access_token = create_access_token({"sub": restaurant.id})
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        restaurant_id=restaurant.id,
        restaurant_name=restaurant.name
    )

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    # Find restaurant
    restaurant = db.query(Restaurant).filter(Restaurant.email == request.email).first()
    
    if not restaurant or not verify_password(request.password, restaurant.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Create token
    access_token = create_access_token({"sub": restaurant.id})
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        restaurant_id=restaurant.id,
        restaurant_name=restaurant.name
    )
