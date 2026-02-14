from core.database import engine
from sqlalchemy import text

def test_connection():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("✅ Database connection successful!")
            
            # Check for demo restaurant
            result = connection.execute(text("SELECT name FROM restaurants WHERE email = 'demo@garsonai.com'"))
            restaurant = result.fetchone()
            if restaurant:
                print(f"✅ Demo restaurant found: {restaurant[0]}")
            else:
                print("❌ Demo restaurant not found. Please run seed.py.")
                
    except Exception as e:
        print(f"❌ Database connection failed: {e}")

if __name__ == "__main__":
    test_connection()
