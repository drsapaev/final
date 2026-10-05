"""#3579 follow-up: телефон нового пациента не пишется в лог открытым текстом.

CodeQL clear-text-logging-sensitive-data (#1329 закрыт соседним PR на
success-логе постановки); остаток — строка регистрации НОВОГО пациента в
join_online_queue_multiple: ID + сырой телефон. Контракт после фикса:
в логе — только маскированный номер (app.core.pii_masker.mask_phone,
политика PII — виден хвост); в БД телефон сохраняется как прежде
(маскирование — только в логе).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, date
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.crud.online_queue import join_online_queue_multiple
from app.models.clinic import Doctor
from app.models.online_queue import OnlineQueueEntry, QueueToken


PHONE = "+998901234567"
MASKED = "+998901•••567"  # mask_phone: (\+\d{6})\d{3}(\d{3}) -> \1•••\2


@pytest.fixture
def join_setup(db_session):
    doctor = Doctor(specialty="cardiology", active=True)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    token = QueueToken(
        token=f"qr-{uuid4().hex[:16]}",
        day=date.today(),
        active=True,
        # Функция сравнивает с naive-локальным временем Asia/Tashkent.
        expires_at=datetime.now(ZoneInfo('Asia/Tashkent')).replace(tzinfo=None)
        + timedelta(hours=1),
        usage_count=0,
    )
    db_session.add(token)
    db_session.commit()
    db_session.refresh(token)
    return doctor, token


def test_new_patient_log_masks_phone(
    db_session, join_setup, queue_admission_open, caplog
):
    """Новый пациент: лог содержит маскированный телефон и НЕ содержит
    полный номер; постановка в очередь работает как прежде."""
    doctor, token = join_setup

    with caplog.at_level(logging.INFO, logger="app.crud.online_queue"):
        result = join_online_queue_multiple(
            db_session,
            token=token.token,
            specialist_ids=[doctor.id],
            phone=PHONE,
            patient_name="Синтетический Пациент Лога",
        )

    assert result["success"] is True, result
    assert result["errors"] in (None, [])

    patient_log_records = [
        record
        for record in caplog.records
        if "Создан новый пациент" in record.getMessage()
    ]
    assert len(patient_log_records) == 1, [
        record.getMessage() for record in patient_log_records
    ]
    message = patient_log_records[0].getMessage()
    assert MASKED in message, f"masked phone expected in log: {message!r}"
    assert PHONE not in message, f"full phone must never reach the log: {message!r}"

    # Маскирование — только в логе: в БД телефон сохранён как прежде,
    # чтобы повторный join по тому же телефону находил ту же запись.
    stored = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.phone == PHONE)
        .first()
    )
    assert stored is not None
    assert stored.phone == PHONE


def test_repeat_join_with_same_phone_stays_masked_and_dedupes(
    db_session, join_setup, queue_admission_open, caplog
):
    """Повторная постановка с тем же телефоном: дубликат по сырому номеру
    (dedupe-ветка), и строка 'Создан новый пациент' второй раз не пишется."""
    doctor, token = join_setup

    first = join_online_queue_multiple(
        db_session,
        token=token.token,
        specialist_ids=[doctor.id],
        phone=PHONE,
        patient_name="Синтетический Пациент Лога",
    )
    assert first["success"] is True

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="app.crud.online_queue"):
        second = join_online_queue_multiple(
            db_session,
            token=token.token,
            specialist_ids=[doctor.id],
            phone=PHONE,
            patient_name="Синтетический Пациент Лога",
        )

    assert second["success"] is True
    assert second["entries"][0]["duplicate"] is True
    assert not [
        record
        for record in caplog.records
        if "Создан новый пациент" in record.getMessage()
    ]
    assert all(PHONE not in record.getMessage() for record in caplog.records)


def test_new_patient_log_call_goes_through_mask_phone(
    db_session, join_setup, queue_admission_open, monkeypatch, caplog
):
    """Дискриминатор source-уровня: строка лога нового пациента обязана
    проходить через app.crud.online_queue.mask_phone. Глобальный
    PIIMaskingFilter маскирует и так (поэтому первые два теста зелёны и на
    base), но CodeQL флагит сам source-call — фикс на источнике обязателен.
    Сантинел без цифр: PIIMaskingFilter его не трогает."""
    doctor, token = join_setup
    sentinel_calls: list[str | None] = []

    def _sentinel_mask(phone: str | None) -> str | None:
        sentinel_calls.append(phone)
        return f"<MASKED-{len(phone or '')}>"

    monkeypatch.setattr("app.crud.online_queue.mask_phone", _sentinel_mask)

    with caplog.at_level(logging.INFO, logger="app.crud.online_queue"):
        result = join_online_queue_multiple(
            db_session,
            token=token.token,
            specialist_ids=[doctor.id],
            phone=PHONE,
            patient_name="Синтетический Пациент Лога",
        )

    assert result["success"] is True
    assert sentinel_calls == [
        PHONE
    ], "mask_phone must be called with the raw phone exactly once"
    patient_log_records = [
        record
        for record in caplog.records
        if "Создан новый пациент" in record.getMessage()
    ]
    assert len(patient_log_records) == 1
    assert "<MASKED-13>" in patient_log_records[0].getMessage(), patient_log_records[
        0
    ].getMessage()


def test_new_patient_log_failclosed_for_noncanonical_formats(
    db_session, join_setup, queue_admission_open, caplog
):
    """P2-1 (Codex): приклад допускает и хранит неканонические форматы
    телефона; mask_phone их не распознаёт — лог обязан быть fail-closed
    (никакого сырого номера, только хвост/скрытие)."""
    doctor, token = join_setup
    for phone in ("998901234567", "+998 90 123 45 67", "+998-90-123-45-67"):
        with caplog.at_level(logging.INFO, logger="app.crud.online_queue"):
            result = join_online_queue_multiple(
                db_session,
                token=token.token,
                specialist_ids=[doctor.id],
                phone=phone,
                patient_name="Синтетический Пациент Лога",
            )
        assert result["success"] is True, (phone, result)

        patient_log_records = [
            record
            for record in caplog.records
            if "Создан новый пациент" in record.getMessage()
        ]
        assert len(patient_log_records) == 1, (phone, caplog.records)
        message = patient_log_records[0].getMessage()
        assert phone not in message, f"raw phone leaked for {phone!r}: {message!r}"
        assert "•••" in message, f"fail-closed mask expected: {message!r}"
        db_session.rollback()
        caplog.clear()
