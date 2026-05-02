#!/usr/bin/env python3
"""Run k6 load profiles and evaluate regression budgets."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_profiles(config_path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    profiles = payload.get("profiles", {})
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError("Config must contain non-empty 'profiles' mapping.")
    return profiles


def _python_cmd() -> list[str]:
    return [sys.executable]


def _docker_k6_command(
    profile: str,
    profile_cfg: dict[str, Any],
    base_url: str,
    workspace: Path,
    artifacts_dir: Path,
    docker_image: str,
) -> list[str]:
    target_rps = float(profile_cfg.get("target_rps", 30.0))
    endpoints = profile_cfg.get("endpoints", [])
    if not isinstance(endpoints, list) or not endpoints:
        raise ValueError(f"Profile '{profile}' has no endpoints configured.")

    command = [
        "docker",
        "run",
        "--rm",
        "--network=host",
    ]
    if hasattr(os, "getuid") and hasattr(os, "getgid"):
        command.extend(["--user", f"{os.getuid()}:{os.getgid()}"])

    command.extend(
        [
            "-e",
            f"BASE_URL={base_url}",
            "-e",
            f"TARGET_RPS={target_rps}",
            "-e",
            f"K6_PROFILE={profile}",
            "-e",
            f"K6_ENDPOINTS_JSON={json.dumps(endpoints, ensure_ascii=False)}",
            "-v",
            f"{(workspace / 'ops' / 'load').as_posix()}:/scripts",
            "-v",
            f"{artifacts_dir.as_posix()}:/artifacts",
            docker_image,
            "run",
            "/scripts/clinic_core.js",
            f"--summary-export=/artifacts/profiles/{profile}/k6-summary.json",
        ]
    )
    return command


def _regression_check_command(
    summary_path: Path,
    config_path: Path,
    report_path: Path,
    report_json_path: Path,
    profile: str,
) -> list[str]:
    return _python_cmd() + [
        "ops/scripts/check_load_regression.py",
        "--summary",
        str(summary_path),
        "--baseline",
        str(config_path),
        "--profile",
        profile,
        "--report",
        str(report_path),
        "--report-json",
        str(report_json_path),
    ]


def _fallback_summary(reason: str) -> dict[str, Any]:
    return {
        "error": reason,
        "metrics": {},
    }


def _build_aggregate_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Load Test Regression Report",
        "",
        f"- Generated at: `{datetime.now(UTC).isoformat()}`",
        f"- Profiles checked: `{len(rows)}`",
        "",
        "| Profile | Status | RPS | P95 ms | Error rate | Checks |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for row in rows:
        metrics = row.get("metrics", {})
        lines.append(
            "| `{profile}` | {status} | {rps:.2f} | {p95:.2f} | {err:.4f} | {checks:.4f} |".format(
                profile=row.get("profile", "unknown"),
                status=row.get("status", "FAIL"),
                rps=float(metrics.get("rps", 0.0)),
                p95=float(metrics.get("p95_ms", 0.0)),
                err=float(metrics.get("error_rate", 1.0)),
                checks=float(metrics.get("checks_rate", 0.0)),
            )
        )

    failing = [row for row in rows if row.get("status") != "PASS"]
    if failing:
        lines.extend(["", "## Failures"])
        for row in failing:
            lines.append(f"- `{row.get('profile', 'unknown')}`")
            for failure in row.get("failures", []):
                lines.append(f"  - {failure}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--workspace", default=Path.cwd(), type=Path)
    parser.add_argument("--artifacts-dir", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--docker-image", default="grafana/k6:latest")
    parser.add_argument("--api-ready", default=1, type=int)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    artifacts_dir = args.artifacts_dir.resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    profiles = _load_profiles(args.config)
    profile_reports: list[dict[str, Any]] = []
    profile_summaries: dict[str, dict[str, Any]] = {}
    had_error = False

    for profile, profile_cfg in profiles.items():
        profile_dir = artifacts_dir / "profiles" / profile
        profile_dir.mkdir(parents=True, exist_ok=True)
        summary_path = profile_dir / "k6-summary.json"
        report_path = profile_dir / "load-regression-report.md"
        report_json_path = profile_dir / "load-regression-report.json"

        if args.api_ready != 1:
            had_error = True
            _write_json(summary_path, _fallback_summary("API was not ready for load test"))
        else:
            run_cmd = _docker_k6_command(
                profile=profile,
                profile_cfg=profile_cfg,
                base_url=args.base_url,
                workspace=workspace,
                artifacts_dir=artifacts_dir,
                docker_image=args.docker_image,
            )
            print(f"[load] running profile={profile}")
            run_proc = subprocess.run(run_cmd, check=False)
            if run_proc.returncode != 0:
                had_error = True
                print(f"[load] k6 failed for profile={profile}, exit={run_proc.returncode}")
                if not summary_path.exists():
                    _write_json(
                        summary_path,
                        _fallback_summary(
                            f"k6 failed with exit code {run_proc.returncode} and no summary"
                        ),
                    )

        reg_cmd = _regression_check_command(
            summary_path=summary_path,
            config_path=args.config,
            report_path=report_path,
            report_json_path=report_json_path,
            profile=profile,
        )
        reg_proc = subprocess.run(reg_cmd, cwd=workspace, check=False)
        if reg_proc.returncode != 0:
            had_error = True
            print(f"[load] regression check failed for profile={profile}, exit={reg_proc.returncode}")

        if report_json_path.exists():
            report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
        else:
            report_payload = {
                "profile": profile,
                "status": "FAIL",
                "metrics": {
                    "rps": 0.0,
                    "p95_ms": 0.0,
                    "error_rate": 1.0,
                    "checks_rate": 0.0,
                },
                "failures": ["Regression report JSON was not generated."],
            }
            had_error = True
            _write_json(report_json_path, report_payload)

        profile_reports.append(report_payload)
        if summary_path.exists():
            profile_summaries[profile] = json.loads(summary_path.read_text(encoding="utf-8"))
        else:
            had_error = True
            profile_summaries[profile] = _fallback_summary("k6 summary missing")

    aggregate_summary_path = artifacts_dir / "k6-summary.json"
    aggregate_report_path = artifacts_dir / "load-regression-report.md"
    aggregate_report_json_path = artifacts_dir / "load-regression-report.json"

    _write_json(
        aggregate_summary_path,
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "profiles": profile_summaries,
        },
    )
    aggregate_report_path.write_text(
        _build_aggregate_markdown(profile_reports),
        encoding="utf-8",
    )
    _write_json(
        aggregate_report_json_path,
        {
            "generated_at": datetime.now(UTC).isoformat(),
            "profiles": profile_reports,
        },
    )

    if had_error:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
