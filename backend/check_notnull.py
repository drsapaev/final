import sqlite3

con = sqlite3.connect('clinic.db')

def show(t):
    rows = con.execute(f"PRAGMA table_info({t})").fetchall()
    print(f"\n{t}:")
    for cid, name, typ, notnull, defv, pk in rows:
        print(f"  {name:<16} NOT NULL={bool(notnull)}  DEFAULT={defv!r}")

for t in ["visits", "payments", "schedules", "queue_tickets", "activations"]:
    try:
        show(t)
    except Exception as e:
        print(f"{t}: {e}")

con.close()
