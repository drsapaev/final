"""Update ЭКГ service code from ECG01 to K10"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text

# Connect to database
db_path = os.path.join(os.path.dirname(__file__), 'app', 'clinic.db')
engine = create_engine(f'sqlite:///{db_path}')

with engine.connect() as conn:
    # Update ЭКГ service code
    result = conn.execute(text("""
        UPDATE services 
        SET service_code='K10', category_code='K' 
        WHERE name='ЭКГ' OR service_code='ECG01'
    """))
    conn.commit()
    print(f"Updated {result.rowcount} rows")
    
    # Show result
    result = conn.execute(text("""
        SELECT id, name, code, service_code, category_code 
        FROM services 
        WHERE name LIKE '%ЭКГ%' OR name LIKE '%ЭхоКГ%'
    """))
    print("\nServices with ЭКГ/ЭхоКГ:")
    for row in result:
        print(f"  ID={row[0]}, name={row[1]}, code={row[2]}, service_code={row[3]}, category_code={row[4]}")

print("\nDone!")
