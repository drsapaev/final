from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.derma_api_service import DermaApiDomainError, DermaApiService


class Repository:
    def __init__(self):
        self.actor = SimpleNamespace(id=10, is_active=True, is_superuser=False, role="derma", auth_epoch=4)
        self.doctor = SimpleNamespace(id=7, user_id=10, active=True, specialty="dermatology", repeat_owner_generation=8, price_owner_generation=12)
        self.visit = SimpleNamespace(id=1, doctor_id=7, confirmation_context_epoch=9, price_context_generation=13)
        self.service = SimpleNamespace(id=2, active=True, allow_doctor_price_override=True, price=Decimal("120"))
        self.line = SimpleNamespace(id=3, visit_id=1, service_id=2, price=Decimal("120"), price_line_generation=14)
        self.created = None

    def reserve_request_writer(self): pass
    def lock_request_user(self, context): return self.actor
    def lock_request_doctor(self, user_id): return self.doctor
    def lock_request_visit(self, visit_id): return self.visit
    def lock_request_service(self, service_id): return self.service
    def request_visit_services(self, visit_id, service_id): return [self.line]
    def has_pending_override(self, **kwargs): return False
    def protect_target_fk(self, visit_id, service_id, target_id): return self.line
    def get_doctor(self, doctor_id): return None
    def rollback(self): pass
    def create_price_override(self, **kwargs):
        self.created = kwargs
        return SimpleNamespace(id=55)


def _data():
    return SimpleNamespace(visit_id=1, service_id=2, new_price=Decimal("100"), reason="manual", details=None)


def _bearer():
    return SimpleNamespace(user_id=10, patient_id=None)


@pytest.mark.unit
class TestDermaApiService:
    def test_create_price_override_rejects_non_dermatologist(self):
        repo = Repository()
        repo.doctor.specialty = "cardiology"
        with pytest.raises(DermaApiDomainError) as exc:
            DermaApiService(None, repo).create_price_override(override_data=_data(), user_id=10, bearer=_bearer())
        assert exc.value.status_code == 403

    def test_create_price_override_returns_created_entity(self):
        repo = Repository()
        result = DermaApiService(None, repo).create_price_override(override_data=_data(), user_id=10, bearer=_bearer())
        assert result.id == 55
        assert repo.created["target_visit_service_id"] == 3
        assert repo.created["doctor_owner_generation"] == 8
        assert repo.created["visit_context_epoch"] == 9
        assert (repo.created["price_context_generation"], repo.created["price_line_generation"],
                repo.created["price_owner_generation"], repo.created["requester_auth_epoch"]) == (13, 14, 12, 4)

    def test_user_id_is_not_an_assigned_doctor(self):
        repo = Repository()
        repo.visit.doctor_id = repo.actor.id
        with pytest.raises(DermaApiDomainError) as exc:
            DermaApiService(None, repo).create_price_override(override_data=_data(), user_id=10, bearer=_bearer())
        assert exc.value.status_code == 403

    def test_create_price_override_rejects_foreign_visit(self):
        repo = Repository()
        repo.visit.doctor_id = 99
        with pytest.raises(DermaApiDomainError) as exc:
            DermaApiService(None, repo).create_price_override(override_data=_data(), user_id=10, bearer=_bearer())
        assert exc.value.status_code == 403
