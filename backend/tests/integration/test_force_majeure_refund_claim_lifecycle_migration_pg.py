"""3808 round 5 (#3809 P1) — claim lifecycle vs. request status: migration proof.

Runtime-покрытие цикла «pending -> rejected -> повторный возврат» живёт в
gate_d-модуле сериализации; ЭТОТ модуль доказывает МИГРАЦИОННУЮ половину
фикса на реальной цепочке alembic (PostgreSQL):

  * мир до 0087/0088 (``alembic upgrade 0086_public_booking_confirm``):
    один платёж с ОТКЛОНЁННОЙ автоматической заявкой, один с pending,
    один с completed, один с депозитным кредитом;
  * ``alembic upgrade head`` прогоняет amended 0087 (статус-зависимый
    частичный индекс) + amended 0088 (статус-зависимый backfill);
  * backfill: rejected НЕ занимает claim (платёж остаётся доступен для
    повторного возврата после rollout), pending/completed/credit —
    занимают ровно одним claim-ом правильного канала;
  * amended 0087 на уровне БД: повторная автоматическая заявка после
    rejected вставляется; второй живой статус по тому же платежу —
    unique violation по ``uq_refund_requests_auto_payment``; completed
    держит уникальность так же строго, как и раньше;
  * RLS на ``payment_refund_claims`` включён (public-schema guardrail).

3808 round 6 (#3809 P1 shared-db drop) — работа со scratch-базой больше
не может задеть чужие данные:

  * админ-подключение допускается ТОЛЬКО к локальному кластеру
    (localhost/127.0.0.1/::1); явный ``PG_ADMIN_URL`` на общий/удалённый
    сервер отвергается ДО любой DDL (в CI — громкий fail, локально —
    skip). Подстрока ``test`` в имени базы НЕ считается доказательством
    одноразовой цели: имя базы вообще не участвует в решении об удалении;
  * scratch-база получает случайное одноразовое имя
    ``clinic_test_fm_claim_<uuid12>`` — параллельные запуски не
    пересекаются, preemptive ``DROP DATABASE IF EXISTS`` убран полностью;
  * убирается ТОЛЬКО база, созданная этим запуском (флаг ``created`` +
    ``_assert_drop_db_safe``): коллизия имён лечится skip-ом, а не
    удалением чужой базы.

Паттерн — зеркало test_queue_resource_sentinel_retirement full-chain
пруфа: свежая scratch-база, alembic-сабпроцессы, skip без одноразового
PostgreSQL (в CI backend-tests job его предоставляет сервис-контейнер).
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"

pytestmark = [pytest.mark.integration, pytest.mark.migration]

# 3808 review round 6 (P1 shared-db drop): одноразовое пространство имён
# scratch-баз этого модуля; имя + uuid12 (ср. fm_gate_d_<uuid> из gate_d).
_SCRATCH_DB_PREFIX = "clinic_test_fm_claim_"

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

# Единый перечень служебных/чужих имён, которые этот модуль не имеет
# права удалять НИКОГДА (ремень поверх ремня перед единственной
# деструктивной DDL — зеркало _assert_drop_safe из gate_d).
_DROP_FORBIDDEN_NAMES = {
    "postgres",
    "template0",
    "template1",
    "clinicdb",
    "clinic_test",
    "prod_like",
}


def _admin_url_is_disposable(url: str) -> bool:
    """Строгая валидация ADMIN-подключения (3808 round 6, P1 shared-db drop).

    Допускаются только ЛОКАЛЬНЫЕ кластеры (localhost/127.0.0.1/::1):
    произвольный ``PG_ADMIN_URL`` на общий или удалённый сервер — источник
    сценария ревью (DROP DATABASE по фиксированному имени на shared
    сервере / при параллельных запусках). Имя базы в admin URL НЕ является
    доказательством одноразовой цели: решение об удалении принимается
    только по флагу ``created`` (базу создал ЭТОТ запуск) и по
    ``_assert_drop_db_safe`` — подстрока ``test`` ни о чём не говорит.
    """
    try:
        u = make_url(url)
    except Exception:  # noqa: BLE001 - невалидируемый URL == не-одноразовая цель
        return False
    return (u.host or "") in _LOCAL_HOSTS


def _refuse_nondisposable_admin_url() -> None:
    """Явный ``PG_ADMIN_URL`` проверяется до любой DDL: общий/удалённый
    сервер отвергается целиком (в CI покрытие не должно молча исчезать —
    громкий fail; локально — skip с объяснением)."""
    explicit = os.environ.get("PG_ADMIN_URL", "").strip()
    if not explicit or _admin_url_is_disposable(explicit):
        return
    message = (
        "migration proof отказывается работать с PG_ADMIN_URL, который не"
        " является локальным кластером (host не localhost/127.0.0.1/::1)."
        " Укажите одноразовый локальный кластер или снимите переменную —"
        " модуль сам найдёт локального кандидата."
    )
    if os.environ.get("CI") == "true":
        pytest.fail(message)
    pytest.skip(message)


def _one_off_scratch_db() -> str:
    """Случайное одноразовое имя scratch-базы: параллельные запуски не
    пересекаются, а preemptive DROP чужой базы с совпавшим именем
    становится невозможен по построению (uuid12)."""
    return f"{_SCRATCH_DB_PREFIX}{uuid.uuid4().hex[:12]}"


def _assert_drop_db_safe(name: str) -> None:
    """Ремень поверх ремня прямо перед ЕДИНСТВЕННОЙ деструктивной DDL
    модуля: удаляться может только база, сгенерированная этим запуском."""
    assert name.startswith(_SCRATCH_DB_PREFIX), name
    assert len(name) == len(_SCRATCH_DB_PREFIX) + 12, name
    assert name not in _DROP_FORBIDDEN_NAMES, name
    assert not name.startswith("pg_"), name


def _candidate_admin_urls() -> list[str]:
    """Одноразовые ЛОКАЛЬНЫЕ admin-подключения (порядок как в sentinel
    full-chain); не-локальные кандидаты отсеиваются до коннекта."""
    urls: list[str] = []
    explicit = os.environ.get("PG_ADMIN_URL", "").strip()
    if explicit and _admin_url_is_disposable(explicit):
        urls.append(explicit)

    env_url = os.environ.get("DATABASE_URL", "").strip()
    if env_url:
        u = make_url(env_url)
        if (u.host or "") in _LOCAL_HOSTS:
            derived = (
                f"postgresql://{u.username or ''}"
                f":{u.password or ''}@{u.host}:{u.port or 5432}/postgres"
            )
            if _admin_url_is_disposable(derived):
                urls.append(derived)

    # the portable zonky server used by local sessions (trust auth)
    zonky = "postgresql://postgres@127.0.0.1:55432/postgres"
    if _admin_url_is_disposable(zonky):
        urls.append(zonky)
    return urls


def _alembic(sa_url: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, DATABASE_URL=sa_url, TESTING="1")
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        capture_output=True,
        text=True,
        cwd=str(BACKEND_ROOT),
        env=env,
        timeout=600,
    )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # локальные кластеры — допускаются
        ("postgresql://postgres@127.0.0.1:55432/postgres", True),
        ("postgresql://clinic:clinic_ci_only_password@localhost:5432/postgres", True),
        ("postgresql://postgres@[::1]:5432/postgres", True),
        # удалённые/общие серверы — отвергаются, ВКЛЮЧАЯ случаи, когда имя
        # базы выглядит «тестовым»: подстрока test не доказывает одноразовость
        ("postgresql://owner@10.0.0.5:5432/postgres", False),
        ("postgresql://owner@db.internal.example:5432/postgres", False),
        ("postgresql://owner@prod.internal:5432/clinic_test", False),
        ("postgresql://owner@prod.internal:5432/test_db", False),
        # невалидируемые значения
        ("not a url at all", False),
        ("", False),
    ],
)
def test_admin_url_must_be_local_before_any_ddl(url: str, expected: bool) -> None:
    """3808 round 6 (P1 shared-db drop): guard-функция допускает только
    локальные admin-подключения и НЕ доверяет «тестовому» имени базы."""
    assert _admin_url_is_disposable(url) is expected


def test_0088_backfill_skips_rejected_and_amended_0087_allows_retry() -> None:
    # 3808 review round 6 (P1 shared-db drop): до любой DDL — строгая
    # проверка ЯВНОГО admin-подключения (только локальные кластеры).
    _refuse_nondisposable_admin_url()

    admin_url = None
    for candidate in _candidate_admin_urls():
        try:
            with psycopg.connect(candidate, connect_timeout=3, autocommit=True) as c:
                c.execute("SELECT 1")
            admin_url = candidate
            break
        except Exception:  # noqa: BLE001 - try the next disposable candidate
            continue
    if admin_url is None:
        pytest.skip("disposable local PostgreSQL unavailable — migration proof NOT_RUN")

    # 3808 review round 6 (P1 shared-db drop): случайное одноразовое имя
    # вместо фиксированного; БЕЗ preemptive DROP (чужая база с тем же
    # именем — параллельный/прошлый запуск — не удаляется); уборка в
    # finally — ТОЛЬКО базы, созданной этим запуском (флаг created).
    scratch_db = _one_off_scratch_db()
    created = False
    try:
        with psycopg.connect(admin_url, autocommit=True) as c:
            try:
                c.execute(f'CREATE DATABASE "{scratch_db}"')
                created = True
            except psycopg.errors.DuplicateDatabase:
                # коллизия имён практически невозможна (uuid12), но даже
                # тогда чужая база НЕ удаляется — тест отказывается дальше
                pytest.skip(
                    f"scratch database name collision ({scratch_db});"
                    " refusing to touch a database this run did not create"
                )

        u = make_url(admin_url)
        # render_as_string(hide_password=False): plain str(URL) masks the
        # password as *** (SQLAlchemy 2.0) and the alembic subprocess would
        # authenticate with literal asterisks (the sentinel full-chain lesson).
        sa_url = (
            u.set(drivername="postgresql+psycopg", database=scratch_db)
            .render_as_string(hide_password=False)
        )

        # ---- 1) мир ДО 0087/0088 --------------------------------------
        result = _alembic(sa_url, "upgrade", "0086_public_booking_confirm")
        assert result.returncode == 0, (
            f"alembic upgrade 0086 failed:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )

        engine = sa.create_engine(sa_url, future=True)
        try:
            with engine.begin() as conn:
                patient_id = conn.execute(
                    sa.text(
                        "INSERT INTO patients (last_name, first_name, birth_date,"
                        " gender, is_deleted, created_at)"
                        " VALUES ('Легаси', 'Клейм', '1990-01-01', 'M', false, now())"
                        " RETURNING id"
                    )
                ).scalar_one()
                visit_id = conn.execute(
                    sa.text(
                        "INSERT INTO visits (patient_id, visit_date, department,"
                        " discount_mode, approval_status, status, source, created_at)"
                        " VALUES (:p, current_date, 'cardiology_common', 'none',"
                        " 'approved', 'open', 'desk', now()) RETURNING id"
                    ),
                    {"p": patient_id},
                ).scalar_one()

                def _payment() -> int:
                    return conn.execute(
                        sa.text(
                            "INSERT INTO payments (visit_id, amount, currency,"
                            " method, status, created_at)"
                            " VALUES (:v, 100, 'UZS', 'cash', 'paid', now()) RETURNING id"
                        ),
                        {"v": visit_id},
                    ).scalar_one()

                pay_rejected, pay_pending, pay_completed, pay_credit = (
                    _payment(),
                    _payment(),
                    _payment(),
                    _payment(),
                )

                def _auto_request(payment_id: int, status: str) -> int:
                    return conn.execute(
                        sa.text(
                            "INSERT INTO refund_requests (patient_id, payment_id,"
                            " original_amount, refund_amount, commission_amount,"
                            " refund_type, status, reason, is_automatic, created_at)"
                            " VALUES (:p, :pay, 100, 100, 0, 'bank_transfer', :st,"
                            " :reason, true, now()) RETURNING id"
                        ),
                        {
                            "p": patient_id,
                            "pay": payment_id,
                            "st": status,
                            "reason": f"pre-0088 {status} leg",
                        },
                    ).scalar_one()

                request_rejected = _auto_request(pay_rejected, "rejected")
                request_pending = _auto_request(pay_pending, "pending")
                _auto_request(pay_completed, "completed")

                deposit_id = conn.execute(
                    sa.text(
                        "INSERT INTO patient_deposits (patient_id, balance, currency,"
                        " max_balance, is_active)"
                        " VALUES (:p, 100, 'UZS', 10000000, true) RETURNING id"
                    ),
                    {"p": patient_id},
                ).scalar_one()
                conn.execute(
                    sa.text(
                        "INSERT INTO deposit_transactions (deposit_id,"
                        " transaction_type, amount, balance_after, payment_id)"
                        " VALUES (:d, 'credit', 100, 100, :pay)"
                    ),
                    {"d": deposit_id, "pay": pay_credit},
                )
        finally:
            engine.dispose()

        # ---- 2) прогоняем amended 0087 + 0088 --------------------------
        result = _alembic(sa_url, "upgrade", "head")
        assert result.returncode == 0, (
            f"alembic upgrade head failed:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )

        engine = sa.create_engine(sa_url, future=True)
        try:
            with engine.connect() as conn:
                version = conn.execute(
                    sa.text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                assert version == "0088_fm_refund_claim", version

                def _claims(payment_id: int) -> list[tuple]:
                    return conn.execute(
                        sa.text(
                            "SELECT channel, refund_request_id, deposit_transaction_id"
                            " FROM payment_refund_claims WHERE payment_id = :p"
                            " ORDER BY id"
                        ),
                        {"p": payment_id},
                    ).fetchall()

                # backfill: rejected НЕ занял платёж (round 5, P1)
                assert _claims(pay_rejected) == [], _claims(pay_rejected)
                # pending занят ровно одним claim-ом своего канала
                pending_claims = _claims(pay_pending)
                assert len(pending_claims) == 1, pending_claims
                assert pending_claims[0][0] == "refund_request"
                assert pending_claims[0][1] == request_pending
                # completed (деньги вернули) занят строго
                completed_claims = _claims(pay_completed)
                assert len(completed_claims) == 1, completed_claims
                assert completed_claims[0][0] == "refund_request"
                # депозитный кредит занят своим каналом
                credit_claims = _claims(pay_credit)
                assert len(credit_claims) == 1, credit_claims
                assert credit_claims[0][0] == "deposit"

                rls = conn.execute(
                    sa.text(
                        "SELECT c.relrowsecurity FROM pg_class c"
                        " JOIN pg_namespace n ON n.oid = c.relnamespace"
                        " WHERE n.nspname = 'public'"
                        " AND c.relname = 'payment_refund_claims'"
                    )
                ).scalar_one()
                assert rls is True, "payment_refund_claims must have RLS enabled"
                conn.rollback()

            # ---- 3) amended 0087: retry после rejected возможен ----------
            with engine.begin() as conn:
                retry_id = conn.execute(
                    sa.text(
                        "INSERT INTO refund_requests (patient_id, payment_id,"
                        " original_amount, refund_amount, commission_amount,"
                        " refund_type, status, reason, is_automatic, created_at)"
                        " VALUES (:p, :pay, 100, 100, 0, 'bank_transfer', 'pending',"
                        " 'corrected details retry', true, now()) RETURNING id"
                    ),
                    {"p": patient_id, "pay": pay_rejected},
                ).scalar_one()
            assert retry_id > 0

            # ---- 4) amended 0087: живые статусы уникальны ----------------
            for payment_id, label in (
                (pay_pending, "second live request for a pending payment"),
                (pay_completed, "live request for a completed (paid) payment"),
            ):
                with pytest.raises(sa.exc.IntegrityError) as exc_info:
                    with engine.begin() as conn:
                        conn.execute(
                            sa.text(
                                "INSERT INTO refund_requests (patient_id, payment_id,"
                                " original_amount, refund_amount, commission_amount,"
                                " refund_type, status, reason, is_automatic, created_at)"
                                " VALUES (:p, :pay, 100, 100, 0, 'bank_transfer',"
                                " 'pending', 'must never persist', true, now())"
                            ),
                            {"p": patient_id, "pay": payment_id},
                        )
                constraint = getattr(
                    getattr(exc_info.value, "orig", None), "diag", None
                )
                constraint_name = (
                    constraint.constraint_name if constraint is not None else None
                ) or str(exc_info.value.orig)
                assert "uq_refund_requests_auto_payment" in str(constraint_name), (
                    f"{label}: expected the amended 0087 partial unique, got "
                    f"{constraint_name!r}"
                )
        finally:
            engine.dispose()
    finally:
        if created:
            # убирается ТОЛЬКО база, созданная этим запуском; имя
            # перепроверяется ремнём непосредственно перед DDL
            _assert_drop_db_safe(scratch_db)
            with psycopg.connect(admin_url, autocommit=True) as c:
                c.execute(f'DROP DATABASE IF EXISTS "{scratch_db}"')
