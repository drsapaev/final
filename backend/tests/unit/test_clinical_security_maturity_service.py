from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.config import settings
from app.models.emr_v2 import EMRAuditLog
from app.models.user_profile import UserAuditLog
from app.services.clinical_security_maturity_service import (
    ClinicalSecurityMaturityService,
)


@pytest.mark.unit
@pytest.mark.security
class TestClinicalSecurityMaturityService:
    def test_retention_inventory_counts_overdue_records(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "PHI_RETENTION_DAYS", 365, raising=False)
        now = datetime.utcnow()
        db_session.add_all(
            [
                EMRAuditLog(
                    emr_id=1,
                    patient_id=10,
                    visit_id=100,
                    action="view",
                    user_id=1,
                    user_role="Doctor",
                    timestamp=now - timedelta(days=900),
                ),
                EMRAuditLog(
                    emr_id=2,
                    patient_id=11,
                    visit_id=101,
                    action="update",
                    user_id=2,
                    user_role="Doctor",
                    timestamp=now - timedelta(days=2),
                ),
            ]
        )
        db_session.commit()

        service = ClinicalSecurityMaturityService(db_session, now_provider=lambda: now)
        inventory = service.build_retention_inventory()
        emr_target = next(
            item for item in inventory["targets"] if item["table_name"] == "emr_audit_logs"
        )

        assert emr_target["total_records"] >= 2
        assert emr_target["overdue_records"] >= 1
        assert inventory["total_overdue_records"] >= 1

    def test_encryption_posture_fails_without_message_key(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "MESSAGE_ENCRYPTION_KEY", None, raising=False)
        monkeypatch.setattr(settings, "ENCRYPTION_KEY", None, raising=False)

        service = ClinicalSecurityMaturityService(db_session)
        posture = service.evaluate_encryption_posture()

        assert posture["encryption_ready"] is False
        assert posture["message_key_configured"] is False
        assert any("MESSAGE_ENCRYPTION_KEY" in issue for issue in posture["issues"])

    def test_encryption_posture_passes_with_valid_keys(self, db_session, monkeypatch):
        monkeypatch.setattr(
            settings, "MESSAGE_ENCRYPTION_KEY", "message-key-for-test-123", raising=False
        )
        monkeypatch.setattr(
            settings, "ENCRYPTION_KEY", "app-key-for-test-456", raising=False
        )

        service = ClinicalSecurityMaturityService(db_session)
        posture = service.evaluate_encryption_posture()

        assert posture["encryption_ready"] is True
        assert posture["issues"] == []
        assert posture["smoke_tests"]["message_encryption_roundtrip"] is True
        assert posture["smoke_tests"]["app_encryption_roundtrip"] is True

    def test_phi_access_report_aggregates_emr_and_user_audit(self, db_session):
        now = datetime.utcnow()
        db_session.add_all(
            [
                EMRAuditLog(
                    emr_id=1,
                    patient_id=10,
                    visit_id=100,
                    action="view",
                    user_id=7,
                    user_role="Doctor",
                    timestamp=now - timedelta(days=1),
                ),
                EMRAuditLog(
                    emr_id=1,
                    patient_id=10,
                    visit_id=100,
                    action="view",
                    user_id=7,
                    user_role="Doctor",
                    timestamp=now - timedelta(hours=2),
                ),
                EMRAuditLog(
                    emr_id=2,
                    patient_id=11,
                    visit_id=101,
                    action="update",
                    user_id=8,
                    user_role="Doctor",
                    timestamp=now - timedelta(hours=1),
                ),
                UserAuditLog(
                    user_id=7,
                    action="UPDATE",
                    resource_type="patients",
                    resource_id=10,
                    created_at=now - timedelta(hours=3),
                ),
                UserAuditLog(
                    user_id=8,
                    action="UPDATE",
                    resource_type="emr",
                    resource_id=1,
                    created_at=now - timedelta(hours=4),
                ),
            ]
        )
        db_session.commit()

        service = ClinicalSecurityMaturityService(db_session, now_provider=lambda: now)
        report = service.build_phi_access_report(days=30, top_users_limit=5)

        assert report["emr_events"] == 3
        assert report["user_audit_phi_events"] == 2
        assert report["total_phi_events"] == 5
        assert report["unique_users"] == 2
        assert report["action_breakdown"]["view"] == 2
        assert report["action_breakdown"]["update"] == 1
        assert report["action_breakdown"]["user_audit:update"] == 2
        assert report["top_users"][0]["events"] >= report["top_users"][1]["events"]

    def test_break_glass_policy_validation(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "BREAK_GLASS_ENABLED", True, raising=False)
        monkeypatch.setattr(settings, "BREAK_GLASS_MAX_MINUTES", 60, raising=False)
        monkeypatch.setattr(settings, "BREAK_GLASS_REASON_MIN_LENGTH", 32, raising=False)
        monkeypatch.setattr(settings, "BREAK_GLASS_REQUIRE_TICKET", True, raising=False)
        monkeypatch.setattr(
            settings, "BREAK_GLASS_ALLOWED_ROLES", "Admin,ChiefDoctor", raising=False
        )

        service = ClinicalSecurityMaturityService(db_session)
        valid = service.validate_break_glass_policy()

        assert valid["compliant"] is True
        assert valid["errors"] == []

        monkeypatch.setattr(settings, "BREAK_GLASS_MAX_MINUTES", 360, raising=False)
        monkeypatch.setattr(settings, "BREAK_GLASS_REASON_MIN_LENGTH", 10, raising=False)
        monkeypatch.setattr(settings, "BREAK_GLASS_ALLOWED_ROLES", "", raising=False)
        invalid = service.validate_break_glass_policy()

        assert invalid["compliant"] is False
        assert any("240 minutes" in err for err in invalid["errors"])
        assert any("at least 20" in err for err in invalid["errors"])
        assert any("no allowed roles" in err.lower() for err in invalid["errors"])
