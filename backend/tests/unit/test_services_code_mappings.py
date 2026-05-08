from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.api.v1.endpoints.services import get_service_code_mappings


class _FakeQuery:
    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return [
            SimpleNamespace(service_code="K002", name="legacy ECG", queue_tag="ecg"),
            SimpleNamespace(service_code="K003", name="legacy EchoCG", queue_tag="echokg"),
            SimpleNamespace(service_code="D01", name="Dermatology", queue_tag="dermatology"),
        ]


class _FakeDb:
    def query(self, *args, **kwargs):
        return _FakeQuery()


def test_code_mappings_keep_ecg_and_echo_canonical_with_legacy_db_rows():
    result = asyncio.run(get_service_code_mappings(db=_FakeDb()))

    assert result.specialty_to_code["ecg"] == "K10"
    assert result.specialty_to_code["echokg"] == "K11"
    assert result.specialty_to_code["echo"] == "K11"
    assert result.code_to_name["K10"] == "\u042d\u041a\u0413"
    assert result.code_to_name["K11"] == "\u042d\u0445\u043e\u041a\u0413"
    assert result.specialty_to_code["dermatology"] == "D01"
