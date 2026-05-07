"""Legacy SQLite queue-entry diagnostic.

PostgreSQL + Alembic are the runtime source of truth. This helper is limited to
explicit local recovery diagnostics against a legacy clinic.db file.
"""

from __future__ import annotations

import json
import os
import sqlite3


def require_diagnostic_db_read() -> None:
    if os.getenv("ALLOW_LEGACY_SQLITE_DIAGNOSTIC_READ") != "1":
        raise SystemExit(
            "Refusing to read diagnostic database state. "
            "Set ALLOW_LEGACY_SQLITE_DIAGNOSTIC_READ=1 only for an explicit local legacy SQLite diagnostic run."
        )


def main() -> int:
    require_diagnostic_db_read()

    conn = sqlite3.connect("clinic.db")
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, patient_id, patient_name, queue_time, services, service_codes
            FROM queue_entries
            WHERE patient_id = 377
            ORDER BY id
            """
        )
        rows = cursor.fetchall()
        print("--- Entries for patient 377 ---")
        for row in rows:
            print(f"\nID={row[0]}, patient_id={row[1]}, name={row[2]}")
            print(f"  queue_time={row[3]}")
            print(f"  service_codes={row[5]}")
            if row[4]:
                try:
                    services = json.loads(row[4])
                    for service in services:
                        print(
                            "    - "
                            f"{service.get('name', 'N/A')} "
                            f"(code={service.get('code', 'N/A')}, "
                            f"id={service.get('service_id', 'N/A')})"
                        )
                except (TypeError, ValueError):
                    print(f"  services (raw): {row[4][:200]}")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
