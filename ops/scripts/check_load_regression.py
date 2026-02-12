#!/usr/bin/env python3
"""Validate k6 summary against absolute targets and baseline regression limits."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LoadMetrics:
    rps: float
    p95_ms: float
    error_rate: float
    checks_rate: float


def _metric(summary: dict, metric_name: str, value_key: str, default: float = 0.0) -> float:
    metric = summary.get("metrics", {}).get(metric_name, {})
    values = metric.get("values", {})
    value = values.get(value_key, default)
    return float(value)


def parse_k6_summary(path: Path) -> LoadMetrics:
    summary = json.loads(path.read_text(encoding="utf-8"))
    return LoadMetrics(
        rps=_metric(summary, "http_reqs", "rate"),
        p95_ms=_metric(summary, "http_req_duration", "p(95)"),
        error_rate=_metric(summary, "http_req_failed", "rate"),
        checks_rate=_metric(summary, "checks", "rate", 1.0),
    )


def evaluate(metrics: LoadMetrics, baseline_cfg: dict) -> tuple[bool, list[str]]:
    targets = baseline_cfg.get("targets", {})
    baseline = baseline_cfg.get("baseline", {})
    regression = baseline_cfg.get("regression", {})
    failures: list[str] = []

    target_rps_min = float(targets.get("rps_min", 0))
    target_p95_max = float(targets.get("p95_ms_max", 0))
    target_error_rate_max = float(targets.get("error_rate_max", 1))
    target_checks_rate_min = float(targets.get("checks_rate_min", 0))

    if metrics.rps < target_rps_min:
        failures.append(f"RPS below target: {metrics.rps:.2f} < {target_rps_min:.2f}")
    if metrics.p95_ms > target_p95_max:
        failures.append(
            f"P95 latency above target: {metrics.p95_ms:.2f}ms > {target_p95_max:.2f}ms"
        )
    if metrics.error_rate > target_error_rate_max:
        failures.append(
            f"Error rate above target: {metrics.error_rate:.4f} > {target_error_rate_max:.4f}"
        )
    if metrics.checks_rate < target_checks_rate_min:
        failures.append(
            f"Checks success below target: {metrics.checks_rate:.4f} < {target_checks_rate_min:.4f}"
        )

    baseline_rps = float(baseline.get("rps", 0))
    baseline_p95 = float(baseline.get("p95_ms", 0))
    max_rps_drop_pct = float(regression.get("max_rps_drop_pct", 0))
    max_p95_increase_pct = float(regression.get("max_p95_increase_pct", 0))

    if baseline_rps > 0 and max_rps_drop_pct > 0:
        min_allowed_rps = baseline_rps * (1 - max_rps_drop_pct / 100.0)
        if metrics.rps < min_allowed_rps:
            failures.append(
                "RPS regression exceeded: "
                f"{metrics.rps:.2f} < {min_allowed_rps:.2f} "
                f"(baseline {baseline_rps:.2f}, drop limit {max_rps_drop_pct:.2f}%)"
            )

    if baseline_p95 > 0 and max_p95_increase_pct > 0:
        max_allowed_p95 = baseline_p95 * (1 + max_p95_increase_pct / 100.0)
        if metrics.p95_ms > max_allowed_p95:
            failures.append(
                "P95 regression exceeded: "
                f"{metrics.p95_ms:.2f}ms > {max_allowed_p95:.2f}ms "
                f"(baseline {baseline_p95:.2f}ms, increase limit {max_p95_increase_pct:.2f}%)"
            )

    return (len(failures) == 0), failures


def write_report(path: Path, metrics: LoadMetrics, ok: bool, failures: list[str]) -> None:
    lines = [
        "# Load Test Regression Report",
        "",
        f"- Status: {'PASS' if ok else 'FAIL'}",
        f"- RPS: {metrics.rps:.2f}",
        f"- P95 latency: {metrics.p95_ms:.2f} ms",
        f"- Error rate: {metrics.error_rate:.4f}",
        f"- Checks success: {metrics.checks_rate:.4f}",
        "",
    ]
    if failures:
        lines.append("## Failures")
        for failure in failures:
            lines.append(f"- {failure}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    metrics = parse_k6_summary(args.summary)
    baseline_cfg = json.loads(args.baseline.read_text(encoding="utf-8"))
    ok, failures = evaluate(metrics, baseline_cfg)
    write_report(args.report, metrics, ok, failures)

    print(
        "Load test summary: "
        f"rps={metrics.rps:.2f}, p95={metrics.p95_ms:.2f}ms, "
        f"error_rate={metrics.error_rate:.4f}, checks={metrics.checks_rate:.4f}"
    )
    if not ok:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("PASS: load metrics are within target and regression limits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
