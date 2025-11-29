from __future__ import annotations

"""
Вспомогательный скрипт для быстрой проверки сегодняшних визитов в базе clinic.db.
Ничего не меняет, только читает данные.
"""

import os
import sqlite3
from datetime import date


def main() -> None:
  db_path = os.path.abspath("clinic.db")
  print(f"DB_PATH: {db_path}")

  if not os.path.exists(db_path):
    print("❌ Файл базы данных clinic.db не найден")
    return

  conn = sqlite3.connect(db_path)
  cur = conn.cursor()

  today = date.today().isoformat()
  print(f"\n=== VISITS TODAY (visits.visit_date = {today}) ===")
  try:
    cur.execute(
      """
      SELECT id, patient_id, department, visit_date, visit_time, status, discount_mode, approval_status
      FROM visits
      WHERE visit_date = ?
      ORDER BY id DESC
      LIMIT 50
      """,
      (today,),
    )
    rows = cur.fetchall()
    if not rows:
      print("  (нет записей в visits на сегодня)")
    else:
      for r in rows:
        print("  ", r)
  except Exception as e:  # pragma: no cover
    print("Error querying visits:", e)

  print(f"\n=== APPOINTMENTS TODAY (appointments.appointment_date = {today}) ===")
  try:
    cur.execute(
      """
      SELECT id, patient_id, department, appointment_date, appointment_time, status
      FROM appointments
      WHERE appointment_date = ?
      ORDER BY id DESC
      LIMIT 50
      """,
      (today,),
    )
    rows = cur.fetchall()
    if not rows:
      print("  (нет записей в appointments на сегодня)")
    else:
      for r in rows:
        print("  ", r)
  except Exception as e:  # pragma: no cover
    print("Error querying appointments:", e)

  conn.close()


if __name__ == "__main__":
  main()


