
import asyncio
import httpx
import sys
import os

# Add backend to path (needed for token generation if we want to be self-contained, 
# but ideally we just hit the login endpoint or generate token if we have the key)
sys.path.append(os.path.join(os.getcwd(), 'app'))
sys.path.append(os.getcwd())

# We need to generate a valid token. 
# We'll try to import settings. If that fails, we can't generate a token easily without credentials.
try:
    from app.core.config import settings
    from app.core.security import create_access_token
    from app.db.session import SessionLocal
    from app.models.user import User
    
    SECRET_KEY = settings.SECRET_KEY
    ALGORITHM = settings.ALGORITHM
    
    HAS_LOCAL_ACCESS = True
except ImportError:
    HAS_LOCAL_ACCESS = False
    print("⚠️ Local imports failed. Cannot generate token locally.")

async def debug_remote():
    base_url = "http://127.0.0.1:8000"
    
    if not HAS_LOCAL_ACCESS:
        print("Cannot proceed without local access to generate token.")
        return

    # 1. Get Token for Cashier
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "cashier@example.com").first()
        if not user:
            # Fallback to any cashier
            user = db.query(User).filter(User.role == "Cashier").first()
        
        if not user:
            print("❌ No cashier user found in DB.")
            return

        print(f"👤 Using Cashier: {user.username} (ID: {user.id})")
        
        # Generate token
        token = create_access_token(subject={"sub": str(user.id), "username": user.username})
        headers = {"Authorization": f"Bearer {token}"}
        
    finally:
        db.close()

    # 2. Test Endpoint
    print(f"🚀 Sending GET request to {base_url}/api/v1/cashier/pending-payments")
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        try:
            response = await client.get("/api/v1/cashier/pending-payments", headers=headers)
            print(f"📡 Status Code: {response.status_code}")
            print(f"📄 Response Preview: {response.text[:200]}...")
            
            if response.status_code == 200:
                print("✅ ACCESS GRANTED (200 OK)")
            elif response.status_code == 403:
                print("❌ ACCESS DENIED (403 Forbidden)")
                print("👉 check server logs for 'DEBUG: ACCESS DENIED'")
            else:
                print(f"⚠️ Unexpected status: {response.status_code}")
                
        except httpx.ConnectError:
            print("❌ Connection Error: Is the server running on port 8000?")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_remote())
