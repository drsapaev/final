"""
Интеграционные тесты для API подтверждения визитов
"""
from datetime import datetime, timedelta

import pytest

from app.models.online_queue import OnlineQueueEntry
from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
)


@pytest.mark.integration
@pytest.mark.confirmation
class TestVisitConfirmationAPI:
    """Интеграционные тесты для API подтверждения визитов"""

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

    def test_get_visit_info_expired_token(self, client, test_visit):
        """Тест получения информации с истекшим токеном"""
        # Устанавливаем время истечения в прошлом
        test_visit.confirmation_expires_at = datetime.utcnow() - timedelta(hours=1)

        response = client.get(f"/api/v1/visits/info/{test_visit.confirmation_token}")

        assert response.status_code == 400
        data = response.json()
        assert "истек" in data["detail"]

    def test_post_visit_info_matches_legacy_get(self, client, test_visit):
        """The token moves to the request body; the visit card is unchanged."""
        token = test_visit.confirmation_token
        post_response = client.post("/api/v1/visits/info", json={"token": token})
        get_response = client.get(f"/api/v1/visits/info/{token}")

        assert post_response.status_code == get_response.status_code == 200
        assert post_response.json() == get_response.json()
        assert token not in post_response.request.url.path

    def test_post_visit_info_unknown_token_matches_legacy_get(self, client):
        token = "synthetic-unknown-token"
        post_response = client.post("/api/v1/visits/info", json={"token": token})
        get_response = client.get(f"/api/v1/visits/info/{token}")

        assert post_response.status_code == get_response.status_code == 404
        assert post_response.json() == get_response.json()

    def test_post_visit_info_expired_token_matches_legacy_get(self, client, test_visit):
        test_visit.confirmation_expires_at = datetime.utcnow() - timedelta(hours=1)
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

    def test_confirm_visit_telegram_success(self, client, test_visit, test_daily_queue):
        """Тест успешного подтверждения визита через Telegram"""
        response = client.post("/api/v1/telegram/visits/confirm", json={
            "token": test_visit.confirmation_token,
            "telegram_user_id": "123456789",
            "telegram_username": "testuser"
        })

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["visit_id"] == test_visit.id
        assert data["status"] in ["confirmed", "open"]
        assert "подтвержден" in data["message"]

    def test_confirm_visit_telegram_invalid_token(self, client):
        """Тест подтверждения с недействительным токеном"""
        response = client.post("/api/v1/telegram/visits/confirm", json={
            "token": "invalid-token-123",
            "telegram_user_id": "123456789"
        })

        assert response.status_code == 404
        data = response.json()
        assert "не найден" in data["detail"]

    def test_confirm_visit_telegram_wrong_channel(self, client, test_visit):
        """Тест подтверждения через неправильный канал"""
        test_visit.confirmation_channel = "phone"

        response = client.post("/api/v1/telegram/visits/confirm", json={
            "token": test_visit.confirmation_token,
            "telegram_user_id": "123456789"
        })

        assert response.status_code == 400
        data = response.json()
        assert "Telegram" in data["detail"]

    def test_confirm_visit_pwa_success(self, client, test_visit, test_daily_queue):
        """Тест успешного подтверждения визита через PWA"""
        test_visit.confirmation_channel = "pwa"

        response = client.post("/api/v1/patient/visits/confirm", json={
            "token": test_visit.confirmation_token,
            "patient_phone": test_visit.patient.phone
        })

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["visit_id"] == test_visit.id

    def test_confirm_visit_pwa_phone_mismatch(self, client, test_visit):
        """Тест подтверждения PWA с неправильным телефоном"""
        test_visit.confirmation_channel = "pwa"

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

        response = client.post("/api/v1/telegram/visits/confirm", json={
            "token": test_visit.confirmation_token,
            "telegram_user_id": "123456789"
        })

        assert response.status_code == 200
        data = response.json()

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

        response = client.post("/api/v1/telegram/visits/confirm", json={
            "token": test_visit.confirmation_token,
            "telegram_user_id": "123456789"
        })

        assert response.status_code == 200
        data = response.json()

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

        response = client.post("/api/v1/telegram/visits/confirm", json={
            "token": test_visit.confirmation_token,
            "telegram_user_id": "123456789"
        })

        assert response.status_code == 200

        # Обновляем объект из БД
        db_session.refresh(test_visit)

        assert test_visit.status != original_status
        assert test_visit.status in ["confirmed", "open"]
        assert test_visit.confirmed_at is not None
        assert test_visit.confirmed_by is not None
        assert "telegram_" in test_visit.confirmed_by

    def test_confirm_visit_rate_limiting(self, client, test_visit):
        """Тест rate limiting при множественных попытках подтверждения"""
        # Первое подтверждение должно пройти
        response1 = client.post("/api/v1/telegram/visits/confirm", json={
            "token": test_visit.confirmation_token,
            "telegram_user_id": "123456789"
        })

        assert response1.status_code == 200

        # Повторное подтверждение того же визита должно вернуть ошибку
        response2 = client.post("/api/v1/telegram/visits/confirm", json={
            "token": test_visit.confirmation_token,
            "telegram_user_id": "123456789"
        })

        assert response2.status_code == 400
        data = response2.json()
        assert "уже" in data["detail"]

    def test_confirm_visit_security_validation(self, client, test_visit):
        """Тест валидации безопасности при подтверждении"""
        # Тест с подозрительным User-Agent
        response = client.post(
            "/api/v1/telegram/visits/confirm",
            json={
                "token": test_visit.confirmation_token,
                "telegram_user_id": "123456789"
            },
            headers={"User-Agent": "Googlebot/2.1"}
        )

        # Должна сработать защита от ботов
        assert response.status_code in [400, 429]
