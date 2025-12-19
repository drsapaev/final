import sqlite3
import json

conn = sqlite3.connect('clinic.db')
c = conn.cursor()

# Check entry 506 (Хово Логи)
c.execute("SELECT id, patient_id, patient_name, queue_time, visit_id, services, service_codes FROM queue_entries WHERE id = 506")
row = c.fetchone()
if row:
    print(f"--- Entry 506 (Хово Логи) ---")
    print(f"ID={row[0]}, patient_id={row[1]}, name={row[2]}")
    print(f"queue_time={row[3]}")
    print(f"visit_id={row[4]} <-- Fix 2 должен заполнить это!")
    print(f"service_codes={row[6]}")
    if row[5]:
        try:
            services = json.loads(row[5])
            for svc in services:
                print(f"  - {svc.get('name', 'N/A')} (code={svc.get('code', 'N/A')}, id={svc.get('service_id', 'N/A')})")
        except:
            print(f"services (raw): {row[5][:200]}")
else:
    print("Entry 506 not found")

# Check if Visit was created
if row and row[4]:
    visit_id = row[4]
    c.execute("SELECT id, patient_id, visit_date, status, notes FROM visits WHERE id = ?", (visit_id,))
    visit = c.fetchone()
    if visit:
        print(f"\n--- Visit {visit[0]} ---")
        print(f"patient_id={visit[1]}, date={visit[2]}, status={visit[3]}")
        print(f"notes={visit[4]}")
        
        # Check visit_services
        c.execute("SELECT service_id, code, name, qty, price FROM visit_services WHERE visit_id = ?", (visit_id,))
        vs_rows = c.fetchall()
        print(f"\nVisitServices ({len(vs_rows)} услуг):")
        for vs in vs_rows:
            print(f"  - service_id={vs[0]}, code={vs[1]}, name={vs[2]}, qty={vs[3]}, price={vs[4]}")
else:
    print("\n⚠️ visit_id пустой - Fix 2 не сработал или это не первое заполнение")

conn.close()
