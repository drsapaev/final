"""Check and Fix services in clinic.db"""
import os
import sqlite3

def check_db(db_path):
    if not os.path.exists(db_path):
        print(f"File not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"\n--- Checking {db_path} ---")
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    if 'services' not in tables:
        print("Table 'services' NOT FOUND in this database.")
        conn.close()
        return

    # Check ECG services
    print("\nECG Services:")
    cursor.execute("SELECT id, name, category_code, service_code FROM services WHERE name LIKE '%ЭКГ%' OR service_code='ECG01' OR service_code='K10'")
    rows = cursor.fetchall()
    for row in rows:
        print(f"  ID={row[0]}, Name={row[1]}, Category={row[2]}, Code={row[3]}")
    
    # Check Cardio services
    print("\nCardio Services (First 5):")
    cursor.execute("SELECT id, name, category_code, service_code FROM services WHERE category_code='K' OR service_code='K01' LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(f"  ID={row[0]}, Name={row[1]}, Category={row[2]}, Code={row[3]}")

    # Fix them
    print("\nApplying fixes...")
    
    # Fix ECG -> K10
    cursor.execute("""
        UPDATE services 
        SET service_code='K10', category_code='K' 
        WHERE name='ЭКГ' OR service_code='ECG01'
    """)
    print(f"  Fixed ECG: {cursor.rowcount} rows")
    
    # Fix K1 -> K01 (if any)
    cursor.execute("""
        UPDATE services 
        SET service_code='K01'
        WHERE service_code='K1'
    """)
    print(f"  Fixed K1 -> K01: {cursor.rowcount} rows")

    # Double check K01
    cursor.execute("""
        UPDATE services
        SET service_code='K01'
        WHERE name LIKE 'Консультация кардиолога%' AND (service_code IS NULL OR service_code = '')
    """)
    print(f"  Ensured K01 for cardiologist consultations: {cursor.rowcount} rows")

    conn.commit()
    conn.close()

# Paths found by find_by_name
paths = ['clinic.db', 'app/clinic.db']
for p in paths:
    check_db(p)

print("\nDone!")
