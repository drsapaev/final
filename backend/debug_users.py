
import sys
import os

# Add backend directory to python path
sys.path.append(os.getcwd())

from app.db.session import SessionLocal
from app.models.user import User

def list_users():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print(f"{'ID':<5} | {'Username':<30} | {'Email':<30} | {'Role':<15}")
        print("-" * 85)
        for user in users:
            print(f"{user.id:<5} | {str(user.username):<30} | {str(user.email):<30} | {str(user.role):<15}")
    finally:
        db.close()

if __name__ == "__main__":
    list_users()
