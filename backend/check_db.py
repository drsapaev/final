import sqlite3
import json

conn = sqlite3.connect('clinic.db')
c = conn.cursor()

# Check all entries for patient 377
c.execute("SELECT id, patient_id, patient_name, queue_time, services, service_codes FROM queue_entries WHERE patient_id = 377 ORDER BY id")
rows = c.fetchall()
print("--- Entries for patient 377 (Тестовая Кардио) ---")
for r in rows:
    print(f"\nID={r[0]}, patient_id={r[1]}, name={r[2]}")
    print(f"  queue_time={r[3]}")
    print(f"  service_codes={r[5]}")
    if r[4]:
        try:
            services = json.loads(r[4])
            for svc in services:
                print(f"    - {svc.get('name', 'N/A')} (code={svc.get('code', 'N/A')}, id={svc.get('service_id', 'N/A')})")
        except:
            print(f"  services (raw): {r[4][:200]}")
