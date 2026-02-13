"""
Seed script: Creates a proper Turkish restaurant menu with allergens.
Run: python seed.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.database import SessionLocal, engine, Base
from models.models import Product, Allergen, product_allergens, Restaurant

# Create tables if not exists
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    # Get restaurant
    restaurant = db.query(Restaurant).first()
    if not restaurant:
        print("❌ No restaurant found. Register first via /api/auth/register")
        sys.exit(1)

    rid = restaurant.id
    print(f"🏪 Restaurant: {restaurant.name} (ID: {rid})")

    # ── Clear existing products & allergens ──
    db.execute(product_allergens.delete())
    db.query(Product).filter(Product.restaurant_id == rid).delete()
    db.query(Allergen).filter(Allergen.restaurant_id == rid).delete()
    db.commit()
    print("🗑️  Cleared old products & allergens")

    # ── Create Allergens ──
    allergen_data = [
        ("Gluten", "🌾"),
        ("Süt/Laktoz", "🥛"),
        ("Yumurta", "🥚"),
        ("Fıstık", "🥜"),
        ("Soya", "🫘"),
        ("Deniz Ürünleri", "🦐"),
        ("Susam", "⚪"),
    ]
    allergens = {}
    for name, icon in allergen_data:
        a = Allergen(restaurant_id=rid, name=name, icon=icon)
        db.add(a)
        db.flush()
        allergens[name] = a
        print(f"  ✅ Allergen: {icon} {name} (ID: {a.id})")

    # ── Create Menu Products ──
    menu_items = [
        # ── Ana Yemekler ──
        {
            "name": "Izgara Köfte",
            "description": "El yapımı dana köfte, közlenmiş biber ve domates ile servis edilir. Yanında pilav ve yeşillik.",
            "price": 185.0,
            "category": "Ana Yemek",
            "allergens": ["Gluten", "Yumurta"],
        },
        {
            "name": "Tavuk Şiş",
            "description": "Marine edilmiş tavuk göğsü, meşe kömüründe pişirilir. Yanında bulgur pilavı ve mevsim salata.",
            "price": 165.0,
            "category": "Ana Yemek",
            "allergens": [],
        },
        {
            "name": "Adana Kebap",
            "description": "Acılı el kıyması, şişte közlenmiş. Lavaş, soğan ve közlenmiş domates ile.",
            "price": 195.0,
            "category": "Ana Yemek",
            "allergens": ["Gluten"],
        },
        {
            "name": "Levrek Izgara",
            "description": "Taze Ege levreği, zeytinyağı ve limon ile hafif ızgara. Roka salatası eşliğinde.",
            "price": 245.0,
            "category": "Ana Yemek",
            "allergens": ["Deniz Ürünleri"],
        },
        {
            "name": "Mantı",
            "description": "El açması Kayseri mantısı, yoğurt ve kızgın tereyağlı sos ile. Sumak ve pul biber eşliğinde.",
            "price": 145.0,
            "category": "Ana Yemek",
            "allergens": ["Gluten", "Süt/Laktoz", "Yumurta"],
        },
        # ── Başlangıçlar ──
        {
            "name": "Mercimek Çorbası",
            "description": "Geleneksel kırmızı mercimek çorbası, limon ve kruton ile servis edilir.",
            "price": 65.0,
            "category": "Başlangıç",
            "allergens": ["Gluten"],
        },
        {
            "name": "Humus Tabağı",
            "description": "Tahin, limon suyu ve zeytinyağı ile hazırlanan nohut ezmesi. Pide eşliğinde.",
            "price": 75.0,
            "category": "Başlangıç",
            "allergens": ["Susam", "Gluten"],
        },
        {
            "name": "Sigara Böreği",
            "description": "Çıtır yufka içinde beyaz peynir ve maydanoz. 4 adet.",
            "price": 85.0,
            "category": "Başlangıç",
            "allergens": ["Gluten", "Süt/Laktoz", "Yumurta"],
        },
        {
            "name": "Karides Güveç",
            "description": "Tereyağında sote karides, domates sos, kaşar peyniri ile fırınlanmış.",
            "price": 155.0,
            "category": "Başlangıç",
            "allergens": ["Deniz Ürünleri", "Süt/Laktoz"],
        },
        # ── Salatalar ──
        {
            "name": "Çoban Salata",
            "description": "Domates, salatalık, biber, soğan, maydanoz. Zeytinyağı ve limon sosu.",
            "price": 55.0,
            "category": "Salata",
            "allergens": [],
        },
        {
            "name": "Sezar Salata",
            "description": "Marul, tavuk, parmesan, kruton ve sezar sos ile.",
            "price": 95.0,
            "category": "Salata",
            "allergens": ["Gluten", "Süt/Laktoz", "Yumurta"],
        },
        # ── Tatlılar ──
        {
            "name": "Künefe",
            "description": "Hatay usulü, tel kadayıf arasında özel peynir. Antep fıstığı ve şerbet ile.",
            "price": 115.0,
            "category": "Tatlı",
            "allergens": ["Gluten", "Süt/Laktoz", "Fıstık"],
        },
        {
            "name": "Sütlaç",
            "description": "Fırında pişirilmiş geleneksel sütlaç. Tarçın ile servis edilir.",
            "price": 75.0,
            "category": "Tatlı",
            "allergens": ["Süt/Laktoz", "Gluten"],
        },
        {
            "name": "Baklava",
            "description": "Antep fıstıklı el açması baklava. 4 dilim.",
            "price": 125.0,
            "category": "Tatlı",
            "allergens": ["Gluten", "Fıstık"],
        },
        # ── İçecekler ──
        {
            "name": "Ayran",
            "description": "Ev yapımı taze ayran.",
            "price": 25.0,
            "category": "İçecek",
            "allergens": ["Süt/Laktoz"],
        },
        {
            "name": "Taze Limonata",
            "description": "Taze sıkılmış limon, nane ve buz ile.",
            "price": 45.0,
            "category": "İçecek",
            "allergens": [],
        },
        {
            "name": "Türk Kahvesi",
            "description": "Geleneksel Türk kahvesi, lokum ile servis edilir.",
            "price": 40.0,
            "category": "İçecek",
            "allergens": [],
        },
        {
            "name": "Çay",
            "description": "Demli Rize çayı, ince belli bardakta.",
            "price": 15.0,
            "category": "İçecek",
            "allergens": [],
        },
    ]

    for item in menu_items:
        product = Product(
            restaurant_id=rid,
            name=item["name"],
            description=item["description"],
            price=item["price"],
            category=item["category"],
            is_available=True,
        )
        # Attach allergens
        for aname in item["allergens"]:
            if aname in allergens:
                product.allergens.append(allergens[aname])

        db.add(product)
        db.flush()
        allerg_str = ", ".join(item["allergens"]) if item["allergens"] else "—"
        print(f"  🍽️  ID:{product.id:>2} | {item['category']:<12} | {item['name']:<20} | {item['price']:>6.0f}₺ | Alerjen: {allerg_str}")

    db.commit()

    # ── Summary ──
    total = db.query(Product).filter(Product.restaurant_id == rid).count()
    total_a = db.query(Allergen).filter(Allergen.restaurant_id == rid).count()
    print(f"\n✅ Seed complete: {total} products, {total_a} allergens")
    print(f"📱 QR Menu URL: http://localhost:5173/menu/<qr_token>")

    # Print QR tokens
    from models.models import Table
    tables = db.query(Table).filter(Table.restaurant_id == rid).all()
    for t in tables:
        print(f"   Masa {t.table_number}: http://localhost:5173/menu/{t.qr_token}")

finally:
    db.close()
