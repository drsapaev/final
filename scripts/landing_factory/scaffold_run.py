from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil


AUDIT_FILES = [
    "design-audit.json",
    "ux-audit.json",
    "accessibility-audit.json",
    "seo-audit.json",
    "performance-audit.json",
    "conversion-audit.json",
    "visual-audit.json",
]

AUDIT_AGENTS = {
    "design-audit.json": "landing-design-audit",
    "ux-audit.json": "landing-ux-audit",
    "accessibility-audit.json": "landing-accessibility",
    "seo-audit.json": "landing-seo",
    "performance-audit.json": "landing-performance",
    "conversion-audit.json": "landing-conversion",
    "visual-audit.json": "landing-visual-qa",
}

TEMPLATE_MAP = {
    "landing_brief.template.json": Path("briefs/landing_brief.json"),
    "brand_constraints.template.json": Path("briefs/brand_constraints.json"),
    "success_metrics.template.json": Path("briefs/success_metrics.json"),
    "task_graph.template.json": Path("plans/task_graph.json"),
    "pipeline_plan.template.md": Path("plans/pipeline_plan.md"),
    "build_status.template.json": Path("plans/build_status.json"),
    "tokens.template.json": Path("design/tokens.json"),
    "layout-spec.template.json": Path("design/layout-spec.json"),
    "landing-copy.template.md": Path("content/landing-copy.md"),
    "seo-meta.template.json": Path("content/seo-meta.json"),
    "schema.template.json": Path("content/schema.json"),
    "qa-scorecard.template.json": Path("release/qa-scorecard.json"),
    "preview-summary.template.md": Path("release/preview-summary.md"),
    "release-notes.template.md": Path("release/release-notes.md"),
}


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "landing"


def copy_template(template_path: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template_path, destination)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def build_manifest(run_id: str, slug: str) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "run_id": run_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "slug": slug,
        "status": "initialized",
        "stage": "intake",
        "history": [
            {
                "stage": "intake",
                "event": "initialized",
                "timestamp": timestamp,
                "reason": "run scaffold created",
            }
        ],
        "stage_status": {
            "intake": {
                "ready": False,
                "missing": [],
                "owner_skills": ["landing-intake"],
                "summary": "Waiting for brief artifacts.",
                "checked_at": None,
                "skill_checks": [],
                "recommended_skill": None,
            },
            "build": {
                "ready": False,
                "missing": [],
                "owner_skills": [
                    "landing-strategy",
                    "landing-copy",
                    "landing-design-system",
                    "landing-ui-build",
                ],
                "summary": "Waiting for strategy, copy, design, and UI implementation.",
                "checked_at": None,
                "skill_checks": [],
                "recommended_skill": None,
            },
            "audit": {
                "ready": False,
                "missing": [],
                "owner_skills": [
                    "landing-design-audit",
                    "landing-ux-audit",
                    "landing-accessibility",
                    "landing-seo",
                    "landing-performance",
                    "landing-visual-qa",
                    "landing-conversion",
                ],
                "summary": "Waiting for audit evidence.",
                "checked_at": None,
                "skill_checks": [],
                "recommended_skill": None,
            },
            "release": {
                "ready": False,
                "missing": [],
                "owner_skills": ["landing-release", "landing-orchestrator"],
                "summary": "Waiting for release scorecard aggregation.",
                "checked_at": None,
                "outcome": "pending",
                "skill_checks": [],
                "recommended_skill": None,
                "repair_queue": [],
            },
        },
        "next_actions": [
            "Run landing-intake to fill the brief artifacts.",
            "Use run_pipeline.py status or sync to refresh manifest state.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a new AI Landing Factory run with scaffolded artifacts."
    )
    parser.add_argument(
        "--root",
        default=".ai-factory/landing",
        help="Landing factory root directory.",
    )
    parser.add_argument(
        "--slug",
        default="landing",
        help="Human-readable label used in the run id.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow reusing an existing run directory.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    root = Path(args.root).resolve()
    templates_dir = root / "templates"
    runs_dir = root / "runs"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}-{slugify(args.slug)}"
    run_dir = runs_dir / run_id

    if not templates_dir.exists():
        raise SystemExit(f"Template directory not found: {templates_dir}")

    if run_dir.exists() and not args.force:
        raise SystemExit(
            f"Run directory already exists: {run_dir}. Re-run with --force to reuse it."
        )

    for relative in [
        Path("briefs"),
        Path("plans"),
        Path("design/screenshot-baseline"),
        Path("content"),
        Path("audits"),
        Path("release"),
    ]:
        (run_dir / relative).mkdir(parents=True, exist_ok=True)

    for template_name, output_path in TEMPLATE_MAP.items():
        copy_template(templates_dir / template_name, run_dir / output_path)

    audit_template = json.loads((templates_dir / "audit.template.json").read_text(encoding="utf-8"))
    for audit_name in AUDIT_FILES:
        audit_payload = dict(audit_template)
        audit_payload["agent"] = AUDIT_AGENTS[audit_name]
        write_json(run_dir / "audits" / audit_name, audit_payload)

    manifest_path = run_dir / "run-manifest.json"
    write_json(manifest_path, build_manifest(run_id, slugify(args.slug)))

    print(f"Created landing run: {run_dir}")
    print(f"Manifest: {manifest_path}")
    print("Next step: fill the brief artifacts with landing-intake.")
    print(f"Optional: python scripts/landing_factory/run_pipeline.py status {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
