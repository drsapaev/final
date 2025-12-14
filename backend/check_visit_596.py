
import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.append(os.path.abspath("c:/final/backend"))

from app.core.config import settings
from app.models.visit import Visit
from app.models.payment import Payment

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

visit_id = 596
visit = db.query(Visit).filter(Visit.id == visit_id).first()

print(f"--- VISIT {visit_id} ---")
if visit:
    print(f"Status: '{visit.status}'")
    print(f"Discount Mode: '{visit.discount_mode}'")
    print(f"Created At: {visit.created_at}")
    print(f"Date: {visit.date}")
    
    payments = db.query(Payment).filter(Payment.visit_id == visit_id).all()
    print(f"Payments count: {len(payments)}")
    for p in payments:
        # Check transaction_id attribute existence safely
        trans_id = getattr(p, 'provider_transaction_id', getattr(p, 'transaction_id', 'N/A'))
        print(f"  Payment {p.id}: Status='{p.status}', Amount={p.amount}, TransID={trans_id}")
else:
    print("Visit not found")

db.close()
