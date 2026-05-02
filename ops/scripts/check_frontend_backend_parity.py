#!/usr/bin/env python3
"""Fail CI when frontend-backend parity quality gates are not met."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

LOGGER = logging.getLogger("frontend_backend_parity_gate")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate frontend-backend parity gates.")
    parser.add_argument(
        "--parity-json",
        type=Path,
        default=Path("docs/reports/frontend_backend_parity.json"),
        help="Parity report JSON path.",
    )
    parser.add_argument(
        "--ux-json",
        type=Path,
        default=Path("docs/reports/frontend_ux_correctness_scorecard.json"),
        help="UX scorecard JSON path.",
    )
    parser.add_argument(
        "--min-correctness",
        type=float,
        default=4.0,
        help="Minimum average correctness score.",
    )
    parser.add_argument(
        "--min-usability",
        type=float,
        default=4.0,
        help="Minimum average usability score.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    LOGGER.info("frontend_backend_parity_gate.start")

    parity = json.loads(args.parity_json.read_text(encoding="utf-8"))
    ux = json.loads(args.ux_json.read_text(encoding="utf-8"))

    failures: list[str] = []

    critical_flow_summary = parity.get("critical_flows", {}).get("summary", {})
    failed_flows = int(critical_flow_summary.get("failed_flows", 0))
    if failed_flows > 0:
        failures.append(f"critical flow failures: {failed_flows}")

    rbac_status = str(parity.get("rbac_alignment", {}).get("status", "fail"))
    if rbac_status != "pass":
        failures.append(f"rbac alignment status: {rbac_status}")

    avg_correctness = float(ux.get("summary", {}).get("avg_correctness", 0.0))
    if avg_correctness < args.min_correctness:
        failures.append(
            f"avg_correctness {avg_correctness:.2f} < required {args.min_correctness:.2f}"
        )

    avg_usability = float(ux.get("summary", {}).get("avg_usability", 0.0))
    if avg_usability < args.min_usability:
        failures.append(
            f"avg_usability {avg_usability:.2f} < required {args.min_usability:.2f}"
        )

    LOGGER.info(
        (
            "frontend_backend_parity_gate.summary coverage_pct=%.2f "
            "failed_flows=%d rbac_status=%s avg_correctness=%.2f avg_usability=%.2f"
        ),
        float(parity.get("summary", {}).get("coverage_pct", 0.0)),
        failed_flows,
        rbac_status,
        avg_correctness,
        avg_usability,
    )

    if failures:
        for failure in failures:
            LOGGER.error("frontend_backend_parity_gate.fail reason=%s", failure)
        return 1

    LOGGER.info("frontend_backend_parity_gate.pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
