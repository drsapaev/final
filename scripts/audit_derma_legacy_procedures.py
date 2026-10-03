#!/usr/bin/env python3
"""Phase B (P3, реконсиляция #3490/#3491): аудит и нормализация legacy-ключа
specialty_data.procedures в дерма-ЭМК.

Канонический ключ записи косметологических процедур —
specialty_data.cosmetic_procedures (решение P3, Phase A в #3508);
specialty_data.procedures (эпоха #3491) читается проекцией временно как
transitional READ alias. Этот скрипт — операторский инструмент Phase B:

  audit     (READ-ONLY) inventory записей с legacy-ключом, разбор возможных
            double-writes (записи с ОБОИМИ ключами), кросс-чек read-модели
            derma_history_entries; JSON-артефакт для ревью владельца.
  normalize (dry-run по умолчанию) перенос legacy-записей в канонический
            ключ ЧЕРЕЗ стандартный путь записи emr_v2_service (новая
            ревизия EMRRevision с change_type="migrated" / "amended" для
            подписанных, строка EMRAuditLog, проекция пересобирается
            after_flush listener'ом — тот же код, что обслуживает прод).
  verify    (READ-ONLY) Phase C gate: в активных дерма-ЭМК не осталось
            legacy-ключа + паритет procedure-строк read-модели.

Гарантия read-only для audit/verify — механизм, а не политика: PostgreSQL
соединение открывается с default_transaction_read_only=on (любая запись
отвергается сервером), SQLite — PRAGMA query_only=ON. Пароль не печатается.

Примеры (хост C:\\final, локальный прод):

  C:\\final\\backend\\.venv\\Scripts\\python.exe ^
    C:\\final\\scripts\\audit_derma_legacy_procedures.py audit ^
    --env-file C:\\final\\backend\\.env

  # после ревью артефакта — перенос (сначала dry-run, потом --apply):
  ... normalize --record-ids 12,34 --strategy append --user-id 1
  ... normalize --record-ids 12,34 --strategy append --user-id 1 --apply

  # gate перед Phase C:
  ... verify --env-file C:\\final\\backend\\.env

Коды возврата: audit — 0 при успехе прогона (наличие legacy-данных НЕ код
ошибки: это ожидаемый результат аудита); normalize — 0, если все запрошенные
записи обработаны или уже чисты (идемпотентный скип); verify — 0 только если
Phase C gate зелёный.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"

CANONICAL_KEY = "cosmetic_procedures"
LEGACY_KEY = "procedures"
SESSION_MARKER = "phase-b-p3-legacy-migration"
BATCH = 500

# Классификация записи по сочетанию ключей (см. classify_record):
#   legacy_only     — только legacy: append переносит всё без потерь;
#   both_subset     — оба ключа, и КАЖДАЯ валидная legacy-запись уже есть в
#                     canonical (точное совпадение): drop-legacy без потерь;
#   both_partial    — оба ключа, часть legacy совпадает с canonical:
#                     решение владельца по каждой записи;
#   both_disjoint   — оба ключа, совпадений нет: append сохранит все события;
#   canonical_only  — legacy-ключа нет (чисто);
#   none            — нет ни одного ключа с процедурами.
CLASSIFICATIONS = (
    "legacy_only",
    "both_subset",
    "both_partial",
    "both_disjoint",
    "canonical_only",
    "none",
)


def mask_url(url: str) -> str:
    """host/port/db для баннера; пароль не печатается никогда."""
    if url.startswith("sqlite"):
        return "db=%s" % url.split("sqlite:///", 1)[-1]
    m = re.match(r"^[^:/]+://(?:[^@/]+@)?([^/]+)(?:/([^?]+))?", url)
    if not m:
        return "<unparsed>"
    return "host=%s db=%s" % (m.group(1), (m.group(2) or "").split("?")[0] or "<default>")


def resolve_url(args: argparse.Namespace) -> str:
    if args.database_url:
        return args.database_url
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    if args.env_file and Path(args.env_file).is_file():
        try:
            from dotenv import dotenv_values

            env = dotenv_values(args.env_file)
            if env.get("DATABASE_URL"):
                return str(env["DATABASE_URL"])
        except ImportError:
            pass
    sys.exit(
        "Цель не задана: передайте --database-url или --env-file с "
        "DATABASE_URL (backend/.env)."
    )


def make_readonly_engine(url: str) -> sa.Engine:
    if url.startswith("sqlite"):
        engine = sa.create_engine(url, future=True)

        @sa.event.listens_for(engine, "connect")
        def _sqlite_readonly(dbapi_conn, _record):  # noqa: ANN001
            dbapi_conn.execute("PRAGMA query_only=ON")

        return engine
    return sa.create_engine(
        url,
        future=True,
        connect_args={"options": "-c default_transaction_read_only=on"},
    )


def make_readwrite_engine(url: str) -> sa.Engine:
    return sa.create_engine(url, future=True)


def bootstrap_backend() -> None:
    sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------------------------
# Разбор specialty_data (зеркало правил валидности проекции)
# ---------------------------------------------------------------------------


def entry_is_valid(entry: Any) -> bool:
    """Проекция читает запись, только если это dict с непустым
    procedure_type-строкой (derma_history_projection._emr_procedure_items)."""
    if not isinstance(entry, dict):
        return False
    procedure_type = entry.get("procedure_type")
    return isinstance(procedure_type, str) and bool(procedure_type.strip())


def entry_fingerprint(entry: Any) -> str:
    """Канонический JSON для точного сравнения записей между ключами."""
    return json.dumps(entry, sort_keys=True, ensure_ascii=False, default=str)


def split_entries(value: Any) -> tuple[list[Any], list[Any], bool]:
    """(valid, invalid, type_anomaly) для значения массива specialty_data."""
    if value is None:
        return [], [], False
    if not isinstance(value, list):
        return [], [value], True
    valid = [e for e in value if entry_is_valid(e)]
    invalid = [e for e in value if not entry_is_valid(e)]
    return valid, invalid, False


def classify_record(specialty_data: Any) -> dict[str, Any]:
    """Inventory одной записи: ключи, счётчики, совпадения, классификация."""
    out: dict[str, Any] = {
        "classification": "none",
        "canonical": {"present": False, "count": 0, "valid": 0, "invalid": 0,
                      "type_anomaly": False},
        "legacy": {"present": False, "count": 0, "valid": 0, "invalid": 0,
                   "type_anomaly": False},
        "exact_matches": [],       # пары (canonical_idx, legacy_idx)
        "date_type_matches": [],   # (canonical_idx, legacy_idx) — same type+date
        "legacy_valid_entries": [],
        "legacy_invalid_entries": [],
    }
    if not isinstance(specialty_data, dict):
        return out
    for side, key in (("canonical", CANONICAL_KEY), ("legacy", LEGACY_KEY)):
        if key in specialty_data:
            out[side]["present"] = True
            value = specialty_data[key]
            if isinstance(value, list):
                out[side]["count"] = len(value)
            valid, invalid, anomaly = split_entries(value)
            out[side]["valid"] = len(valid)
            out[side]["invalid"] = len(invalid)
            out[side]["type_anomaly"] = anomaly
    canon_valid, _, _ = split_entries(specialty_data.get(CANONICAL_KEY))
    legacy_valid, legacy_invalid, _ = split_entries(specialty_data.get(LEGACY_KEY))
    out["legacy_valid_entries"] = legacy_valid
    out["legacy_invalid_entries"] = legacy_invalid

    if out["legacy"]["present"] and out["canonical"]["present"]:
        canon_fps = [entry_fingerprint(e) for e in canon_valid]
        legacy_fps = [entry_fingerprint(e) for e in legacy_valid]
        matched_legacy: set[int] = set()
        for li, lfp in enumerate(legacy_fps):
            for ci, cfp in enumerate(canon_fps):
                if lfp == cfp:
                    out["exact_matches"].append([ci, li])
                    matched_legacy.add(li)
                    break
        for li, lentry in enumerate(legacy_valid):
            if li in matched_legacy:
                continue
            for ci, centry in enumerate(canon_valid):
                if (
                    lentry.get("procedure_date") == centry.get("procedure_date")
                    and lentry.get("procedure_type") == centry.get("procedure_type")
                ):
                    out["date_type_matches"].append([ci, li])
                    break
        if not legacy_valid:
            out["classification"] = "both_subset"  # переносить нечего
        elif len(matched_legacy) == len(legacy_valid):
            out["classification"] = "both_subset"
        elif matched_legacy:
            out["classification"] = "both_partial"
        else:
            out["classification"] = "both_disjoint"
    elif out["legacy"]["present"]:
        out["classification"] = "legacy_only" if out["legacy"]["valid"] else "none"
    elif out["canonical"]["present"] and out["canonical"]["valid"]:
        out["classification"] = "canonical_only"
    return out


def iter_emr_rows(session: Session):
    """Курсорная выборка всех EMR-записей (keyset по id, батчами)."""
    from app.models.emr_v2 import EMRRecord

    cursor = 0
    while True:
        rows = session.execute(
            sa.select(EMRRecord.__table__)
            .where(EMRRecord.__table__.c.id > cursor)
            .order_by(EMRRecord.__table__.c.id)
            .limit(BATCH)
        ).all()
        if not rows:
            break
        cursor = rows[-1].id
        yield from rows


def scan_records(session: Session) -> tuple[list[dict], list[dict], int]:
    """(derma_inventory, non_derma_with_legacy, emr_total).

    derma_inventory — по одной записи на каждую активную/неактивную дерма-ЭМК,
    где есть хотя бы один ключ процедур ИЛИ legacy-ключ присутствует любым
    образом (включая аномальные типы и пустые списки).
    """
    from app.services.derma_history_projection import is_dermatology_emr

    derma: list[dict] = []
    non_derma: list[dict] = []
    total = 0
    for row in iter_emr_rows(session):
        total += 1
        data = row.data if isinstance(row.data, dict) else {}
        specialty_data = data.get("specialty_data")
        inv = classify_record(specialty_data)
        has_any_key = inv["canonical"]["present"] or inv["legacy"]["present"]
        if is_dermatology_emr(row):
            if has_any_key:
                derma.append(
                    {
                        "record_id": row.id,
                        "patient_id": row.patient_id,
                        "visit_id": row.visit_id,
                        "status": row.status,
                        "is_active": bool(row.is_active),
                        "version": row.version,
                        "row_version": row.row_version,
                        "created_at": str(row.created_at or ""),
                        **inv,
                    }
                )
        elif inv["legacy"]["present"]:
            non_derma.append(
                {"record_id": row.id, "specialty": data.get("specialty"),
                 "is_active": bool(row.is_active),
                 "legacy_count": inv["legacy"]["count"]}
            )
    return derma, non_derma, total


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


def projection_alias_check(session: Session, records: list[dict]) -> dict:
    """Кросс-чек read-модели для записей с валидными legacy-записями.

    Ожидаемые строки строит та же проекция, что listener/backfill
    (emr_entry_dicts); сверяются identity (kind, source, record_id,
    position) и payload с фактическими строками derma_history_entries.
    """
    from app.models.derma_history import DermaHistoryEntry
    from app.models.emr_v2 import EMRRecord
    from app.services.derma_history_projection import (
        _visit_map_for_records,
        emr_entry_dicts,
    )

    ids = [r["record_id"] for r in records]
    result: dict[str, Any] = {"checked_records": len(ids), "mismatches": []}
    if not ids:
        return result
    by_record: dict[int, dict[tuple, dict]] = {rid: {} for rid in ids}
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        orm_rows = (
            session.execute(
                sa.select(EMRRecord).where(EMRRecord.__table__.c.id.in_(chunk))
            )
            .scalars()
            .all()
        )
        visits = _visit_map_for_records(session, list(orm_rows))
        for entry in emr_entry_dicts(list(orm_rows), visits):
            if entry["kind"] != "procedure":
                continue
            key = tuple(entry[f] for f in ("kind", "source", "record_id", "position"))
            by_record[entry["record_id"]][key] = entry
        stored = (
            session.execute(
                sa.select(DermaHistoryEntry)
                .where(
                    DermaHistoryEntry.kind == "procedure",
                    DermaHistoryEntry.source == "emr",
                    DermaHistoryEntry.record_id.in_(chunk),
                )
            )
            .scalars()
            .all()
        )
        stored_keys: dict[int, set[tuple]] = {rid: set() for rid in chunk}
        for srow in stored:
            key = (srow.kind, srow.source, srow.record_id, srow.position)
            stored_keys.setdefault(srow.record_id, set()).add(key)
            expected = by_record.get(srow.record_id, {}).get(key)
            if expected is None:
                result["mismatches"].append(
                    {"record_id": srow.record_id, "issue": "extra_row",
                     "identity": list(key)}
                )
            elif json.dumps(srow.payload, sort_keys=True, ensure_ascii=False,
                            default=str) != json.dumps(
                    expected.get("payload", expected), sort_keys=True,
                    ensure_ascii=False, default=str):
                result["mismatches"].append(
                    {"record_id": srow.record_id, "issue": "payload_mismatch",
                     "identity": list(key)}
                )
        chunk_set = set(chunk)
        for rid, expected_map in by_record.items():
            if rid not in chunk_set:
                continue
            for key in expected_map:
                if key not in stored_keys.get(rid, set()):
                    result["mismatches"].append(
                        {"record_id": rid, "issue": "missing_row",
                         "identity": list(key)}
                    )
    return result


def cmd_audit(args: argparse.Namespace) -> int:
    url = resolve_url(args)
    print("Phase B audit | цель: %s (READ-ONLY)" % mask_url(url))
    bootstrap_backend()
    engine = make_readonly_engine(url)
    with Session(engine) as session:
        derma, non_derma, emr_total = scan_records(session)
        with_legacy = [r for r in derma if r["legacy"]["present"]]
        active_with_legacy = [r for r in with_legacy if r["is_active"]]
        # паритет только для активных: listener/backfill не проецируют
        # неактивные записи (is_active=False)
        alias_records = [
            r for r in derma if r["legacy"]["valid"] > 0 and r["is_active"]
        ]
        proj = projection_alias_check(session, alias_records)

    counts = {c: 0 for c in CLASSIFICATIONS}
    for r in derma:
        counts[r["classification"]] += 1

    print()
    print("EMR всего: %d; дерма с ключами процедур: %d" % (emr_total, len(derma)))
    print("Классификация: " + ", ".join("%s=%d" % kv for kv in counts.items()))
    print("Legacy-ключ (любое значение): %d записей, из них активных: %d"
          % (len(with_legacy), len(active_with_legacy)))
    print("Неактивные с legacy: %d (не проецируются; решение владельца)"
          % (len(with_legacy) - len(active_with_legacy)))
    signed_with_legacy = [r for r in active_with_legacy if r["status"] == "signed"]
    print("Подписанные с legacy (нормализация через amend): %d"
          % len(signed_with_legacy))
    if non_derma:
        print("ВНИМАНИЕ: legacy-ключ в НЕ-дерма ЭМК: %d записей (вне скоупа "
              "дерма-проекции; см. артефакт)" % len(non_derma))
    exact_dup = [r for r in derma if r["exact_matches"]]
    print("Double-write (точные совпадения canonical==legacy): %d записей"
          % len(exact_dup))
    date_dup = [r for r in derma if r["date_type_matches"]]
    print("Возможные дубликаты (same type+date, разное наполнение): %d записей"
          % len(date_dup))
    print("Read-модель (procedure/emr) для записей с legacy: проверено %d, "
          "расхождений %d" % (proj["checked_records"], len(proj["mismatches"])))

    print()
    print("== Записи с legacy-ключом (активные) ==")
    # числовые суррогатные id (record/visit/patient) и счётчики, без
    # PHI-полей — политика derma.py #1321 / patient_service.py #1295
    for r in sorted(active_with_legacy, key=lambda x: x["record_id"]):
        print(  # codeql[py/clear-text-logging-sensitive-data]
            "  EMR #%d visit=%s patient=%s status=%s class=%s "
            "canon(valid/invalid)=%d/%d legacy(valid/invalid)=%d/%d "
            "exact=%d date=%d"
            % (
                r["record_id"], r["visit_id"], r["patient_id"], r["status"],
                r["classification"],
                r["canonical"]["valid"], r["canonical"]["invalid"],
                r["legacy"]["valid"], r["legacy"]["invalid"],
                len(r["exact_matches"]), len(r["date_type_matches"]),
            )
        )
    if not active_with_legacy:
        print("  (нет — Phase B нормализация не требуется)")

    artifact = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": mask_url(url),
        "totals": {
            "emr_records": emr_total,
            "derma_with_procedure_keys": len(derma),
            "classification_counts": counts,
            "with_legacy": len(with_legacy),
            "active_with_legacy": len(active_with_legacy),
            "signed_active_with_legacy": len(signed_with_legacy),
        },
        "records": derma,
        "non_derma_with_legacy_key": non_derma,
        "projection_check": proj,
        "normalize_hint": {
            "append": sorted(
                r["record_id"] for r in active_with_legacy
                if r["classification"] in ("legacy_only", "both_disjoint")
            ),
            "drop_legacy_lossless": sorted(
                r["record_id"] for r in active_with_legacy
                if r["classification"] == "both_subset"
            ),
            "needs_manual_review": sorted(
                r["record_id"] for r in active_with_legacy
                if r["classification"] in ("both_partial", "none")
                or r["legacy"]["type_anomaly"]
            ),
        },
    }
    out_path = Path(args.out) if args.out else Path(
        "derma_legacy_procedures_audit_%s.json"
        % datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    # артефакт аудита НАМЕРЕННО содержит клинические данные (id записей
    # и процедуры) — это предмет ревью владельца Phase B; пишется в
    # локальную ФС оператора на хосте БД (тот же домен доверия, что сама
    # БД и её pg_dump-бэкапы), наружу не передаётся
    out_path.write_text(  # codeql[py/clear-text-storage-of-sensitive-information]
        json.dumps(artifact, ensure_ascii=False, indent=1, default=str),
        encoding="utf-8",
    )
    print()
    print("Артефакт: %s" % out_path)
    print("Следующий шаг: ревью артефакта владельцем, затем normalize "
          "(dry-run -> --apply).")
    return 0


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------


def build_normalized_data(
    record: Any, strategy: str, skip_exact: bool = False
) -> tuple[dict, dict]:
    """new_data + план изменений для одной записи.

    append: валидные legacy-записи дописываются в конец canonical,
            legacy-ключ удаляется; invalid-legacy-записи покидают живую
            запись (полностью сохранены в предыдущей ревизии EMRRevision
            и в артефакте аудита). С --skip-exact-duplicates legacy-записи,
            ТОЧНО совпадающие с уже существующей canonical-записью, не
            дублируются (данные уже в canonical дословно; решение об
            эквивалентности принимает оператор по артефакту аудита,
            где совпадения перечислены).
    drop-legacy: legacy-ключ удаляется без переноса (осознанная потеря
            только если валидные legacy-записи не имеют точного совпадения
            в canonical — см. --confirm-data-loss).
    """
    data = deepcopy(record.data if isinstance(record.data, dict) else {})
    specialty_data = data.get("specialty_data")
    specialty_data = specialty_data if isinstance(specialty_data, dict) else {}
    inv = classify_record(specialty_data)
    canonical_raw = specialty_data.get(CANONICAL_KEY)
    canonical = list(canonical_raw) if isinstance(canonical_raw, list) else []
    legacy_valid = inv["legacy_valid_entries"]
    legacy_invalid = inv["legacy_invalid_entries"]

    plan = {
        "strategy": strategy,
        "move_valid": 0,
        "skip_exact": 0,
        "drop_valid_unmatched": 0,
        "drop_invalid": len(legacy_invalid),
        "path": "amend" if record.status == "signed" else "update",
        "status_change": "signed -> amended" if record.status == "signed" else None,
    }
    if strategy == "append":
        to_move = legacy_valid
        if skip_exact:
            matched = {li for _, li in inv["exact_matches"]}
            to_move = [
                e for li, e in enumerate(legacy_valid) if li not in matched
            ]
            plan["skip_exact"] = len(legacy_valid) - len(to_move)
        canonical = canonical + to_move
        plan["move_valid"] = len(to_move)
    else:  # drop-legacy
        matched = {li for _, li in inv["exact_matches"]}
        plan["drop_valid_unmatched"] = len(legacy_valid) - len(matched)
    specialty_data = dict(specialty_data)
    specialty_data[CANONICAL_KEY] = canonical
    specialty_data.pop(LEGACY_KEY, None)
    data["specialty_data"] = specialty_data
    return data, plan


def cmd_normalize(args: argparse.Namespace) -> int:
    url = resolve_url(args)
    ids = [int(x) for x in re.split(r"[,\s]+", args.record_ids.strip()) if x]
    if not ids:
        sys.exit("--record-ids пуст: укажите id записей из артефакта аудита.")
    if args.strategy == "drop-legacy" and args.confirm_data_loss is None:
        # допустимо без флага, только если потерь нет — проверим по ходу
        pass
    if args.skip_exact_duplicates and args.strategy != "append":
        sys.exit("--skip-exact-duplicates применим только к --strategy append.")
    print("Phase B normalize | цель: %s | стратегия=%s | записей=%d | %s"
          % (mask_url(url), args.strategy, len(ids),
             "APPLY (запись)" if args.apply else "DRY-RUN (без записи)"))
    bootstrap_backend()
    from app.models.emr_v2 import EMRRecord
    from app.services.derma_history_projection import is_dermatology_emr
    from app.services.emr_v2_service import (
        ConcurrencyError,
        EMRSignedError,
        emr_v2_service,
    )

    engine = make_readwrite_engine(url)
    results: list[dict] = []

    for rid in ids:
        with Session(engine) as session:
            record = session.get(EMRRecord, rid)
            if record is None:
                results.append({"record_id": rid, "result": "error",
                                "note": "запись не найдена"})
                continue
            inv = classify_record(
                (record.data or {}).get("specialty_data")
            )
            if not inv["legacy"]["present"]:
                results.append({"record_id": rid, "result": "already_clean",
                                "note": "legacy-ключ отсутствует (идемпотентно)"})
                continue
            if not is_dermatology_emr(record):
                results.append({"record_id": rid, "result": "error",
                                "note": "не дерма-ЭМК (specialty != dermatology)"})
                continue
            if not record.is_active:
                results.append({"record_id": rid, "result": "error",
                                "note": "запись неактивна (is_active=False); "
                                        "нормализация неактивных — отдельное "
                                        "решение владельца"})
                continue
            new_data, plan = build_normalized_data(
                record, args.strategy, args.skip_exact_duplicates
            )
            if (
                args.strategy == "drop-legacy"
                and plan["drop_valid_unmatched"] > 0
                and not args.confirm_data_loss
            ):
                results.append({
                    "record_id": rid, "result": "refused",
                    "note": "drop-legacy удаляет %d валидных legacy-записей "
                            "без точного совпадения в canonical; требуется "
                            "--confirm-data-loss" % plan["drop_valid_unmatched"],
                })
                continue
            plan["new_version"] = record.version + 1
            plan["row_version_used"] = record.row_version
            if not args.apply:
                results.append({"record_id": rid, "result": "planned", "plan": plan})
                continue
            try:
                if record.status == "signed":
                    reason = args.reason or (
                        "Phase B (P3 #3490/#3491): перенос косметологических "
                        "процедур из legacy-ключа specialty_data.procedures в "
                        "канонический cosmetic_procedures"
                    )
                    emr_v2_service.amend(
                        session,
                        visit_id=record.visit_id,
                        data=new_data,
                        reason=reason,
                        user_id=args.user_id,
                        row_version=record.row_version,
                    )
                else:
                    emr_v2_service._update_emr(  # noqa: SLF001 — см. docstring
                        session,
                        record,
                        new_data,
                        args.user_id,
                        record.row_version,
                        client_session_id=SESSION_MARKER,
                        is_draft=True,
                        change_type="migrated",
                        change_summary_override=(
                            "Phase B (P3 #3490/#3491): legacy "
                            "specialty_data.procedures -> cosmetic_procedures "
                            "(strategy=%s, moved=%d, skip_exact=%d, "
                            "dropped_invalid=%d)"
                            % (args.strategy, plan["move_valid"],
                               plan["skip_exact"], plan["drop_invalid"])
                        ),
                        audit_action="update",
                    )
                results.append({"record_id": rid, "result": "ok", "plan": plan})
            except (ConcurrencyError, EMRSignedError, ValueError) as exc:
                session.rollback()
                results.append({"record_id": rid, "result": "error",
                                "note": "%s: %s" % (type(exc).__name__, exc)})
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                results.append({"record_id": rid, "result": "error",
                                "note": "%s: %s" % (type(exc).__name__, exc)})

    ok = sum(1 for r in results if r["result"] in ("ok", "already_clean", "planned"))
    refused = [r for r in results if r["result"] == "refused"]
    errors = [r for r in results if r["result"] == "error"]
    print()
    for r in results:
        if r["result"] == "planned":
            p = r["plan"]
            print("  EMR #%d PLANNED (%s%s): move=%d skip_exact=%d "
                  "drop_invalid=%d unmatched_drop=%d version->%d"
                  % (r["record_id"], p["path"],
                     " статус подписанного изменится: " + p["status_change"]
                     if p.get("status_change") else "",
                     p["move_valid"], p["skip_exact"],
                     p["drop_invalid"], p["drop_valid_unmatched"],
                     p["new_version"]))
        elif r["result"] == "ok":
            p = r["plan"]
            print("  EMR #%d OK (%s): move=%d skip_exact=%d drop_invalid=%d "
                  "version->%d"
                  % (r["record_id"], p["path"], p["move_valid"],
                     p["skip_exact"], p["drop_invalid"], p["new_version"]))
        else:
            print("  EMR #%d %s: %s" % (r["record_id"], r["result"].upper(),
                                        r.get("note", "")))
    print()
    print("Итог: ok=%d refused=%d error=%d (%s)"
          % (ok, len(refused), len(errors),
             "APPLY" if args.apply else "DRY-RUN"))
    if errors or refused:
        return 1
    if args.apply:
        print("Следующий шаг: verify (Phase C gate).")
    else:
        print("Это был dry-run. Для записи повторите с --apply.")
    return 0


# ---------------------------------------------------------------------------
# verify (Phase C gate)
# ---------------------------------------------------------------------------


def cmd_verify(args: argparse.Namespace) -> int:
    url = resolve_url(args)
    print("Phase C gate | цель: %s (READ-ONLY)" % mask_url(url))
    bootstrap_backend()
    engine = make_readonly_engine(url)
    failures: list[str] = []
    with Session(engine) as session:
        derma, _non_derma, _total = scan_records(session)
        active_with_legacy = [
            r for r in derma if r["legacy"]["present"] and r["is_active"]
        ]
        inactive_with_legacy = [
            r for r in derma if r["legacy"]["present"] and not r["is_active"]
        ]
        # 1) активные дерма-ЭМК не содержат legacy-ключ (даже пустой список)
        if active_with_legacy:
            failures.append(
                "legacy-ключ ещё жив в %d активных дерма-ЭМК: %s"
                % (len(active_with_legacy),
                   sorted(r["record_id"] for r in active_with_legacy)[:20])
            )
        else:
            print("  [1/2] legacy-ключ в активных дерма-ЭМК отсутствует: OK")
        # 2) паритет procedure-строк read-модели (emr + legacy источники)
        from app.models.derma_history import DermaHistoryEntry
        from app.models.derma_procedure import DermaProcedure
        from app.models.emr_v2 import EMRRecord
        from app.services.derma_history_projection import (
            _visit_map_for_records,
            emr_entry_dicts,
            legacy_procedure_entry_dicts,
        )

        expected: dict[tuple, dict] = {}
        cursor = 0
        derma_rows: list[Any] = []
        while True:
            rows = (
                session.execute(
                    sa.select(EMRRecord)
                    .where(EMRRecord.__table__.c.id > cursor)
                    .order_by(EMRRecord.__table__.c.id)
                    .limit(BATCH)
                )
                .scalars()
                .all()
            )
            if not rows:
                break
            cursor = rows[-1].id
            for r in rows:
                data = r.data if isinstance(r.data, dict) else {}
                if r.is_active and data.get("specialty") == "dermatology":
                    derma_rows.append(r)
        for i in range(0, len(derma_rows), BATCH):
            chunk = derma_rows[i:i + BATCH]
            visits = _visit_map_for_records(session, chunk)
            for entry in emr_entry_dicts(chunk, visits):
                if entry["kind"] != "procedure":
                    continue
                key = tuple(
                    entry[f] for f in ("kind", "source", "record_id", "position")
                )
                expected[key] = entry
        legacy_rows = (
            session.execute(sa.select(DermaProcedure.__table__)).all()
        )
        for entry in legacy_procedure_entry_dicts(legacy_rows):
            key = tuple(
                entry[f] for f in ("kind", "source", "record_id", "position")
            )
            expected[key] = entry
        stored = (
            session.execute(
                sa.select(DermaHistoryEntry).where(
                    DermaHistoryEntry.kind == "procedure"
                )
            )
            .scalars()
            .all()
        )
        stored_map = {
            (s.kind, s.source, s.record_id, s.position): s for s in stored
        }
        missing = [k for k in expected if k not in stored_map]
        extra = [k for k in stored_map if k not in expected]
        payload_mismatch = []
        for key, entry in expected.items():
            srow = stored_map.get(key)
            if srow is None:
                continue
            if json.dumps(srow.payload, sort_keys=True, ensure_ascii=False,
                          default=str) != json.dumps(
                    entry.get("payload", entry), sort_keys=True,
                    ensure_ascii=False, default=str):
                payload_mismatch.append(key)
        if missing or extra or payload_mismatch:
            failures.append(
                "паритет procedure-строк: missing=%d extra=%d payload=%d"
                % (len(missing), len(extra), len(payload_mismatch))
            )
        else:
            print("  [2/2] паритет procedure-строк read-модели "
                  "(%d строк): OK" % len(expected))

    if inactive_with_legacy:
        print("  INFO: legacy-ключ остался в %d НЕАКТИВНЫХ дерма-ЭМК "
              "(не проецируются; вне Phase C gate): %s"
              % (len(inactive_with_legacy),
                 sorted(r["record_id"] for r in inactive_with_legacy)[:20]))
    if failures:
        print()
        for f in failures:
            print("FAIL: %s" % f)
        print()
        print("Phase C gate: КРАСНЫЙ (см. FAIL выше).")
        return 1
    print()
    print("Phase C gate: ЗЕЛЁНЫЙ — можно готовить удаление legacy alias.")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def add_target_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--env-file", type=Path, default=REPO_ROOT / "backend" / ".env",
        help="backend/.env с DATABASE_URL (по умолчанию: %(default)s)",
    )
    parser.add_argument(
        "--database-url", default=None,
        help="явная цель (приоритет над --env-file)",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase B (P3 #3490/#3491): аудит/нормализация legacy-ключа "
                    "specialty_data.procedures дерма-ЭМК",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_audit = sub.add_parser(
        "audit", help="READ-ONLY inventory + double-write анализ + кросс-чек "
                      "read-модели; JSON-артефакт для ревью",
    )
    add_target_args(p_audit)
    p_audit.add_argument("--out", default=None,
                         help="путь JSON-артефакта (по умолчанию — файл с "
                              "UTC-таймстампом в текущем каталоге)")
    p_audit.set_defaults(func=cmd_audit)

    p_norm = sub.add_parser(
        "normalize", help="перенос legacy-записей в canonical ключ через "
                          "стандартный путь записи (dry-run по умолчанию)",
    )
    add_target_args(p_norm)
    p_norm.add_argument("--record-ids", required=True,
                        help="id EMR-записей через запятую (из артефакта аудита)")
    p_norm.add_argument("--strategy", choices=["append", "drop-legacy"],
                        default="append",
                        help="append: валидные legacy дописываются в canonical "
                             "(без потерь); drop-legacy: legacy-ключ удаляется "
                             "без переноса")
    p_norm.add_argument("--user-id", type=int, required=True,
                        help="id оператора для ревизии/аудита (0 = системный)")
    p_norm.add_argument("--reason", default=None,
                        help="reason для amend подписанных записей (>=10 симв.; "
                             "по умолчанию — стандартная формулировка Phase B)")
    p_norm.add_argument("--apply", action="store_true",
                        help="выполнить запись (без флага — dry-run)")
    p_norm.add_argument("--skip-exact-duplicates", action="store_true",
                        help="(только append) не дописывать legacy-записи, "
                             "уже дословно присутствующие в canonical "
                             "(совпадения перечислены в артефакте аудита)")
    p_norm.add_argument("--confirm-data-loss", action="store_true",
                        help="подтверждение удаления валидных legacy-записей "
                             "без точного совпадения в canonical "
                             "(только для drop-legacy)")
    p_norm.set_defaults(func=cmd_normalize)

    p_verify = sub.add_parser(
        "verify", help="READ-ONLY Phase C gate: legacy-ключ исчез из активных "
                       "дерма-ЭМК + паритет procedure-строк read-модели",
    )
    add_target_args(p_verify)
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
