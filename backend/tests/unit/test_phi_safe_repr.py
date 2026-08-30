"""Tests for PHI-safe __repr__ methods (FOLLOWUP-4).

Validates that __repr__ on models with PHI-bearing fields does NOT
include free-text fields (title, content, phrase, name) that could
leak patient data into logs or debug output.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.ai_chat import AIChatMessage, AIChatSession
from app.models.doctor_phrase_history import DoctorPhraseHistory
from app.models.passkey_credential import PasskeyCredential


@pytest.mark.unit
class TestPhiSafeRepr:
    """Verify __repr__ does not leak PHI fields."""

    def test_ai_chat_session_repr_omits_title(self):
        """AIChatSession.title may contain free-text PHI (user-typed
        session title). __repr__ must NOT include it.
        """
        session = SimpleNamespace(id=42, title="Patient Ivanov HIV+ treatment plan")
        repr_str = AIChatSession.__repr__(session)
        assert "Ivanov" not in repr_str, f"PHI leaked in repr: {repr_str}"
        assert "HIV" not in repr_str, f"PHI leaked in repr: {repr_str}"
        assert "Patient" not in repr_str, f"free-text leaked in repr: {repr_str}"
        assert "42" in repr_str, f"id should be in repr: {repr_str}"

    def test_ai_chat_message_repr_omits_content(self):
        """AIChatMessage.content contains free-text PHI (chat message
        body). __repr__ must NOT include a content preview.
        """
        phi_content = (
            "Patient John Doe (IIN 123456789012) reports chest pain "
            "and shortness of breath. Diagnosed with hypertension."
        )
        message = SimpleNamespace(id=99, role="user", content=phi_content)
        repr_str = AIChatMessage.__repr__(message)
        assert "John Doe" not in repr_str, f"PHI leaked in repr: {repr_str}"
        assert "123456789012" not in repr_str, f"IIN leaked in repr: {repr_str}"
        assert "chest pain" not in repr_str, f"diagnosis leaked in repr: {repr_str}"
        assert "99" in repr_str, f"id should be in repr: {repr_str}"
        assert "user" in repr_str, f"role should be in repr: {repr_str}"

    def test_doctor_phrase_history_repr_omits_phrase(self):
        """DoctorPhraseHistory.phrase contains medical free-text PHI
        (doctor's saved phrases for anamnesis/diagnosis/treatment).
        __repr__ must NOT include phrase preview.
        """
        phi_phrase = "Patient has severe periodontal disease, requires immediate extraction of teeth 16, 17, 18"
        history = SimpleNamespace(
            id=7,
            doctor_id=3,
            field="diagnosis",
            phrase=phi_phrase,
        )
        repr_str = DoctorPhraseHistory.__repr__(history)
        assert "periodontal" not in repr_str, f"PHI leaked in repr: {repr_str}"
        assert "extraction" not in repr_str, f"PHI leaked in repr: {repr_str}"
        assert "7" in repr_str, f"id should be in repr: {repr_str}"
        assert "3" in repr_str, f"doctor_id should be in repr: {repr_str}"
        assert "diagnosis" in repr_str, f"field should be in repr: {repr_str}"

    def test_passkey_credential_repr_omits_name(self):
        """PasskeyCredential.name is user-supplied free text that may
        contain identifying information. __repr__ must NOT include it.
        """
        credential = SimpleNamespace(
            id=5,
            patient_id=11,
            name="John Doe's iPhone 15",
            active=True,
        )
        repr_str = PasskeyCredential.__repr__(credential)
        assert "John Doe" not in repr_str, f"PHI leaked in repr: {repr_str}"
        assert "iPhone" not in repr_str, f"free-text leaked in repr: {repr_str}"
        assert "5" in repr_str, f"id should be in repr: {repr_str}"
        assert "11" in repr_str, f"patient_id should be in repr: {repr_str}"
        assert "True" in repr_str, f"active should be in repr: {repr_str}"

    def test_ai_chat_session_repr_format(self):
        """Verify the exact format of AIChatSession.__repr__."""
        session = SimpleNamespace(id=42, title="anything")
        repr_str = AIChatSession.__repr__(session)
        assert repr_str == "<AIChatSession(id=42)>"

    def test_ai_chat_message_repr_format(self):
        """Verify the exact format of AIChatMessage.__repr__."""
        message = SimpleNamespace(id=99, role="assistant", content="anything")
        repr_str = AIChatMessage.__repr__(message)
        assert repr_str == "<AIChatMessage(id=99, role=assistant)>"

    def test_doctor_phrase_history_repr_format(self):
        """Verify the exact format of DoctorPhraseHistory.__repr__."""
        history = SimpleNamespace(
            id=7, doctor_id=3, field="treatment", phrase="anything"
        )
        repr_str = DoctorPhraseHistory.__repr__(history)
        assert repr_str == "<DoctorPhraseHistory(id=7, doctor=3, field=treatment)>"

    def test_passkey_credential_repr_format(self):
        """Verify the exact format of PasskeyCredential.__repr__."""
        credential = SimpleNamespace(
            id=5, patient_id=11, name="anything", active=True
        )
        repr_str = PasskeyCredential.__repr__(credential)
        assert repr_str == "<PasskeyCredential(id=5, patient_id=11, active=True)>"
