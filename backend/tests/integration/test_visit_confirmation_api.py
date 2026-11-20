"""
Интеграционные тесты для API подтверждения визитов
"""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.models.online_queue import OnlineQueueEntry
from app.models.telegram_config import TelegramUser
from app.models.visit import VisitService
from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
    build_telegram_visit_action_token,
)


@pytest.fixture(autouse=True)
def _future_telegram_start(monkeypatch):
    monkeypatch.setattr("app.tasks.worker._appointment_start_utc", lambda visit: datetime.now(UTC) + timedelta(days=1))


@pytest.fixture(autouse=True)
def _currency_for_positive_visit_fixture(request):
    if "test_visit" not in request.fixturenames:
        return
    visit = request.getfixturevalue("test_visit")
    db = request.getfixturevalue("db_session")
    token, expires_at = visit.confirmation_token, visit.confirmation_expires_at
    db.add(VisitService(visit_id=visit.id, service_id=123, name="SYNTHETIC",
                        price=Decimal("1.00"), qty=1, currency="UZS"))
    db.flush()
    db.refresh(visit)
    # A migrated trigger may invalidate the pre-existing synthetic bearer
    # when the service is added; mint the fixture bearer after that change.
    visit.confirmation_token, visit.confirmation_expires_at = token, expires_at
    db.commit()


def _link_patient_chat(db, visit):
    link = db.query(TelegramUser).filter_by(chat_id=123456789).first()
    if link is None:
        link = TelegramUser(chat_id=123456789)
        db.add(link)
    link.patient_id = visit.patient_id
    link.active = True
    link.blocked = False
    link.notifications_enabled = True
    link.appointment_reminders = True
    visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
    db.commit()
    return link


def _trusted_confirm(db, token, user_agent="telegram"):
    from app.models.visit import Visit

    visit = db.query(Visit).filter(Visit.confirmation_token == token).first()
    link = db.query(TelegramUser).filter_by(chat_id=123456789).first()
    if visit is not None and link is not None:
        token = build_telegram_visit_action_token(
            visit_id=visit.id, confirmation_token=token, link_id=link.id,
            chat_id=link.chat_id, patient_id=visit.patient_id,
            link_epoch=link.patient_link_epoch, visit_context_epoch=visit.confirmation_context_epoch,
        )
    return VisitConfirmationService(db).confirm_by_telegram(
        token=token, telegram_user_id="123456789", source_ip=None,
        user_agent=user_agent,
    )


@pytest.mark.integration
@pytest.mark.confirmation
class TestVisitConfirmationAPI:
    """Интеграционные тесты для API подтверждения визитов"""

    def test_dirty_same_session_is_not_silently_discarded(self, db_session, test_visit):
        test_visit.notes = "synthetic unflushed update"
        with pytest.raises(VisitConfirmationDomainError) as error:
            VisitConfirmationService(db_session).get_visit_info(test_visit.confirmation_token)
        assert error.value.status_code == 409
        assert test_visit.notes == "synthetic unflushed update"

    def test_get_visit_info_success(self, client, test_visit):
        """Тест получения информации о визите по токену"""
        response = client.get(f"/api/v1/visits/info/{test_visit.confirmation_token}")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["visit_id"] == test_visit.id
        assert data["patient_name"] == test_visit.patient.short_name()
        assert data["visit_date"] == test_visit.visit_date.isoformat()
        assert data["visit_time"] == test_visit.visit_time

    def test_get_visit_info_invalid_token(self, client):
        """Тест получения информации с недействительным токеном"""
        response = client.get("/api/v1/visits/info/invalid-token-123")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Визит не найден"

    def test_get_visit_info_expired_token(self, client, db_session, test_visit):
        """Тест получения информации с истекшим токеном"""
        # Устанавливаем время истечения в прошлом
        test_visit.confirmation_expires_at = datetime.utcnow() - timedelta(hours=1)
        db_session.flush()

        response = client.get(f"/api/v1/visits/info/{test_visit.confirmation_token}")

        assert response.status_code == 400
        data = response.json()
        assert "истек" in data["detail"]

    def test_post_visit_info_matches_legacy_get(self, client, db_session, test_visit):
        """The token moves to the request body; the card keeps its fields.

        PR 3407 delta review P2: BOTH the POST and the legacy GET are
        patient-safe now — the card is built without the internal
        ``notes`` field at the service level, so the two routes publish
        the identical shape.
        """
        token = test_visit.confirmation_token
        test_visit.notes = "diagnosis: private clinical note"
        db_session.flush()
        post_response = client.post("/api/v1/visits/info", json={"token": token})
        get_response = client.get(f"/api/v1/visits/info/{token}")

        assert post_response.status_code == get_response.status_code == 200
        assert post_response.json() == get_response.json()
        assert "notes" not in get_response.json()
        assert token not in post_response.request.url.path

    def test_post_visit_info_omits_internal_notes(self, client, db_session, test_visit):
        """PR 3390 review P2: the public POST card must not leak Visit.notes.

        ``Visit.notes`` carries clinical/admin text (the same marker the
        Telegram security tests keep off patient-facing messaging:
        "diagnosis: private clinical note", cancel reasons, force-reopen
        audit lines). The bearer-token confirmation card does not need it,
        so the POST response is a minimal patient-safe DTO without the
        field — even though the UI never renders it, any link holder could
        read it in the Network response.
        """
        test_visit.notes = "diagnosis: private clinical note"
        db_session.flush()
        response = client.post(
            "/api/v1/visits/info", json={"token": test_visit.confirmation_token}
        )

        assert response.status_code == 200
        assert "notes" not in response.json()
        assert "private clinical note" not in response.text

        # PR 3407 delta review P2: the patient-safe boundary must hold at
        # the capability level, not per-route — the same bearer token must
        # not read ``notes`` through the legacy GET either.
        legacy = client.get(
            f"/api/v1/visits/info/{test_visit.confirmation_token}"
        )
        assert legacy.status_code == 200
        assert "notes" not in legacy.json()
        assert "private clinical note" not in legacy.text

    def test_legacy_get_visit_info_omits_internal_notes(self, client, db_session, test_visit):
        """PR 3407 delta review P2: legacy GET is patient-safe too.

        The old per-route fix filtered ``notes`` only on the POST via the
        ``VisitInfoResponse`` model, while the legacy GET still published
        the raw service card. Any holder of the confirmation token could
        read the clinical/admin text through the legacy URL, so the field
        is now dropped from the service card itself (both routes share
        it) and the GET response is additionally filtered through the
        same patient-safe model.
        """
        test_visit.notes = "diagnosis: private clinical note"
        db_session.flush()
        response = client.get(
            f"/api/v1/visits/info/{test_visit.confirmation_token}"
        )

        assert response.status_code == 200
        assert "notes" not in response.json()
        assert "private clinical note" not in response.text

    def test_post_visit_info_unknown_token_matches_legacy_get(self, client):
        token = "synthetic-unknown-token"
        post_response = client.post("/api/v1/visits/info", json={"token": token})
        get_response = client.get(f"/api/v1/visits/info/{token}")

        assert post_response.status_code == get_response.status_code == 404
        assert post_response.json() == get_response.json()

    def test_post_visit_info_expired_token_matches_legacy_get(self, client, db_session, test_visit):
        """Error bodies stay identical between POST and legacy GET."""
        test_visit.confirmation_expires_at = datetime.utcnow() - timedelta(hours=1)
        db_session.flush()
        token = test_visit.confirmation_token
        post_response = client.post("/api/v1/visits/info", json={"token": token})
        get_response = client.get(f"/api/v1/visits/info/{token}")

        assert post_response.status_code == get_response.status_code == 400
        assert post_response.json() == get_response.json()

    @pytest.mark.parametrize(
        "failure",
        [
            VisitConfirmationDomainError(
                status_code=500, detail="SYNTHETIC-SENSITIVE-DETAIL"
            ),
            RuntimeError("SYNTHETIC-SENSITIVE-DETAIL"),
        ],
    )
    def test_post_visit_info_hides_internal_errors(self, client, monkeypatch, failure):
        def fail_read(_service, _token):
            raise failure

        monkeypatch.setattr(VisitConfirmationService, "get_visit_info", fail_read)
        response = client.post(
            "/api/v1/visits/info", json={"token": "synthetic-error-token"}
        )

        assert response.status_code == 500
        assert response.json() == {"detail": "Не удалось получить информацию о визите"}
        assert "SYNTHETIC-SENSITIVE-DETAIL" not in response.text

    def test_post_visit_info_is_in_openapi(self, client):
        schema = client.get("/openapi.json").json()
        operation = schema["paths"]["/api/v1/visits/info"]["post"]
        request_ref = operation["requestBody"]["content"]["application/json"]["schema"]
        assert request_ref["$ref"] == "#/components/schemas/VisitInfoRequest"
        response_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]
        assert response_ref["$ref"] == "#/components/schemas/VisitInfoResponse"

    @pytest.mark.parametrize(
        "failure, expected_status",
        [
            (
                VisitConfirmationDomainError(
                    status_code=500, detail="SYNTHETIC-SENSITIVE-DETAIL"
                ),
                500,
            ),
            (
                VisitConfirmationDomainError(
                    status_code=503, detail="Internal: SYNTHETIC-SENSITIVE-DETAIL"
                ),
                503,
            ),
            (RuntimeError("SYNTHETIC-SENSITIVE-DETAIL"), 500),
            (
                VisitConfirmationDomainError(
                    status_code=500,
                    detail="Ошибка получения информации о визите: SQLAlchemy SYNTHETIC-SENSITIVE-DETAIL",
                ),
                500,
            ),
            (RuntimeError("division by zero in SYNTHETIC-SENSITIVE-DETAIL"), 500),
        ],
    )
    def test_get_visit_info_hides_internal_errors(
        self, client, monkeypatch, failure, expected_status
    ):
        """PR 3417 review residual P2: the legacy GET is a public
        bearer-token route, so its 5xx error path must be as patient-safe
        as the POST's — the service wraps raw exception text
        (SQLAlchemy/DB internals) into its 500 detail, and the legacy GET
        used to forward it verbatim via ``_raise_http_error``.
        """
        def fail_read(_service, _token):
            raise failure

        monkeypatch.setattr(VisitConfirmationService, "get_visit_info", fail_read)
        response = client.get("/api/v1/visits/info/synthetic-error-token")

        assert response.status_code == expected_status
        assert response.json() == {"detail": "Не удалось получить информацию о визите"}
        assert "SYNTHETIC-SENSITIVE-DETAIL" not in response.text

    @pytest.mark.parametrize("status_code", [500, 503])
    def test_visit_info_get_post_error_parity_on_5xx(
        self, client, monkeypatch, status_code
    ):
        """PR 3417 review residual P2: GET and POST are identical on the
        successful card, so the 5xx error bodies must be identical too —
        both sanitized, no raw internal exception text on either route.
        """
        def fail_read(_service, _token):
            raise VisitConfirmationDomainError(
                status_code=status_code,
                detail=f"Ошибка получения информации о визите: SYNTHETIC-{status_code}",
            )

        monkeypatch.setattr(VisitConfirmationService, "get_visit_info", fail_read)
        get_response = client.get("/api/v1/visits/info/synthetic-error-token")
        post_response = client.post(
            "/api/v1/visits/info", json={"token": "synthetic-error-token"}
        )

        assert get_response.status_code == post_response.status_code == status_code
        assert get_response.json() == post_response.json()
        assert get_response.json() == {"detail": "Не удалось получить информацию о визите"}

    def test_visit_info_cards_are_not_cacheable(self, client, test_visit):
        """PR 3417 review residual P2: the card is bearer-capability PHI
        (patient/doctor names, services, totals), so GET and POST responses
        must never be storable by browsers or intermediaries — same policy
        as the dental clinical content (``Cache-Control: private, no-store``).
        """
        token = test_visit.confirmation_token
        get_response = client.get(f"/api/v1/visits/info/{token}")
        post_response = client.post("/api/v1/visits/info", json={"token": token})

        assert get_response.status_code == post_response.status_code == 200
        assert get_response.headers["cache-control"] == "private, no-store"
        assert post_response.headers["cache-control"] == "private, no-store"

    def test_confirm_visit_telegram_success(self, db_session, test_visit, test_daily_queue):
        """A trusted callback can confirm only for the linked patient."""
        _link_patient_chat(db_session, test_visit)
        data = _trusted_confirm(db_session, test_visit.confirmation_token)

        assert data["success"] is True
        assert data["visit_id"] == test_visit.id
        assert data["status"] in ["confirmed", "open"]
        assert "подтвержден" in data["message"]

    def test_confirm_visit_telegram_invalid_token(self, db_session):
        """Тест подтверждения с недействительным токеном"""
        with pytest.raises(VisitConfirmationDomainError) as exc:
            _trusted_confirm(db_session, "invalid-token-123")
        assert exc.value.status_code == 404

    def test_confirm_visit_telegram_wrong_channel(self, db_session, test_visit):
        """Тест подтверждения через неправильный канал"""
        test_visit.confirmation_channel = "phone"

        _link_patient_chat(db_session, test_visit)
        with pytest.raises(VisitConfirmationDomainError) as exc:
            _trusted_confirm(db_session, test_visit.confirmation_token)
        assert exc.value.status_code == 400

    @pytest.mark.parametrize("action", ["confirm", "cancel"])
    def test_public_telegram_endpoint_rejects_claimed_identity(
        self, client, db_session, test_visit, action
    ):
        link = _link_patient_chat(db_session, test_visit)
        token = test_visit.confirmation_token
        capability = build_telegram_visit_action_token(
            visit_id=test_visit.id, confirmation_token=token, link_id=link.id,
            chat_id=link.chat_id, patient_id=test_visit.patient_id,
            link_epoch=link.patient_link_epoch, visit_context_epoch=test_visit.confirmation_context_epoch,
        )
        response = client.post(
            f"/api/v1/telegram/visits/{action}",
            json={"token": capability, "telegram_user_id": "123456789"},
        )
        assert response.status_code == 403
        assert "no-store" in response.headers["cache-control"]
        assert test_visit.patient.short_name() not in response.text
        db_session.refresh(test_visit)
        assert test_visit.status == "pending_confirmation"
        assert test_visit.confirmation_token == token

    def test_confirm_visit_pwa_success(self, client, db_session, test_visit, test_daily_queue):
        """Тест успешного подтверждения визита через PWA"""
        test_visit.confirmation_channel = "pwa"
        db_session.flush()

        response = client.post("/api/v1/patient/visits/confirm", json={
            "token": test_visit.confirmation_token,
            "patient_phone": test_visit.patient.phone
        })

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["visit_id"] == test_visit.id

    def test_confirm_visit_pwa_phone_mismatch(self, client, db_session, test_visit):
        """Тест подтверждения PWA с неправильным телефоном"""
        test_visit.confirmation_channel = "pwa"
        db_session.flush()

        response = client.post("/api/v1/patient/visits/confirm", json={
            "token": test_visit.confirmation_token,
            "patient_phone": "+998900000999"
        })

        assert response.status_code == 400
        data = response.json()
        assert "не совпадает" in data["detail"]

    @pytest.mark.parametrize("status_code", [500, 503])
    def test_confirm_visit_pwa_hides_internal_error(
        self, client, monkeypatch, status_code
    ):
        marker = "SYNTHETIC-SENSITIVE-DETAIL"

        def fail_confirmation(_service, **_kwargs):
            raise VisitConfirmationDomainError(
                status_code=status_code, detail=f"Internal error: {marker}"
            )

        monkeypatch.setattr(
            VisitConfirmationService, "confirm_by_pwa", fail_confirmation
        )
        response = client.post(
            "/api/v1/patient/visits/confirm",
            json={"token": "synthetic-confirm-token"},
        )

        assert response.status_code == status_code
        assert response.json() == {"detail": "Не удалось подтвердить визит"}
        assert marker not in response.text

    @pytest.mark.parametrize("status_code", [400, 404, 429])
    def test_confirm_visit_pwa_preserves_domain_error(
        self, client, monkeypatch, status_code
    ):
        detail = "Синтетическая ошибка подтверждения"
        headers = {"Retry-After": "7"} if status_code == 429 else None

        def fail_confirmation(_service, **_kwargs):
            raise VisitConfirmationDomainError(
                status_code=status_code, detail=detail, headers=headers
            )

        monkeypatch.setattr(
            VisitConfirmationService, "confirm_by_pwa", fail_confirmation
        )
        response = client.post(
            "/api/v1/patient/visits/confirm",
            json={"token": "synthetic-confirm-token"},
        )

        assert response.status_code == status_code
        assert response.json() == {"detail": detail}
        if headers:
            assert response.headers["Retry-After"] == "7"

    def test_confirm_visit_registrar_success(self, client, test_visit, registrar_auth_headers, test_daily_queue):
        """Тест подтверждения визита регистратором"""
        response = client.post(
            f"/api/v1/registrar/visits/{test_visit.id}/confirm",
            json={
                "confirmation_notes": "Подтверждено по телефону"
            },
            headers=registrar_auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["visit_id"] == test_visit.id

    def test_confirm_visit_registrar_unauthorized(self, client, test_visit):
        """Тест подтверждения регистратором без авторизации"""
        response = client.post(
            f"/api/v1/registrar/visits/{test_visit.id}/confirm",
            json={
                "confirmation_notes": "Test"
            }
        )

        assert response.status_code == 401

    def test_confirm_visit_registrar_wrong_role(self, client, test_visit, cardio_auth_headers):
        """Тест подтверждения регистратором с неправильной ролью"""
        response = client.post(
            f"/api/v1/registrar/visits/{test_visit.id}/confirm",
            json={
                "confirmation_notes": "Test"
            },
            headers=cardio_auth_headers
        )

        assert response.status_code == 403

    def test_confirm_visit_creates_queue_entry_today(self, client, db_session, test_visit, test_daily_queue):
        """Тест создания записи в очереди при подтверждении визита на сегодня"""
        # SSOT: «сегодня» = день КЛИНИКИ (не host-UTC дата)
        from app.services.visit_confirmation_service import _clinic_today

        test_visit.visit_date = _clinic_today(db_session)
        db_session.commit()

        _link_patient_chat(db_session, test_visit)
        data = _trusted_confirm(db_session, test_visit.confirmation_token)

        # Проверяем что создалась запись в очереди
        queue_entry = db_session.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.visit_id == test_visit.id
        ).first()

        assert queue_entry is not None
        assert queue_entry.number > 0
        assert queue_entry.status == "waiting"
        assert queue_entry.source == "confirmation"

        # Проверяем что в ответе есть информация об очереди
        assert "queue_numbers" in data
        assert len(data["queue_numbers"]) > 0

    def test_confirm_visit_no_queue_entry_future_date(self, client, db_session, test_visit, test_daily_queue):
        """Тест отсутствия записи в очереди при подтверждении визита на будущую дату"""
        # SSOT: «завтра» = день клиники + 1 (не host-UTC окно 19:00-24:00)
        from app.services.visit_confirmation_service import _clinic_today

        test_visit.visit_date = _clinic_today(db_session) + timedelta(days=1)
        db_session.commit()

        _link_patient_chat(db_session, test_visit)
        data = _trusted_confirm(db_session, test_visit.confirmation_token)

        # Проверяем что НЕ создалась запись в очереди
        queue_entry = db_session.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.visit_id == test_visit.id
        ).first()

        assert queue_entry is None

        # Проверяем сообщение о том, что номера будут присвоены позже
        assert "утром в день визита" in data["message"]

    def test_confirm_visit_updates_status(self, client, db_session, test_visit):
        """Тест обновления статуса визита при подтверждении"""
        original_status = test_visit.status

        _link_patient_chat(db_session, test_visit)
        assert _trusted_confirm(db_session, test_visit.confirmation_token)["success"] is True

        # Обновляем объект из БД
        db_session.refresh(test_visit)

        assert test_visit.status != original_status
        assert test_visit.status in ["confirmed", "open"]
        assert test_visit.confirmed_at is not None
        assert test_visit.confirmed_by is not None
        assert "telegram_" in test_visit.confirmed_by

    def test_confirm_visit_replay_rejected(self, db_session, test_visit):
        """A consumed visit cannot be confirmed twice."""
        # Первое подтверждение должно пройти
        _link_patient_chat(db_session, test_visit)
        token = test_visit.confirmation_token
        assert _trusted_confirm(db_session, token)["success"] is True

        # Повторное подтверждение того же визита должно вернуть ошибку
        with pytest.raises(VisitConfirmationDomainError) as exc:
            _trusted_confirm(db_session, token)
        assert 400 <= exc.value.status_code < 500

    def test_confirm_visit_security_validation(self, db_session, test_visit):
        """Тест валидации безопасности при подтверждении"""
        # Тест с подозрительным User-Agent
        _link_patient_chat(db_session, test_visit)
        with pytest.raises(VisitConfirmationDomainError) as exc:
            _trusted_confirm(db_session, test_visit.confirmation_token, "Googlebot/2.1")
        assert exc.value.status_code in [400, 429]
