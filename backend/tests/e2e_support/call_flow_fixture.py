"""Disposable integration runner fixture; not an application entry point."""

import builtins
import datetime
import json
import os
import types
from datetime import UTC
from urllib.parse import urlsplit

from pathlib import Path

# Never start this fixture against an existing database or a remote server.
target = urlsplit(os.environ["DATABASE_URL"])
if (
    os.environ.get("TESTING") != "1"
    or target.hostname != "127.0.0.1"
    or target.path != "/synthetic_worklist"
):
    raise RuntimeError("A disposable localhost worklist database is required")
from sqlalchemy import inspect  # noqa: E402
from app.db import base  # noqa: E402, F401
from app.db.base_class import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.crud import clinic  # noqa: E402
from app.models.clinic import Doctor  # noqa: E402
from app.models.online_queue import DailyQueue, OnlineQueueEntry  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.visit import Visit  # noqa: E402
from app.main import app  # noqa: E402


proof_dir = Path(os.environ["WORKLIST_PROOF_DIR"])
clock_file = proof_dir / "instant"


def instant():
    return datetime.datetime.fromisoformat(clock_file.read_text().strip())


class FrozenDateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return instant().astimezone(tz) if tz else instant().replace(tzinfo=None)


def frozen_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "datetime" and fromlist == ("datetime",):
        return types.SimpleNamespace(datetime=FrozenDateTime)
    return builtins.__import__(name, globals, locals, fromlist, level)


fn = clinic.clinic_today
clinic.clinic_today = types.FunctionType(
    fn.__code__,
    {**fn.__globals__, "__builtins__": {**vars(builtins), "__import__": frozen_import}},
)

if __name__ == "__main__":
    if inspect(engine).get_table_names():
        raise RuntimeError("The synthetic database must be empty")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        rows = {}
        for mode in ("manual", "complete", "finish"):
            user = User(
                username=f"synthetic-{mode}",
                email=f"{mode}@example.test",
                full_name=f"SYNTHETIC-{mode}",
                hashed_password=get_password_hash(os.environ["WORKLIST_PROOF_PASSWORD"]),
                role="Doctor", is_active=True,
            )
            db.add(user)
            db.flush()
            doc = Doctor(
                user_id=user.id, specialty="dentistry", active=True, cabinet="101",
            )
            db.add(doc)
            db.flush()
            actor = {"user": user.id, "doctor": doc.id, "days": {}}
            for day in ("2026-11-25", "2026-11-26"):
                check_day = datetime.date.fromisoformat(day)
                q_main = DailyQueue(
                    day=check_day, specialist_id=doc.id, queue_tag="dentistry", active=True,
                )
                q_followup = DailyQueue(
                    day=check_day, specialist_id=doc.id, queue_tag="dentistry_followup", active=True,
                )
                db.add_all([q_main, q_followup])
                db.flush()
                p = Patient(first_name="TEST", last_name="SYNTHETIC")
                db.add(p)
                db.flush()
                v = Visit(
                    patient_id=p.id, doctor_id=doc.id, visit_date=check_day,
                    department="dentistry", status="in_progress",
                )
                db.add(v)
                db.flush()
                current = OnlineQueueEntry(
                    queue_id=q_main.id, number=3, patient_id=p.id, visit_id=v.id,
                    patient_name="SYNTHETIC CURRENT", source="desk", status="in_progress",
                )
                # Lower ticket number and earlier time lose to restored priority.
                other = OnlineQueueEntry(
                    queue_id=q_main.id, number=1, patient_name="SYNTHETIC OTHER",
                    source="desk", status="waiting", priority=0,
                    queue_time=datetime.datetime.combine(check_day, datetime.time(9), UTC),
                )
                winner = OnlineQueueEntry(
                    queue_id=q_followup.id, number=9, patient_name="SYNTHETIC RETURN",
                    source="desk", status="waiting", priority=1,
                    queue_time=datetime.datetime.combine(check_day, datetime.time(10), UTC),
                )
                db.add_all([current, other, winner])
                db.flush()
                actor["days"][day] = {
                    "current": current.id, "other": other.id, "winner": winner.id,
                    "patient": p.id, "visit": v.id,
                }
            rows[mode] = actor
        db.commit()
        (proof_dir / "fixture.json").write_text(json.dumps(rows))
