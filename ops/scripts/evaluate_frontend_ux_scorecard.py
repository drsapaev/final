#!/usr/bin/env python3
"""Evaluate frontend UX correctness/usability scorecard for critical modules."""

from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

LOGGER = logging.getLogger("frontend_ux_scorecard")

MODULE_SPECS = [
    {
        "id": "registrar_queue",
        "name": "Registrar Queue",
        "files": [
            "frontend/src/pages/RegistrarPanel.jsx",
            "frontend/src/components/wizard/AppointmentWizardV2.jsx",
            "frontend/src/api/queue.js",
        ],
    },
    {
        "id": "doctor_emr_rw",
        "name": "Doctor EMR Read/Write",
        "files": [
            "frontend/src/pages/DoctorPanel.jsx",
            "frontend/src/hooks/useDoctorPhrases.js",
            "frontend/src/hooks/useDoctorTreatmentTemplates.js",
        ],
    },
    {
        "id": "cashier_payment",
        "name": "Cashier Payment",
        "files": [
            "frontend/src/pages/CashierPanel.jsx",
            "frontend/src/hooks/usePayments.js",
            "frontend/src/services/payment.js",
        ],
    },
    {
        "id": "admin_settings",
        "name": "Admin Settings",
        "files": [
            "frontend/src/pages/AdminPanel.jsx",
            "frontend/src/pages/Settings.jsx",
            "frontend/src/hooks/useSettings.js",
        ],
    },
]

INDICATOR_PATTERNS = {
    "loading": re.compile(r"\bloading\b|isLoading|setLoading|Loader|Spinner|skeleton", re.IGNORECASE),
    "error_handling": re.compile(
        r"\berror\b|setError|toast\.error|alert\(|catch\s*\(|retry|try\s+again|повтор|ошиб",
        re.IGNORECASE,
    ),
    "empty_state": re.compile(
        r"\bempty\b|no\s+data|no\s+results|нет\s+данных|ничего\s+не|length\s*===\s*0|\.length\s*===\s*0",
        re.IGNORECASE,
    ),
    "validation_feedback": re.compile(
        r"\bvalidation\b|required\b|errors?\.|isValid|invalid|yup|zod|formState|setFieldError",
        re.IGNORECASE,
    ),
    "a11y_keyboard": re.compile(
        r"aria-|tabIndex|onKeyDown|onKeyUp|onKeyPress|htmlFor|autoFocus|focus\(|<label|role=",
        re.IGNORECASE,
    ),
    "recovery_actions": re.compile(
        r"retry|refresh|reload|restore|undo|fallback|recover|повтор|обновить",
        re.IGNORECASE,
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build UX correctness scorecard.")
    parser.add_argument(
        "--parity-json",
        type=Path,
        default=Path("docs/reports/frontend_backend_parity.json"),
        help="Parity JSON with critical flow status.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/reports/FRONTEND_UX_CORRECTNESS_SCORECARD.md"),
        help="Markdown output path.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("docs/reports/frontend_ux_correctness_scorecard.json"),
        help="JSON output path.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser.parse_args()


def load_critical_flow_status(parity_json_path: Path) -> dict[str, str]:
    data = json.loads(parity_json_path.read_text(encoding="utf-8"))
    flows = data.get("critical_flows", {}).get("flows", [])
    mapping = {flow.get("id"): flow.get("status", "fail") for flow in flows}
    LOGGER.info(
        "frontend_ux_scorecard.critical_flows_loaded file=%s flows=%d",
        parity_json_path.as_posix(),
        len(mapping),
    )
    return mapping


def _read_existing_files(paths: list[str]) -> tuple[str, list[str]]:
    chunks: list[str] = []
    existing: list[str] = []
    for path in paths:
        file_path = Path(path)
        if file_path.exists():
            existing.append(path)
            chunks.append(file_path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks), existing


def _score_to_text(score: float) -> str:
    if score >= 4.5:
        return "excellent"
    if score >= 4.0:
        return "good"
    if score >= 3.0:
        return "fair"
    return "poor"


def evaluate_modules(flow_status: dict[str, str]) -> dict:
    modules: list[dict] = []
    for spec in MODULE_SPECS:
        content, existing_files = _read_existing_files(spec["files"])
        indicators = {
            name: bool(pattern.search(content))
            for name, pattern in INDICATOR_PATTERNS.items()
        }

        flow_pass = flow_status.get(spec["id"], "fail") == "pass"
        correctness_factors = [
            indicators["loading"],
            indicators["error_handling"],
            indicators["validation_feedback"],
            flow_pass,
        ]
        usability_factors = [
            indicators["empty_state"],
            indicators["a11y_keyboard"],
            indicators["recovery_actions"],
            indicators["loading"],
        ]
        correctness = round((sum(correctness_factors) / len(correctness_factors)) * 5, 2)
        usability = round((sum(usability_factors) / len(usability_factors)) * 5, 2)

        missing_gaps: list[str] = []
        for key, is_present in indicators.items():
            if not is_present:
                missing_gaps.append(key)
        if not flow_pass:
            missing_gaps.append("critical_flow_contract_mismatch")

        LOGGER.info(
            "frontend_ux_scorecard.module id=%s correctness=%.2f usability=%.2f files=%d flow=%s",
            spec["id"],
            correctness,
            usability,
            len(existing_files),
            "pass" if flow_pass else "fail",
        )
        if missing_gaps:
            LOGGER.debug(
                "frontend_ux_scorecard.module_gaps id=%s gaps=%s",
                spec["id"],
                ",".join(missing_gaps),
            )

        modules.append(
            {
                "id": spec["id"],
                "name": spec["name"],
                "files_scanned": existing_files,
                "indicators": indicators,
                "critical_flow_status": "pass" if flow_pass else "fail",
                "correctness_score": correctness,
                "usability_score": usability,
                "grade": {
                    "correctness": _score_to_text(correctness),
                    "usability": _score_to_text(usability),
                },
                "gaps": missing_gaps,
            }
        )

    avg_correctness = round(
        sum(module["correctness_score"] for module in modules) / len(modules),
        2,
    )
    avg_usability = round(
        sum(module["usability_score"] for module in modules) / len(modules),
        2,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "modules_total": len(modules),
            "avg_correctness": avg_correctness,
            "avg_usability": avg_usability,
        },
        "modules": modules,
    }


def build_markdown(scorecard: dict) -> str:
    lines: list[str] = []
    lines.append("# Frontend UX Correctness Scorecard")
    lines.append("")
    lines.append(f"Generated at: {scorecard['generated_at']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Modules: **{scorecard['summary']['modules_total']}**")
    lines.append(f"- Average Correctness: **{scorecard['summary']['avg_correctness']} / 5**")
    lines.append(f"- Average Usability: **{scorecard['summary']['avg_usability']} / 5**")
    lines.append("")
    lines.append("## Module Scores")
    lines.append("")
    lines.append("| Module | Critical Flow | Correctness | Usability |")
    lines.append("|---|---|---:|---:|")
    for module in scorecard["modules"]:
        lines.append(
            "| "
            + f"{module['name']} "
            + f"| {module['critical_flow_status']} "
            + f"| {module['correctness_score']} "
            + f"| {module['usability_score']} |"
        )
    lines.append("")
    lines.append("## Gaps")
    lines.append("")
    for module in scorecard["modules"]:
        if module["gaps"]:
            lines.append(f"- `{module['id']}`: " + ", ".join(f"`{gap}`" for gap in module["gaps"]))
        else:
            lines.append(f"- `{module['id']}`: no critical gaps detected")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    LOGGER.info("frontend_ux_scorecard.start")

    flow_status = load_critical_flow_status(args.parity_json)
    scorecard = evaluate_modules(flow_status)
    markdown = build_markdown(scorecard)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(scorecard, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    LOGGER.info(
        "frontend_ux_scorecard.done avg_correctness=%.2f avg_usability=%.2f output_md=%s output_json=%s",
        scorecard["summary"]["avg_correctness"],
        scorecard["summary"]["avg_usability"],
        args.output.as_posix(),
        args.output_json.as_posix(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
