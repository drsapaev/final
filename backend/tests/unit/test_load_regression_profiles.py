from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    root = Path(__file__).resolve().parents[3]
    script_path = root / "ops" / "scripts" / "check_load_regression.py"
    spec = importlib.util.spec_from_file_location("check_load_regression", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load check_load_regression.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_effective_config_selects_requested_profile():
    module = _load_module()
    cfg = {
        "profiles": {
            "core": {
                "targets": {"rps_min": 10.0, "p95_ms_max": 500.0, "error_rate_max": 0.01, "checks_rate_min": 0.99},
                "baseline": {"rps": 12.0, "p95_ms": 450.0},
                "regression": {"max_rps_drop_pct": 15.0, "max_p95_increase_pct": 20.0},
            }
        }
    }

    effective = module._effective_config(cfg, "core")
    assert effective["targets"]["rps_min"] == 10.0


@pytest.mark.unit
def test_effective_config_requires_profile_for_profiled_config():
    module = _load_module()
    cfg = {"profiles": {"core": {}}}
    with pytest.raises(ValueError):
        module._effective_config(cfg, None)


@pytest.mark.unit
def test_evaluate_detects_profile_budget_violations():
    module = _load_module()
    metrics = module.LoadMetrics(
        rps=9.0,
        p95_ms=610.0,
        error_rate=0.02,
        checks_rate=0.95,
    )
    effective_cfg = {
        "targets": {"rps_min": 10.0, "p95_ms_max": 500.0, "error_rate_max": 0.01, "checks_rate_min": 0.99},
        "baseline": {"rps": 12.0, "p95_ms": 450.0},
        "regression": {"max_rps_drop_pct": 15.0, "max_p95_increase_pct": 20.0},
    }

    ok, failures = module.evaluate(metrics, effective_cfg)
    assert ok is False
    assert any("RPS below target" in failure for failure in failures)
    assert any("P95 latency above target" in failure for failure in failures)
    assert any("Error rate above target" in failure for failure in failures)


@pytest.mark.unit
def test_parse_k6_summary_handles_values_dict(tmp_path):
    module = _load_module()
    summary = tmp_path / "k6-summary.json"
    summary.write_text(
        """
        {
          "metrics": {
            "http_reqs": {"values": {"rate": 31.2}},
            "http_req_duration": {"values": {"p(95)": 412.5}},
            "http_req_failed": {"values": {"rate": 0.001}},
            "checks": {"values": {"rate": 0.999}}
          }
        }
        """.strip(),
        encoding="utf-8",
    )

    metrics = module.parse_k6_summary(summary)
    assert metrics.rps == pytest.approx(31.2)
    assert metrics.p95_ms == pytest.approx(412.5)
    assert metrics.error_rate == pytest.approx(0.001)
    assert metrics.checks_rate == pytest.approx(0.999)
