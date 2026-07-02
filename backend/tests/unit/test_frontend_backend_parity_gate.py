from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_module():
    root = Path(__file__).resolve().parents[3]
    script_path = root / "ops" / "scripts" / "check_frontend_backend_parity.py"
    spec = importlib.util.spec_from_file_location("check_frontend_backend_parity", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load check_frontend_backend_parity.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_parity_gate_passes_when_all_quality_thresholds_met(tmp_path, monkeypatch):
    module = _load_module()
    parity_path = tmp_path / "parity.json"
    ux_path = tmp_path / "ux.json"

    parity_path.write_text(
        json.dumps(
            {
                "summary": {"coverage_pct": 11.52},
                "critical_flows": {"summary": {"failed_flows": 0}},
                "rbac_alignment": {"status": "pass"},
            }
        ),
        encoding="utf-8",
    )
    ux_path.write_text(
        json.dumps({"summary": {"avg_correctness": 4.2, "avg_usability": 4.1}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_frontend_backend_parity.py",
            "--parity-json",
            str(parity_path),
            "--ux-json",
            str(ux_path),
        ],
    )
    assert module.main() == 0


@pytest.mark.unit
def test_parity_gate_fails_when_rbac_or_ux_thresholds_are_broken(tmp_path, monkeypatch):
    module = _load_module()
    parity_path = tmp_path / "parity.json"
    ux_path = tmp_path / "ux.json"

    parity_path.write_text(
        json.dumps(
            {
                "summary": {"coverage_pct": 9.0},
                "critical_flows": {"summary": {"failed_flows": 1}},
                "rbac_alignment": {"status": "fail"},
            }
        ),
        encoding="utf-8",
    )
    ux_path.write_text(
        json.dumps({"summary": {"avg_correctness": 3.9, "avg_usability": 3.5}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_frontend_backend_parity.py",
            "--parity-json",
            str(parity_path),
            "--ux-json",
            str(ux_path),
        ],
    )
    assert module.main() == 1
