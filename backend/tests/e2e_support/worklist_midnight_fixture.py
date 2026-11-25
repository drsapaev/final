"""Disposable integration runner fixture; not an application entry point."""

import builtins
import datetime
import json
import os
import types
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
        doctor_ids = []
        for key in ["owner", "other"]:
            user = User(
                username=f"synthetic-{key}",
                email=f"{key}@example.test",
                full_name=f"SYNTHETIC-{key}",
                hashed_password=get_password_hash(
                    os.environ["WORKLIST_PROOF_PASSWORD"]
                ),
                role="derma",
                is_active=True,
            )
            db.add(user)
            db.flush()
            doc = Doctor(
                user_id=user.id,
                specialty="dermatology",
                active=True,
                cabinet="SYNTHETIC",
            )
            db.add(doc)
            db.flush()
            doctor_ids.append((user.id, doc.id))
        rows = {}
        for key, day, (user_id, doc_id) in [
            ("OLD", "2026-11-25", doctor_ids[0]),
            ("CURRENT", "2026-11-26", doctor_ids[0]),
            ("OTHER", "2026-11-26", doctor_ids[1]),
        ]:
            patient = Patient(
                first_name=key,
                last_name="SYNTHETIC",
                phone=f"+99890000000{len(rows) + 1}",
            )
            db.add(patient)
            db.flush()
            visit = Visit(
                patient_id=patient.id,
                doctor_id=doc_id,
                visit_date=datetime.date.fromisoformat(day),
                department="dermatology",
                status="open",
            )
            db.add(visit)
            db.flush()
            queue = DailyQueue(
                day=datetime.date.fromisoformat(day),
                specialist_id=doc_id,
                queue_tag="dermatology",
                active=True,
            )
            db.add(queue)
            db.flush()
            entry = OnlineQueueEntry(
                queue_id=queue.id,
                number=len(rows) + 1,
                patient_id=patient.id,
                visit_id=visit.id,
                patient_name=f"SYNTHETIC {key}",
                phone=patient.phone,
                source="desk",
                status="called",
            )
            db.add(entry)
            db.flush()
            rows[key] = {
                "entry": entry.id,
                "patient": patient.id,
                "doctor": doc_id,
                "user": user_id,
                "visit": visit.id,
            }
        db.commit()
        (proof_dir / "fixture.json").write_text(json.dumps(rows))
