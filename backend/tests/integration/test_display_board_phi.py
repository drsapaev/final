"""
RQ-24.a.1 fail-first (E-018 defect-1): verify that the WS payload
formats patient_name according to DisplayBoard.show_patient_names,
not just hardwired "initials".

Pure-function test: no DB needed. Tests _format_patient_name
and _resolve_name_format in isolation.
"""
from __future__ import annotations
from types import SimpleNamespace

import pytest

from app.services.display_websocket import DisplayWebSocketManager


class TestFormatPatientName:
    def setup_method(self):
        self.mgr = DisplayWebSocketManager()

    def test_none_hides_name(self):
        assert self.mgr._format_patient_name("SYNTHETIC-Petrov", "none") == "Пациент"

    def test_initials_shortens_name(self):
        assert self.mgr._format_patient_name("SYNTHETIC-Petrov Ivan", "initials") == "SYNTHETIC-Petrov I."

    def test_full_returns_name(self):
        assert self.mgr._format_patient_name("SYNTHETIC-Petrov Ivan", "full") == "SYNTHETIC-Petrov Ivan"

    def test_unknown_format_falls_back(self):
        assert self.mgr._format_patient_name("SYNTHETIC-Petrov", "bogus") == "SYNTHETIC-Petrov"

    def test_empty_name_returns_placeholder(self):
        assert self.mgr._format_patient_name("", "none") == "Пациент"


class TestResolveNameFormat:
    """Verify the resolver reads from _name_format_cache."""

    def test_resolves_none(self):
        mgr = DisplayWebSocketManager()
        mgr._name_format_cache["main_board"] = "none"
        assert mgr._resolve_name_format(["main_board"]) == "none"

    def test_resolves_full(self):
        mgr = DisplayWebSocketManager()
        mgr._name_format_cache["main_board"] = "full"
        assert mgr._resolve_name_format(["main_board"]) == "full"

    def test_no_board_defaults_to_initials(self):
        mgr = DisplayWebSocketManager()
        assert mgr._resolve_name_format(["nonexistent"]) == "initials"
