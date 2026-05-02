from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import payment_init_service as init_module


def _service_with_repo(
    monkeypatch: pytest.MonkeyPatch, repo: Mock, payment_manager: Mock
) -> init_module.PaymentInitService:
    monkeypatch.setattr(init_module, "PaymentInitRepository", lambda db: repo)
    return init_module.PaymentInitService(db=Mock(), payment_manager=payment_manager)


def _patch_payment_side_effects(monkeypatch: pytest.MonkeyPatch, billing: Mock) -> None:
    monkeypatch.setattr(init_module, "BillingService", Mock(return_value=billing))
    monkeypatch.setattr(
        init_module,
        "extract_model_changes",
        Mock(return_value=(None, {"id": 1})),
    )
    monkeypatch.setattr(init_module, "log_critical_change", Mock())
    monkeypatch.setattr(
        init_module.queue_service,
        "get_local_timestamp",
        Mock(return_value=datetime(2026, 1, 1, 10, 0, 0)),
    )


def test_init_payment_raises_when_visit_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = Mock()
    repo.db = Mock()
    repo.get_visit.return_value = None
    manager = Mock()
    service = _service_with_repo(monkeypatch, repo, manager)

    with pytest.raises(init_module.PaymentInitDomainError) as exc:
        service.init_payment(
            request=Mock(),
            current_user_id=1,
            visit_id=404,
            provider="payme",
            amount=100_000,
            currency="UZS",
            description=None,
            return_url=None,
            cancel_url=None,
        )

    assert exc.value.status_code == 404
    assert "Визит не найден" in exc.value.detail
    repo.rollback.assert_called_once()
    repo.commit.assert_not_called()


def test_init_payment_returns_error_for_unsupported_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = Mock()
    repo.db = Mock()
    repo.get_visit.return_value = SimpleNamespace(id=10)
    manager = Mock()
    manager.get_providers_for_currency.return_value = ["click"]
    service = _service_with_repo(monkeypatch, repo, manager)

    result = service.init_payment(
        request=Mock(),
        current_user_id=1,
        visit_id=10,
        provider="payme",
        amount=100_000,
        currency="UZS",
        description=None,
        return_url=None,
        cancel_url=None,
    )

    assert result["success"] is False
    assert "не поддерживает валюту" in result["error_message"]
    manager.create_payment.assert_not_called()
    repo.commit.assert_not_called()
    repo.rollback.assert_not_called()


def test_init_payment_success_path_updates_pending_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = Mock()
    repo.db = Mock()
    repo.get_visit.return_value = SimpleNamespace(id=11)
    payment = SimpleNamespace(id=501, provider_payment_id=None, payment_url=None, provider_data={})
    billing = Mock()
    billing.create_payment.return_value = payment
    billing.update_payment_status.return_value = payment
    _patch_payment_side_effects(monkeypatch, billing)

    manager = Mock()
    manager.get_providers_for_currency.return_value = ["payme"]
    manager.create_payment.return_value = SimpleNamespace(
        success=True,
        payment_id="payme_abc",
        payment_url="https://pay.example/payme_abc",
        status="pending",
        provider_data={"provider": "payme"},
        error_message=None,
    )

    service = _service_with_repo(monkeypatch, repo, manager)
    result = service.init_payment(
        request=Mock(),
        current_user_id=7,
        visit_id=11,
        provider="payme",
        amount=200_000,
        currency="UZS",
        description=None,
        return_url=None,
        cancel_url=None,
    )

    assert result["success"] is True
    assert result["payment_id"] == 501
    assert result["provider_payment_id"] == "payme_abc"
    assert result["status"] == "pending"

    assert payment.provider_payment_id == "payme_abc"
    assert payment.payment_url == "https://pay.example/payme_abc"
    assert payment.provider_data == {"provider": "payme"}

    billing.create_payment.assert_called_once()
    billing.update_payment_status.assert_called_once_with(
        payment_id=501,
        new_status="pending",
        meta={"provider": "payme"},
        commit=False,
    )
    repo.commit.assert_called_once()
    repo.refresh.assert_called_once_with(payment)
    repo.rollback.assert_not_called()


def test_init_payment_provider_failure_sets_failed_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = Mock()
    repo.db = Mock()
    repo.get_visit.return_value = SimpleNamespace(id=12)
    payment = SimpleNamespace(id=777, provider_payment_id=None, payment_url=None, provider_data={})
    billing = Mock()
    billing.create_payment.return_value = payment
    billing.update_payment_status.return_value = payment
    _patch_payment_side_effects(monkeypatch, billing)

    manager = Mock()
    manager.get_providers_for_currency.return_value = ["click"]
    manager.create_payment.return_value = SimpleNamespace(
        success=False,
        payment_id=None,
        payment_url=None,
        status=None,
        provider_data={},
        error_message="provider timeout",
    )

    service = _service_with_repo(monkeypatch, repo, manager)
    result = service.init_payment(
        request=Mock(),
        current_user_id=7,
        visit_id=12,
        provider="click",
        amount=150_000,
        currency="UZS",
        description=None,
        return_url=None,
        cancel_url=None,
    )

    assert result["success"] is False
    assert result["payment_id"] == 777
    assert result["error_message"] == "provider timeout"
    billing.update_payment_status.assert_called_once_with(
        payment_id=777,
        new_status="failed",
        meta={"error": "provider timeout"},
        commit=False,
    )
    repo.commit.assert_called_once()
    repo.refresh.assert_called_once_with(payment)
    repo.rollback.assert_not_called()


def test_init_payment_unexpected_error_returns_with_payment_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = Mock()
    repo.db = Mock()
    repo.get_visit.return_value = SimpleNamespace(id=13)
    payment = SimpleNamespace(id=888, provider_payment_id=None, payment_url=None, provider_data={})
    billing = Mock()
    billing.create_payment.return_value = payment
    _patch_payment_side_effects(monkeypatch, billing)

    manager = Mock()
    manager.get_providers_for_currency.return_value = ["payme"]
    manager.create_payment.side_effect = RuntimeError("network down")

    service = _service_with_repo(monkeypatch, repo, manager)
    result = service.init_payment(
        request=Mock(),
        current_user_id=2,
        visit_id=13,
        provider="payme",
        amount=90_000,
        currency="UZS",
        description=None,
        return_url=None,
        cancel_url=None,
    )

    assert result["success"] is False
    assert result["payment_id"] == 888
    assert "Ошибка инициализации платежа" in result["error_message"]
    repo.rollback.assert_called_once()
    repo.commit.assert_not_called()
