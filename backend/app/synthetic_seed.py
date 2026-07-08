"""
Synthetic data generator — bulk-generate realistic patients, visits, EMR records.

Distinct from dev_seed.py which creates a small fixed demo dataset (one of
each role, ~5 patients). This script creates THOUSANDS of records for:

- Load testing (P2.1 wait time ML needs 10k+ visits)
- Staging environment with realistic data volume
- Demo recordings that don't look obviously fake
- AI/ML training data without real PII

SAFETY:
- Refuses to run against databases named 'clinicdb' or 'clinic' (prod names).
- Refuses to run without --confirm-synthetic-seed.
- All generated records carry a 'SYNTHETIC-' prefix in last_name so they
  can be deleted with a single SQL query: DELETE FROM patients WHERE
  last_name LIKE 'SYNTHETIC-%'.

Usage:
    cd backend
    python -m app.synthetic_seed --count-patients 1000 --count-visits 10000 --confirm-synthetic-seed

    # Or for a specific DB
    DATABASE_URL=postgresql://user:pass@host:5432/clinic_staging \\
        python -m app.synthetic_seed --count-patients 5000 --confirm-synthetic-seed

Env vars:
    SYNTHETIC_SEED_BATCH_SIZE — bulk insert batch (default 500)
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")
log = logging.getLogger("synthetic_seed")

# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

PROTECTED_DB_NAMES = {"clinicdb", "clinic", "clinic_prod", "clinic_production"}
SYNTHETIC_PREFIX = "SYNTHETIC-"


class SyntheticSeedSafetyError(RuntimeError):
    pass


def _check_db_safety(database_url: str) -> None:
    """Refuse to seed production-looking databases."""
    db_name = database_url.rsplit("/", 1)[-1].split("?")[0].lower()
    for protected in PROTECTED_DB_NAMES:
        if db_name == protected:
            raise SyntheticSeedSafetyError(
                f"Refusing to seed database matching protected name '{protected}'. "
                f"Synthetic seed is for staging/dev only. URL: {database_url[:80]}..."
            )

    # Require explicit dev/staging/test marker in DB name
    if not any(marker in db_name for marker in ("staging", "dev", "test", "synthetic", "sandbox")):
        raise SyntheticSeedSafetyError(
            f"Database name '{db_name}' does not contain 'staging'/'dev'/'test'/'synthetic'/'sandbox'. "
            "Refusing to seed. Rename your staging DB or use --force-unsafe (not recommended)."
        )


# ---------------------------------------------------------------------------
# Realistic data pools (Uzbekistan clinic context)
# ---------------------------------------------------------------------------

UZBEK_LAST_NAMES = [
    "Karimov", "Rahimov", "Saidov", "Yusupov", "Ahmedov", "Tursunov", "Ergashev",
    "Mamadjanov", "Khalilov", "Sattorov", "Nazirov", "Ibragimov", "Vosilov",
    "Abdullaev", "Rashidov", "Toshmatov", "Yuldoshev", "Mirzaev", "Olimov",
    "Husanov", "Salimov", "Bahromov", "Davlatov", "Fozilov", "Ganiev",
]
UZBEK_FIRST_NAMES_M = [
    "Akmal", "Bekzod", "Dilshod", "Jasur", "Kamol", "Laziz", "Murod",
    "Nodir", "Oybek", "Rustam", "Sardor", "Sherzod", "Temur", "Ulugbek",
    "Vohid", "Zafar", "Aziz", "Bobur", "Davron", "Elmurod",
]
UZBEK_FIRST_NAMES_F = [
    "Dilnoza", "Gulnora", "Kamola", "Malika", "Nodira", "Oygul", "Sevara",
    "Zarina", "Aziza", "Barfina", "Charos", "Dilfuza", "Feruza", "Gulbahor",
    "Husnora", "Iroda", "Jamila", "Kumush", "Lola", "Munisa",
]
RUSSIAN_LAST_NAMES = [
    "Ivanov", "Petrov", "Sidorov", "Smirnov", "Kuznetsov", "Popov",
    "Vasiliev", "Mikhailov", "Fedorov", "Volkov", "Sokolov", "Morozov",
]
RUSSIAN_FIRST_NAMES_M = ["Aleksandr", "Dmitriy", "Sergey", "Andrey", "Aleksey", "Maksim"]
RUSSIAN_FIRST_NAMES_F = ["Elena", "Olga", "Tatiana", "Irina", "Natalia", "Svetlana"]

DISTRICTS = [
    "Yunusabad", "Chilanzar", "Mirzo-Ulugbek", "Yakkasaray", "Sergeli",
    "Uchtepa", "Shaykhantakhur", "Olmazor", "Bektemir", "Yashnabad",
]

COMPLAINTS_BY_SPECIALTY = {
    "cardiology": [
        "Боли в груди при физической нагрузке", "Одышка", "Сердцебиение",
        "Повышенное артериальное давление", "Отеки нижних конечностей",
    ],
    "dermatology": [
        "Высыпания на коже", "Кожный зуд", "Покраснение", "Шелушение кожи",
        "Появление родинок",
    ],
    "dental": [
        "Зубная боль", "Кровоточивость десен", "Реакция на холодное/горячее",
        "Подвижность зубов", "Неприятный запах изо рта",
    ],
}

ICD10_BY_SPECIALTY = {
    "cardiology": ["I10", "I20.9", "I25.9", "I50.0", "R07.2"],
    "dermatology": ["L20.9", "L30.9", "L40.0", "L70.0", "L98.9"],
    "dental": ["K02.9", "K04.0", "K05.0", "K05.5", "K08.9"],
}


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def _random_phone() -> str:
    return f"+998{random.choice(['90','91','93','94','95','97','99','88'])}{random.randint(1000000, 9999999)}"


def _random_birth_date() -> date:
    today = date.today()
    age_days = random.randint(365 * 18, 365 * 85)
    return today - timedelta(days=age_days)


def _random_passport() -> str:
    series = random.choice(["AB", "AC", "AD", "AE", "AF", "KA", "KB", "KC"])
    return f"{series}{random.randint(1000000, 9999999)}"


def _generate_patient() -> dict[str, Any]:
    use_russian = random.random() < 0.25
    sex = random.choice(["M", "F"])
    if use_russian:
        last_name = random.choice(RUSSIAN_LAST_NAMES)
        first_name = random.choice(RUSSIAN_FIRST_NAMES_M if sex == "M" else RUSSIAN_FIRST_NAMES_F)
    else:
        last_name = random.choice(UZBEK_LAST_NAMES)
        first_name = random.choice(UZBEK_FIRST_NAMES_M if sex == "M" else UZBEK_FIRST_NAMES_F)
    middle_name = random.choice(UZBEK_FIRST_NAMES_M if sex == "M" else UZBEK_FIRST_NAMES_F)

    return {
        "last_name": f"{SYNTHETIC_PREFIX}{last_name}",
        "first_name": first_name,
        "middle_name": middle_name,
        "birth_date": _random_birth_date(),
        "sex": sex,
        "phone": _random_phone(),
        "email": None,
        "doc_type": "passport_uz",
        "doc_number": _random_passport(),
        "address": f"г. Ташкент, {random.choice(DISTRICTS)} район, ул. {random.choice(['Мирзо Улугбека', 'Амира Темура', 'Бабура', 'Шарафа Рашидова'])}, д. {random.randint(1, 200)}",
        "is_deleted": False,
        "created_at": datetime.now(UTC) - timedelta(days=random.randint(1, 365)),
    }


def _generate_visit(patient_id: int, specialty: str) -> dict[str, Any]:
    complaints = random.choice(COMPLAINTS_BY_SPECIALTY.get(specialty, ["Жалобы на общее самочувствие"]))
    icd10 = random.choice(ICD10_BY_SPECIALTY.get(specialty, ["R69"]))
    visit_date = datetime.now(UTC) - timedelta(days=random.randint(0, 90))

    return {
        "patient_id": patient_id,
        "complaints": complaints,
        "icd10_code": icd10,
        "visit_date": visit_date,
        "status": random.choice(["completed", "completed", "completed", "scheduled", "cancelled"]),
        "created_at": visit_date,
    }


# ---------------------------------------------------------------------------
# Inserters
# ---------------------------------------------------------------------------

def _bulk_insert_patients(db: Session, count: int, batch_size: int) -> int:
    from app.models.patient import Patient

    inserted = 0
    while inserted < count:
        chunk = min(batch_size, count - inserted)
        rows = [_generate_patient() for _ in range(chunk)]
        db.bulk_save_objects([Patient(**row) for row in rows])
        db.commit()
        inserted += chunk
        if inserted % (batch_size * 4) == 0 or inserted == count:
            log.info("  patients: %d / %d", inserted, count)
    return inserted


def _bulk_insert_visits(db: Session, count: int, batch_size: int, specialty: str = "cardiology") -> int:
    """Insert `count` visits, assigning them to random existing patients."""
    patient_ids = [r[0] for r in db.execute(text("SELECT id FROM patients WHERE last_name LIKE :prefix LIMIT 50000"), {"prefix": f"{SYNTHETIC_PREFIX}%"}).all()]
    if not patient_ids:
        log.warning("  No synthetic patients found — skipping visit generation.")
        return 0

    inserted = 0
    # We don't import Visit model — too many schema variations across versions.
    # Use raw SQL; field names match the migration history as of 0031.
    while inserted < count:
        chunk = min(batch_size, count - inserted)
        rows = [_generate_visit(random.choice(patient_ids), specialty) for _ in range(chunk)]
        db.execute(
            text("""
                INSERT INTO visits (patient_id, complaints, icd10_code, visit_date, status, created_at)
                VALUES (:patient_id, :complaints, :icd10_code, :visit_date, :status, :created_at)
            """),
            rows,
        )
        db.commit()
        inserted += chunk
        if inserted % (batch_size * 4) == 0 or inserted == count:
            log.info("  visits (%s): %d / %d", specialty, inserted, count)
    return inserted


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup_synthetic(db: Session) -> dict[str, int]:
    """Delete all synthetic records. Safe to run on any DB."""
    log.info("Cleaning up synthetic records (prefix='%s')...", SYNTHETIC_PREFIX)
    deleted = {}
    # Visits first (FK constraint)
    result = db.execute(text("""
        DELETE FROM visits WHERE patient_id IN (
            SELECT id FROM patients WHERE last_name LIKE :prefix
        )
    """), {"prefix": f"{SYNTHETIC_PREFIX}%"})
    deleted["visits"] = result.rowcount or 0
    db.commit()
    result = db.execute(text("DELETE FROM patients WHERE last_name LIKE :prefix"), {"prefix": f"{SYNTHETIC_PREFIX}%"})
    deleted["patients"] = result.rowcount or 0
    db.commit()
    log.info("Cleanup done: %s", deleted)
    return deleted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bulk-generate synthetic patients + visits for staging/load testing.")
    parser.add_argument("--count-patients", type=int, default=1000)
    parser.add_argument("--count-visits", type=int, default=5000)
    parser.add_argument("--specialty", choices=list(COMPLAINTS_BY_SPECIALTY.keys()), default="cardiology")
    parser.add_argument("--confirm-synthetic-seed", action="store_true",
                        help="Required. Confirms you understand this writes fake data.")
    parser.add_argument("--cleanup-only", action="store_true",
                        help="Skip generation; only delete existing synthetic records.")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--batch-size", type=int, default=int(os.environ.get("SYNTHETIC_SEED_BATCH_SIZE", "500")))
    args = parser.parse_args(argv)

    if not args.confirm_synthetic_seed and not args.cleanup_only:
        print("ERROR: pass --confirm-synthetic-seed to acknowledge you are writing fake data.", file=sys.stderr)
        return 2

    if not args.database_url:
        print("ERROR: DATABASE_URL not set.", file=sys.stderr)
        return 2

    try:
        _check_db_safety(args.database_url)
    except SyntheticSeedSafetyError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    engine = create_engine(args.database_url)
    db = Session(engine)

    try:
        if args.cleanup_only:
            cleanup_synthetic(db)
            return 0

        log.info("Seeding synthetic data (patients=%d, visits=%d, specialty=%s)",
                 args.count_patients, args.count_visits, args.specialty)
        log.info("All records will be tagged with prefix '%s' for easy cleanup.", SYNTHETIC_PREFIX)

        n_patients = _bulk_insert_patients(db, args.count_patients, args.batch_size)
        n_visits = _bulk_insert_visits(db, args.count_visits, args.batch_size, args.specialty)

        log.info("✅ Done. Inserted %d patients + %d visits.", n_patients, n_visits)
        log.info("To clean up: python -m app.synthetic_seed --cleanup-only --confirm-synthetic-seed")
        return 0
    except Exception:
        db.rollback()
        log.exception("Seed failed.")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
