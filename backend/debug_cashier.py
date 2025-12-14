
import sys
import os
import asyncio
from datetime import timedelta

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'app'))
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.core.security import create_access_token
from app.models.user import User
from app.main import app
from httpx import AsyncClient

async def debug_cashier():
    db = SessionLocal()
    try:
        # 1. Find the cashier user
        user = db.query(User).filter(User.email == "cashier@example.com").first()
        if not user:
            print("ERROR: User cashier@example.com not found!")
            # Try to find ANY cashier
            user = db.query(User).filter(User.role == "Cashier").first()
            if not user:
                print("ERROR: No user with role 'Cashier' found.")
                return
        
        print(f"Found Cashier User: ID={user.id}, Username={user.username}, Role={user.role}, IsActive={user.is_active}")

        # 2. Generate Token
        token = create_access_token(subject={"sub": str(user.id), "username": user.username})
        headers = {"Authorization": f"Bearer {token}"}
        print(f"Generated Token: {token[:20]}...")

        # 3. Test Endpoint using httpx directly against FastAPI app
        async with AsyncClient(app=app, base_url="http://test") as client:
            print("\n--- Testing GET /api/v1/cashier/pending-payments ---")
            response = await client.get("/api/v1/cashier/pending-payments", headers=headers)
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
            if response.status_code == 403:
                print("❌ 403 FORBIDDEN - Debugging failed access")
            elif response.status_code == 200:
                print("✅ 200 OK - Access allowed")
            else:
                print(f"⚠️ Unexpected status: {response.status_code}")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(debug_cashier())
