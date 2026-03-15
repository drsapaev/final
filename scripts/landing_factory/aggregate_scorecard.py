from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


AUDIT_PATHS = {
    "design": Path("audits/design-audit.json"),
    "ux": Path("audits/ux-audit.json"),
    "accessibility": Path("audits/accessibility-audit.json"),
    "seo": Path("audits/seo-audit.json"),
    "performance": Path("audits/performance-audit.json"),
    "conversion": Path("audits/conversion-audit.json"),
    "visual": Path("audits/visual-audit.json"),
}

MIN_TARGETS = {
    "lighthouse_performance",
    "lighthouse_accessibility",
    "lighthouse_seo",
    "lighthouse_best_practices",
}

MAX_TARGETS = {
    "lcp_seconds",
    "cls",
    "inp_ms",
    "broken_links",
    "console_errors",
    "critical_axe_violations",
}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_metric(metric: str, target: float | int | None, value: float | int | None) -> str:
    if target is None or value is None:
        return "pending"
    if metric in MIN_TARGETS:
        return "passed" if value >= target else "failed"
    if metric in MAX_TARGETS:
        return "passed" if value <= target else "failed"
    return "pending"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate landing audit artifacts into release/qa-scorecard.json."
    )
    parser.add_argument("run_dir", help="Path to a single landing run directory.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    run_dir = Path(args.run_dir).resolve()

    if not run_dir.exists():
        raise SystemExit(f"Run directory not found: {run_dir}")

    success_metrics = load_json(run_dir / "briefs" / "success_metrics.json")
    scorecard_path = run_dir / "release" / "qa-scorecard.json"
    scorecard = load_json(scorecard_path)

    targets = success_metrics.get("quality_targets") or scorecard.get("targets", {})
    results = scorecard.get("results", {})

    blocking_failures: list[str] = []
    pending_gates: list[str] = []
    passed_gates: list[str] = []
    audits_summary: dict[str, dict] = {}

    for audit_name, relative_path in AUDIT_PATHS.items():
        audit = load_json(run_dir / relative_path)
        status = audit.get("status", "pending")
        critical = len(audit.get("critical_issues", []))
        medium = len(audit.get("medium_issues", []))
        minor = len(audit.get("minor_improvements", []))
        audits_summary[audit_name] = {
            "status": status,
            "critical": critical,
            "medium": medium,
            "minor": minor,
        }
        if status == "pending":
            pending_gates.append(f"audit:{audit_name}")
        elif status == "failed" or critical > 0:
            blocking_failures.append(f"audit:{audit_name}")
        else:
            passed_gates.append(f"audit:{audit_name}")

    metric_checks: dict[str, dict] = {}
    for metric_name, target_value in targets.items():
        current_value = results.get(metric_name)
        status = evaluate_metric(metric_name, target_value, current_value)
        metric_checks[metric_name] = {
            "target": target_value,
            "value": current_value,
            "status": status,
        }
        gate_name = f"metric:{metric_name}"
        if status == "passed":
            passed_gates.append(gate_name)
        elif status == "failed":
            blocking_failures.append(gate_name)
        else:
            pending_gates.append(gate_name)

    overall_status = "passed"
    if blocking_failures:
        overall_status = "failed"
    elif pending_gates:
        overall_status = "pending"

    scorecard["targets"] = targets
    scorecard["audits"] = audits_summary
    scorecard["metric_checks"] = metric_checks
    scorecard["summary"] = {
        "status": overall_status,
        "ready_for_preview": overall_status == "passed",
        "blocking_failures": blocking_failures,
        "pending_gates": pending_gates,
        "passed_gates": passed_gates,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    scorecard_path.write_text(
        json.dumps(scorecard, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    print(f"Updated scorecard: {scorecard_path}")
    print(f"Overall status: {overall_status}")
    print(f"Blocking failures: {len(blocking_failures)}")
    print(f"Pending gates: {len(pending_gates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
