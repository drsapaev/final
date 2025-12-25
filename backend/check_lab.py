from app.db.session import SessionLocal
from sqlalchemy import text
import json

db = SessionLocal()
result = db.execute(text("""
    SELECT id, patient_name, service_codes, services
    FROM queue_entries 
    WHERE id = 505
""")).fetchone()

if result:
    print(f"ID={result[0]}, patient={result[1]}")
    print(f"service_codes: {result[2]}")
    print(f"services raw: {result[3]}")
    
    # Parse services JSON
    if result[3]:
        try:
            services = json.loads(result[3])
            print(f"\nParsed services:")
            for svc in services:
                print(f"  - {svc}")
        except:
            print(f"Cannot parse services as JSON")
