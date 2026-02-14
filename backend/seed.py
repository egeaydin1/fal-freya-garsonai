"""
Demo seed script — creates a demo restaurant with tables and a full Turkish menu.
Runs once on first startup; skips if the demo restaurant already exists.
"""
import os
import sys
import time
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Wait for DB to be ready
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@database:5432/garsonai")

def wait_for_db(max_retries=30, delay=2):
    """Wait until Postgres is accepting connections."""
    for attempt in range(max_retries):
        try:
            engine = create_engine(DATABASE_URL)
            conn = engine.connect()
            conn.close()
            print(f"✅ Database ready (attempt {attempt + 1})")
            return engine
        except Exception as e:
            print(f"⏳ Waiting for database... ({attempt + 1}/{max_retries})")
            time.sleep(delay)
    print("❌ Could not connect to database")
    sys.exit(1)

def seed():
    engine = wait_for_db()

    # Import models AFTER engine is ready so Base.metadata is populated
    from core.database import Base
    from models.models import Restaurant, Table, Product, Allergen, product_allergens
    from core.auth import get_password_hash

    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    Session = sessionmaker(bind=engine)
    db = Session()

    # Check if demo already exists
    existing = db.query(Restaurant).filter(Restaurant.email == "demo@garsonai.com").first()
    if existing:
        print("ℹ️  Demo restaurant already exists, skipping seed.")
        db.close()
        return

    print("🌱 Seeding demo restaurant...")

    # 1) Create restaurant
    restaurant = Restaurant(
        name="Demo Restoran",
        email="demo@garsonai.com",
        hashed_password=get_password_hash("demo1234"),
    )
    db.add(restaurant)
    db.flush()  # get restaurant.id

    # 2) Create tables (5 tables)
    for i in range(1, 6):
        table = Table(
            restaurant_id=restaurant.id,
            table_number=i,
            qr_token=uuid.uuid4().hex,
            is_active=True,
        )
        db.add(table)

    # 3) Create allergens
    allergen_data = [
        ("Gluten", "🌾"),
        ("Süt", "🥛"),
        ("Yumurta", "🥚"),
        ("Fıstık", "🥜"),
        ("Balık", "🐟"),
        ("Soya", "🫘"),
    ]
    allergen_map = {}
    for name, icon in allergen_data:
        a = Allergen(restaurant_id=restaurant.id, name=name, icon=icon)
        db.add(a)
        db.flush()
        allergen_map[name] = a

    # 4) Create menu products
    products = [
        # --- Başlangıçlar ---
        {
            "name": "Mercimek Çorbası",
            "description": "Geleneksel Türk mercimek çorbası, limon ve ekmek ile servis edilir",
            "price": 85.0,
            "category": "Başlangıçlar",
            "image_url": "https://images.unsplash.com/photo-1547592166-23ac45744acd?w=400",
            "allergens": ["Gluten"],
        },
        {
            "name": "Humus",
            "description": "Nohut ezmesi, tahin, zeytinyağı ve baharatlarla",
            "price": 75.0,
            "category": "Başlangıçlar",
            "image_url": "https://images.unsplash.com/photo-1637361973-2b03c0a8e3ab?w=400",
            "allergens": [],
        },
        {
            "name": "Sigara Böreği",
            "description": "Çıtır yufka içinde beyaz peynir, maydanoz",
            "price": 95.0,
            "category": "Başlangıçlar",
            "image_url": "https://images.unsplash.com/photo-1519864600857-090ed02a7ca4?w=400",
            "allergens": ["Gluten", "Süt", "Yumurta"],
        },
        {
            "name": "Yaprak Sarma",
            "description": "Zeytinyağlı asma yaprağı sarması, pirinç ve baharatlarla",
            "price": 90.0,
            "category": "Başlangıçlar",
            "image_url": "https://images.unsplash.com/photo-1625944525533-473f1a3d54e7?w=400",
            "allergens": [],
        },
        # --- Ana Yemekler ---
        {
            "name": "Adana Kebap",
            "description": "Acılı kıyma kebap, lavaş ekmek, közlenmiş biber ve domates ile",
            "price": 220.0,
            "category": "Ana Yemekler",
            "image_url": "https://images.unsplash.com/photo-1603360946369-dc9bb6258143?w=400",
            "allergens": ["Gluten"],
        },
        {
            "name": "Tavuk Şiş",
            "description": "Marine edilmiş tavuk göğsü şiş, pilav ve salata ile",
            "price": 190.0,
            "category": "Ana Yemekler",
            "image_url": "https://images.unsplash.com/photo-1610057099431-d73a1c9d2f2f?w=400",
            "allergens": [],
        },
        {
            "name": "Karışık Izgara",
            "description": "Kuzu pirzola, köfte, tavuk kanat — ızgara tabağı",
            "price": 320.0,
            "category": "Ana Yemekler",
            "image_url": "https://images.unsplash.com/photo-1544025162-d76694265947?w=400",
            "allergens": [],
        },
        {
            "name": "İskender Kebap",
            "description": "İnce döner dilimler, domates sosu, yoğurt ve tereyağı ile",
            "price": 250.0,
            "category": "Ana Yemekler",
            "image_url": "https://images.unsplash.com/photo-1599487488170-d11ec9c172f0?w=400",
            "allergens": ["Gluten", "Süt"],
        },
        {
            "name": "Levrek Izgara",
            "description": "Taze levrek, limon ve roka salata ile",
            "price": 280.0,
            "category": "Ana Yemekler",
            "image_url": "https://images.unsplash.com/photo-1534604973900-c43ab4c2e0ab?w=400",
            "allergens": ["Balık"],
        },
        {
            "name": "Köfte",
            "description": "Izgara köfte, patates kızartması ve salata ile servis",
            "price": 185.0,
            "category": "Ana Yemekler",
            "image_url": "https://images.unsplash.com/photo-1529042410759-befb1204b468?w=400",
            "allergens": ["Gluten", "Yumurta"],
        },
        # --- Salatalar ---
        {
            "name": "Çoban Salata",
            "description": "Domates, salatalık, biber, soğan, maydanoz, zeytinyağı",
            "price": 65.0,
            "category": "Salatalar",
            "image_url": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=400",
            "allergens": [],
        },
        {
            "name": "Sezar Salata",
            "description": "Marul, kruton, parmesan, tavuk ve sezar sos",
            "price": 120.0,
            "category": "Salatalar",
            "image_url": "https://images.unsplash.com/photo-1550304943-4f24f54ddde9?w=400",
            "allergens": ["Gluten", "Süt", "Yumurta"],
        },
        # --- İçecekler ---
        {
            "name": "Ayran",
            "description": "Geleneksel Türk yoğurt içeceği",
            "price": 30.0,
            "category": "İçecekler",
            "image_url": "https://images.unsplash.com/photo-1625865797235-1bf09048c825?w=400",
            "allergens": ["Süt"],
        },
        {
            "name": "Türk Çayı",
            "description": "Demlik çay, ince belli bardakta",
            "price": 25.0,
            "category": "İçecekler",
            "image_url": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?w=400",
            "allergens": [],
        },
        {
            "name": "Türk Kahvesi",
            "description": "Geleneksel Türk kahvesi, lokum ile",
            "price": 45.0,
            "category": "İçecekler",
            "image_url": "https://images.unsplash.com/photo-1544787219-7f47ccb76574?w=400",
            "allergens": [],
        },
        {
            "name": "Taze Portakal Suyu",
            "description": "Sıkma portakal suyu",
            "price": 50.0,
            "category": "İçecekler",
            "image_url": "https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?w=400",
            "allergens": [],
        },
        {
            "name": "Kola",
            "description": "330 ml kutu",
            "price": 35.0,
            "category": "İçecekler",
            "image_url": "https://images.unsplash.com/photo-1629203851122-3726ecdf080e?w=400",
            "allergens": [],
        },
        # --- Tatlılar ---
        {
            "name": "Künefe",
            "description": "Sıcak kadayıf tatlısı, peynir dolgulu, şerbetli",
            "price": 130.0,
            "category": "Tatlılar",
            "image_url": "https://images.unsplash.com/photo-1598110750624-207050c4f28c?w=400",
            "allergens": ["Gluten", "Süt"],
        },
        {
            "name": "Baklava",
            "description": "Antep fıstıklı baklava, 4 dilim",
            "price": 140.0,
            "category": "Tatlılar",
            "image_url": "https://images.unsplash.com/photo-1519676867240-f03562e64548?w=400",
            "allergens": ["Gluten", "Fıstık"],
        },
        {
            "name": "Sütlaç",
            "description": "Fırında sütlaç, tarçın ile",
            "price": 85.0,
            "category": "Tatlılar",
            "image_url": "https://images.unsplash.com/photo-1488477181946-6428a0291777?w=400",
            "allergens": ["Süt"],
        },
    ]

    for prod_data in products:
        allergen_names = prod_data.pop("allergens")
        product = Product(
            restaurant_id=restaurant.id,
            is_available=True,
            **prod_data,
        )
        db.add(product)
        db.flush()

        # Attach allergens
        for aname in allergen_names:
            if aname in allergen_map:
                product.allergens.append(allergen_map[aname])

    db.commit()
    db.close()

    print("✅ Demo seed complete!")
    print("   📧 Email:    demo@garsonai.com")
    print("   🔑 Password: demo1234")
    print(f"   🍽️  {len(products)} menu items across 5 categories")
    print(f"   🪑 5 tables created")


if __name__ == "__main__":
    seed()
