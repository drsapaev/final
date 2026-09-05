"""
Seed the canonical services price list (services + service_categories).

The clinic's real price list lived only in the dev/restore database
(backend/restore_data/clinic.db). It was migrated to production on
2026-09-05; this seeder mirrors that migrated state so the catalog can be
restored into any freshly recreated database.

Usage:
    cd backend && python -m app.scripts.seed_services

    # custom database
    cd backend && python -m app.scripts.seed_services --database-url <url>

    # show what would be inserted without committing
    cd backend && python -m app.scripts.seed_services --dry-run

Data notes (must stay in sync with the 2026-09-05 production migration):
- 15 categories + 66 services; test rows (id 81 "other"/Тестостерон duplicate,
  id 128 "Тестовая услуга" with negative price) are intentionally excluded.
- category_code is normalized to the canonical single letters K/D/C/L/S/O
  (the DB column is VARCHAR(1) and the API contract is ^[KDCLSOP]$).
- service_code is NULL for LAB_BILE_URINE / LAB_GLUCOSE_FAST: the values are
  longer than the VARCHAR(10) column, and `code` keeps the full value
  (lookups match on code OR service_code).

Safety:
- Idempotent — existing rows are matched by code (fallback service_code) and
  never modified. Insert-only: admin edits in a live DB are not clobbered.
- Category links are resolved by category code, not by hardcoded ids.
- Refuses to run against DB names containing 'prod'/'production' unless
  --confirm-prod is passed.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.scripts.reset_dev_db import DevDatabaseSafetyError, get_database_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")
log = logging.getLogger("seed_services")


@dataclass(frozen=True)
class CategorySpec:
    code: str
    name_ru: str | None
    name_uz: str | None = None
    name_en: str | None = None
    specialty: str | None = None


@dataclass(frozen=True)
class ServiceSpec:
    code: str
    name: str
    price: str  # Decimal-safe string, UZS
    category_code: str | None = None
    service_code: str | None = None
    category_link: str | None = None  # service_categories.code
    queue_tag: str | None = None
    duration_minutes: int = 30
    requires_doctor: bool = False
    is_consultation: bool = False
    department_key: str | None = None


CATEGORIES: tuple[CategorySpec, ...] = (
    CategorySpec("consultation.cardiology", "Консультация кардиолога", "Kardiolog maslahati", "Cardiologist consultation", "cardiology"),
    CategorySpec("consultation.dermatology", "Консультация дерматолога", "Dermatolog maslahati", "Dermatologist consultation", "dermatology"),
    CategorySpec("consultation.stomatology", "Консультация стоматолога", "Stomatolog maslahati", "Dentist consultation", "stomatology"),
    CategorySpec("procedure.cosmetology", "Косметологические процедуры", "Kosmetologik protseduralar", "Cosmetology procedures", "dermatology"),
    CategorySpec("diagnostics.ecg", "ЭКГ", "EKG", "ECG", "cardiology"),
    CategorySpec("diagnostics.echo", "ЭхоКГ", "ExoKG", "Echocardiography", "cardiology"),
    CategorySpec("laboratory", "Лабораторные анализы", "Laboratoriya tahlillari", specialty="laboratory"),
    CategorySpec("dermatology", "Дерматологические услуги", "Dermatologiya xizmatlari", specialty="dermatology"),
    CategorySpec("cosmetology", "Косметологические услуги", "Kosmetologiya xizmatlari", specialty="cosmetology"),
    CategorySpec("cardiology", "Кардиология", "Kardiologiya", "Cardiology", "cardiology"),
    CategorySpec("dentistry", "Стоматология", "Stomatologiya", "Dentistry", "dentistry"),
    CategorySpec("other", "Прочие услуги", "Boshqa xizmatlar", "Other services", "other"),
    CategorySpec("K", "Консультации", specialty="therapy"),
    CategorySpec("C", "Кардиология", specialty="cardiology"),
    CategorySpec("D", "Дерматология", specialty="dermatology"),
)

SERVICES: tuple[ServiceSpec, ...] = (
    # Консультации
    ServiceSpec("K01", "Консультация кардиолога", "50000", category_code="K", service_code="K01", category_link="consultation.cardiology", queue_tag="cardio", requires_doctor=True, is_consultation=True, department_key="cardiology"),
    ServiceSpec("D01", "Консультация дерматолога-косметолога", "50000", category_code="D", service_code="D01", queue_tag="dermatology", requires_doctor=True, is_consultation=True),
    ServiceSpec("S01", "Консультация стоматолога", "40000", category_code="S", service_code="S01", queue_tag="stomatology", requires_doctor=True, is_consultation=True),
    ServiceSpec("O20", "Невропатолог", "100000", category_code="O", service_code="O20", category_link="other", queue_tag="neurology", duration_minutes=20, is_consultation=True, department_key="neurology"),
    # Кардиодиагностика
    ServiceSpec("K10", "ЭКГ", "25000", category_code="K", service_code="K10", queue_tag="ecg", duration_minutes=20, requires_doctor=True, department_key="echokg"),
    ServiceSpec("K11", "ЭхоКГ", "150000", category_code="K", service_code="K11", category_link="diagnostics.echo", queue_tag="cardio", requires_doctor=True, department_key="cardiology"),
    ServiceSpec("K03", "СМАД", "100000", category_code="K", service_code="K03", category_link="cardiology", queue_tag="ecg"),
    # Лаборатория (общие)
    ServiceSpec("L01", "Общий анализ крови", "15000", category_code="L", service_code="L01", queue_tag="lab"),
    ServiceSpec("L14", "Гемоглобин", "8000", category_code="L", service_code="L02", queue_tag="general", duration_minutes=15),
    ServiceSpec("L25", "Время свертываемости крови", "10000", category_code="L", service_code="L03", queue_tag="general", duration_minutes=20),
    ServiceSpec("L19", "Общий белок", "12000", category_code="L", service_code="L10", queue_tag="general"),
    ServiceSpec("L03", "Глюкоза", "8000", category_code="L", service_code="L11", queue_tag="general", duration_minutes=15),
    ServiceSpec("L16", "Холестерин", "10000", category_code="L", service_code="L12", queue_tag="general", duration_minutes=20),
    ServiceSpec("L18", "Мочевина", "9000", category_code="L", service_code="L13", queue_tag="general", duration_minutes=20),
    ServiceSpec("L17", "Креатинин", "9000", category_code="L", service_code="L14", queue_tag="general", duration_minutes=20),
    ServiceSpec("LAB_ALT", "АлАТ (аланинаминотрансфераза)", "12000", category_code="L", service_code="L15", queue_tag="general", duration_minutes=25),
    ServiceSpec("LAB_AST", "АсАТ (аспартотаминотрансфераза)", "12000", category_code="L", service_code="L16", queue_tag="general", duration_minutes=25),
    ServiceSpec("L15", "Билирубин (общ, прям, непрям)", "15000", category_code="L", service_code="L17", queue_tag="general"),
    ServiceSpec("L20", "Щелочная фосфатаза", "10000", category_code="L", service_code="L18", queue_tag="general", duration_minutes=20),
    ServiceSpec("L21", "Альфа-амилаза", "10000", category_code="L", service_code="L19", queue_tag="general", duration_minutes=20),
    ServiceSpec("L27", "Калий", "8000", category_code="L", service_code="L20", queue_tag="general", duration_minutes=15),
    ServiceSpec("LAB_CA", "Кальций", "8000", category_code="L", service_code="L21", queue_tag="general", duration_minutes=15),
    ServiceSpec("L28", "Натрий", "8000", category_code="L", service_code="L22", queue_tag="general", duration_minutes=15),
    ServiceSpec("L35", "Витамин Д", "25000", category_code="L", service_code="L23", queue_tag="general"),
    ServiceSpec("LAB_HBA1C", "Гликированный гемоглобин (НЬА1C)", "18000", category_code="L", service_code="L24", queue_tag="general"),
    ServiceSpec("L05", "Общий анализ мочи", "10000", category_code="L", service_code="L25", queue_tag="lab", duration_minutes=20),
    ServiceSpec("LAB_BILE_URINE", "Желчные пигменты на моче", "8000", category_code="L", queue_tag="general", duration_minutes=15),
    ServiceSpec("LAB_GLUCOSE_FAST", "Глюкоза экспресс тест", "5000", category_code="L", queue_tag="lab", duration_minutes=10),
    # Лаборатория (инфекции)
    ServiceSpec("L11", "HBsAg Экспресс тест", "15000", category_code="L", service_code="L30", queue_tag="lab", duration_minutes=15),
    ServiceSpec("L13", "HCV Экспресс тест", "15000", category_code="L", service_code="L31", queue_tag="lab", duration_minutes=15),
    ServiceSpec("L12", "HIV Экспресс тест", "15000", category_code="L", service_code="L32", queue_tag="lab", duration_minutes=15),
    ServiceSpec("LAB_RW", "RW Экспресс тест", "15000", category_code="L", service_code="L33", queue_tag="lab", duration_minutes=15),
    ServiceSpec("L30", "Спермограмма", "30000", category_code="L", service_code="L34", queue_tag="general", duration_minutes=60),
    # Лаборатория (воспаление/ревматология)
    ServiceSpec("LAB_RF", "Ревматоидный фактор (RF)", "12000", category_code="L", service_code="L40", queue_tag="general", duration_minutes=20),
    ServiceSpec("LAB_CRP", "С-реактивный белок (CRP)", "12000", category_code="L", service_code="L41", queue_tag="general", duration_minutes=20),
    ServiceSpec("L22", "Антистрептолизин-О (ASlO)", "12000", category_code="L", service_code="L42", queue_tag="general", duration_minutes=20),
    ServiceSpec("L24", "Бруцеллез (Rose Bengal)", "12000", category_code="L", service_code="L43", queue_tag="general", duration_minutes=20),
    # Лаборатория (гормоны)
    ServiceSpec("L34", "ТТГ (тиреотропный гормон)", "20000", category_code="L", service_code="L50", queue_tag="general"),
    ServiceSpec("L33", "Т4 (тироксин)", "18000", category_code="L", service_code="L51", queue_tag="general"),
    ServiceSpec("L32", "Т3 (трийодтиронин)", "18000", category_code="L", service_code="L52", queue_tag="general"),
    ServiceSpec("L23", "АТ-ТПО (аутоантитело к тиреопероксидазе)", "22000", category_code="L", service_code="L53", queue_tag="general"),
    ServiceSpec("LAB_TEST", "Тестостерон", "20000", category_code="L", service_code="L54", queue_tag="lab"),
    # Лаборатория (дерматология/прочее)
    ServiceSpec("LAB_FUNGI", "Нити грибки", "8000", category_code="L", service_code="L60", queue_tag="general", duration_minutes=15),
    ServiceSpec("LAB_MALAS", "Malassezia furfur", "10000", category_code="L", service_code="L61", queue_tag="general", duration_minutes=20),
    ServiceSpec("L26", "Демодекоз", "8000", category_code="L", service_code="L62", queue_tag="general", duration_minutes=15),
    ServiceSpec("L29", "Мазок на степень чистоты", "8000", category_code="L", service_code="L63", queue_tag="general", duration_minutes=15),
    ServiceSpec("L31", "Кал на я/г", "10000", category_code="L", service_code="L64", queue_tag="general", duration_minutes=20),
    ServiceSpec("LAB_IGE", "Иммуноглобулин Е", "18000", category_code="L", service_code="L65", queue_tag="general"),
    # Стоматология
    ServiceSpec("S10", "Рентгенография зуба", "15000", category_code="S", service_code="S10", queue_tag="stomatology", duration_minutes=15, requires_doctor=True),
    # Физиотерапия
    ServiceSpec("P08", "Дарсонваль", "15000", category_code="P", service_code="P01", queue_tag="procedures", duration_minutes=20, requires_doctor=True),
    ServiceSpec("P03", "УФО терапия", "12000", category_code="P", service_code="P02", queue_tag="procedures", duration_minutes=15, requires_doctor=True),
    ServiceSpec("P09", "Диодная маска лица", "18000", category_code="P", service_code="P03", queue_tag="procedures", requires_doctor=True),
    ServiceSpec("P07", "Биоптрон - светотерапия", "20000", category_code="P", service_code="P04", queue_tag="procedures", duration_minutes=25, requires_doctor=True),
    ServiceSpec("P10", "Эксимер лазер", "25000", category_code="P", service_code="P05", queue_tag="procedures", requires_doctor=True),
    # Косметология
    ServiceSpec("C07", "Плазмолифтинг лица", "80000", category_code="C", service_code="C01", queue_tag="procedures", duration_minutes=60, requires_doctor=True),
    ServiceSpec("C08", "Плазмолифтинг волос", "70000", category_code="C", service_code="C02", queue_tag="procedures", duration_minutes=45, requires_doctor=True),
    ServiceSpec("C03", "Мезотерапия", "60000", category_code="C", service_code="C03", queue_tag="procedures", duration_minutes=45, requires_doctor=True),
    ServiceSpec("C06", "Чистка лица", "40000", category_code="C", service_code="C04", queue_tag="procedures", duration_minutes=60, requires_doctor=True),
    ServiceSpec("C09", "Безоперационная блефаропластика", "120000", category_code="C", service_code="C05", queue_tag="procedures", duration_minutes=90, requires_doctor=True),
    ServiceSpec("C12", "Удаление жировик", "30000", category_code="C", service_code="C06", queue_tag="procedures", requires_doctor=True),
    ServiceSpec("C11", "Лазерное удаление татуаж и татуировок", "50000", category_code="C", service_code="C07", queue_tag="procedures", duration_minutes=45, requires_doctor=True),
    ServiceSpec("C10", "Карбоновый пилинг", "45000", category_code="C", service_code="C08", queue_tag="procedures", duration_minutes=45, requires_doctor=True),
    # Дерматологические процедуры
    ServiceSpec("D06", "Криодеструкция бородавок", "25000", category_code="D", service_code="D_PROC01", queue_tag="procedures", duration_minutes=20, requires_doctor=True),
    ServiceSpec("D05", "Криодеструкция папиллом", "25000", category_code="D", service_code="D_PROC02", queue_tag="procedures", duration_minutes=20, requires_doctor=True),
    ServiceSpec("D07", "Мезотерапия келлоидных рубцов", "40000", category_code="D", service_code="D_PROC03", queue_tag="procedures", requires_doctor=True),
    # УЗИ / прочее
    ServiceSpec("O10", "УЗИ", "120000", category_code="O", service_code="O10", category_link="other", queue_tag="ultrason", duration_minutes=15, department_key="ultrason"),
)


def _find_category(db: Session, model: type, code: str):
    return db.query(model).filter(model.code == code).first()


def _find_service(db: Session, model: type, spec: ServiceSpec):
    found = db.query(model).filter(model.code == spec.code).first()
    if found is None and spec.service_code:
        found = db.query(model).filter(model.service_code == spec.service_code).first()
    return found


def seed_services_catalog(db: Session) -> dict[str, int]:
    """Insert missing categories/services. Never mutates existing rows.

    Returns insertion counters for callers/tests to assert on.
    """
    from app.models.clinic import ServiceCategory
    from app.models.service import Service

    category_by_code = {
        cat.code: _find_category(db, ServiceCategory, cat.code) for cat in CATEGORIES
    }

    categories_inserted = 0
    for cat in CATEGORIES:
        if category_by_code[cat.code] is not None:
            continue
        category_by_code[cat.code] = ServiceCategory(
            code=cat.code,
            name_ru=cat.name_ru,
            name_uz=cat.name_uz,
            name_en=cat.name_en,
            specialty=cat.specialty,
            active=True,
        )
        db.add(category_by_code[cat.code])
        categories_inserted += 1
    db.flush()

    services_inserted = 0
    for spec in SERVICES:
        if _find_service(db, Service, spec) is not None:
            continue
        category = (
            category_by_code.get(spec.category_link) if spec.category_link else None
        )
        db.add(
            Service(
                code=spec.code,
                name=spec.name,
                price=Decimal(spec.price),
                currency="UZS",
                active=True,
                category_code=spec.category_code,
                service_code=spec.service_code,
                category_id=category.id if category else None,
                duration_minutes=spec.duration_minutes,
                requires_doctor=spec.requires_doctor,
                queue_tag=spec.queue_tag,
                is_consultation=spec.is_consultation,
                department_key=spec.department_key,
            )
        )
        services_inserted += 1

    db.commit()
    summary = {
        "categories_inserted": categories_inserted,
        "categories_existing": len(CATEGORIES) - categories_inserted,
        "services_inserted": services_inserted,
        "services_existing": len(SERVICES) - services_inserted,
    }
    log.info(
        "seed finished: categories +%d (%d present), services +%d (%d present)",
        summary["categories_inserted"],
        summary["categories_existing"],
        summary["services_inserted"],
        summary["services_existing"],
    )
    return summary


def _ensure_not_production(database_url: str, confirm_prod: bool) -> None:
    lowered = database_url.lower()
    if ("prod" in lowered or "production" in lowered) and not confirm_prod:
        raise DevDatabaseSafetyError(
            "DATABASE_URL looks like a production database; "
            "pass --confirm-prod to proceed."
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed the canonical services price list (idempotent, insert-only)."
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Target database URL (defaults to DATABASE_URL env var).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Roll back at the end instead of committing.",
    )
    parser.add_argument(
        "--confirm-prod",
        action="store_true",
        help="Required when the database name looks like production.",
    )
    args = parser.parse_args(argv)

    try:
        database_url = get_database_url(args.database_url)
        _ensure_not_production(database_url, args.confirm_prod)
    except DevDatabaseSafetyError as exc:
        log.error("%s", exc)
        return 2

    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine)
    db = session_factory()
    try:
        summary = seed_services_catalog(db)
        if args.dry_run:
            db.rollback()
            log.info("dry-run: rolled back, nothing committed")
        return 0
    except Exception:
        db.rollback()
        log.exception("seed failed, rolled back")
        return 1
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
