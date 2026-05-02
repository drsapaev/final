from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys


STAGES = ("intake", "build", "audit", "release")
NEXT_STAGE = {
    "intake": "build",
    "build": "audit",
    "audit": "release",
    "release": None,
}

STAGE_OWNERS = {
    "intake": ["landing-intake"],
    "build": [
        "landing-strategy",
        "landing-copy",
        "landing-design-system",
        "landing-ui-build",
    ],
    "audit": [
        "landing-design-audit",
        "landing-ux-audit",
        "landing-accessibility",
        "landing-seo",
        "landing-performance",
        "landing-visual-qa",
        "landing-conversion",
    ],
    "release": ["landing-release", "landing-orchestrator"],
}

AUDIT_FILES = {
    "landing-design-audit": Path("audits/design-audit.json"),
    "landing-ux-audit": Path("audits/ux-audit.json"),
    "landing-accessibility": Path("audits/accessibility-audit.json"),
    "landing-seo": Path("audits/seo-audit.json"),
    "landing-performance": Path("audits/performance-audit.json"),
    "landing-conversion": Path("audits/conversion-audit.json"),
    "landing-visual-qa": Path("audits/visual-audit.json"),
}

SKILL_PRIORITY = {
    "failed": 0,
    "needs_repair": 1,
    "pending": 2,
    "in_progress": 3,
    "completed": 9,
    "passed": 9,
}

RELEASE_GATE_SKILL_MAP = {
    "audit:design": ("landing-design-audit", "Design audit is blocking release."),
    "audit:ux": ("landing-ux-audit", "UX audit is blocking release."),
    "audit:accessibility": ("landing-accessibility", "Accessibility audit is blocking release."),
    "audit:seo": ("landing-seo", "SEO audit is blocking release."),
    "audit:performance": ("landing-performance", "Performance audit is blocking release."),
    "audit:conversion": ("landing-conversion", "Conversion audit is blocking release."),
    "audit:visual": ("landing-visual-qa", "Visual QA is blocking release."),
    "metric:lighthouse_performance": (
        "landing-performance",
        "Performance score is below the configured threshold.",
    ),
    "metric:lcp_seconds": ("landing-performance", "LCP is slower than the target."),
    "metric:cls": ("landing-performance", "CLS exceeds the target."),
    "metric:inp_ms": ("landing-performance", "INP exceeds the target."),
    "metric:lighthouse_accessibility": (
        "landing-accessibility",
        "Accessibility score is below the configured threshold.",
    ),
    "metric:critical_axe_violations": (
        "landing-accessibility",
        "Critical Axe violations must be fixed before release.",
    ),
    "metric:lighthouse_seo": ("landing-seo", "SEO score is below the configured threshold."),
    "metric:broken_links": ("landing-seo", "Broken links were detected on the landing."),
    "metric:lighthouse_best_practices": (
        "landing-ui-build",
        "Best-practices issues require implementation fixes.",
    ),
    "metric:console_errors": ("landing-ui-build", "Console errors require UI fixes."),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def has_text(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(has_text(item) for item in value)
    if isinstance(value, dict):
        return any(has_text(item) for item in value.values())
    return True


def differs_from_template(path: Path, template_path: Path) -> bool:
    if not path.exists() or not template_path.exists():
        return False
    return path.read_text(encoding="utf-8").strip() != template_path.read_text(encoding="utf-8").strip()


def stage_index(stage: str) -> int:
    return STAGES.index(stage)


def build_default_manifest(run_dir: Path) -> dict:
    timestamp = now_iso()
    return {
        "run_id": run_dir.name,
        "created_at": timestamp,
        "updated_at": timestamp,
        "slug": run_dir.name,
        "status": "initialized",
        "stage": "intake",
        "history": [
            {
                "stage": "intake",
                "event": "initialized",
                "timestamp": timestamp,
                "reason": "manifest backfilled by run_pipeline.py",
            }
        ],
        "stage_status": {},
        "next_actions": [],
    }


def empty_stage_report(stage: str) -> dict:
    report = {
        "ready": False,
        "missing": [],
        "owner_skills": STAGE_OWNERS[stage],
        "summary": "",
        "checked_at": None,
        "skill_checks": [],
        "recommended_skill": None,
    }
    if stage == "release":
        report["outcome"] = "pending"
        report["repair_queue"] = []
    return report


def ensure_manifest_schema(manifest: dict, run_dir: Path) -> dict:
    normalized = build_default_manifest(run_dir)
    normalized.update(manifest)
    normalized["run_id"] = normalized.get("run_id") or run_dir.name
    normalized["slug"] = normalized.get("slug") or run_dir.name
    normalized["stage"] = normalized.get("stage") or "intake"
    normalized["history"] = normalized.get("history") or []
    normalized["stage_status"] = normalized.get("stage_status") or {}
    normalized["next_actions"] = normalized.get("next_actions") or []

    for stage in STAGES:
        defaults = empty_stage_report(stage)
        existing = normalized["stage_status"].get(stage, {})
        defaults.update(existing)
        defaults["owner_skills"] = STAGE_OWNERS[stage]
        if stage == "release":
            defaults["repair_queue"] = defaults.get("repair_queue") or []
            defaults["outcome"] = defaults.get("outcome") or "pending"
        defaults["skill_checks"] = defaults.get("skill_checks") or []
        defaults["recommended_skill"] = defaults.get("recommended_skill")
        normalized["stage_status"][stage] = defaults
    return normalized


def template_root(run_dir: Path) -> Path:
    return run_dir.parent.parent / "templates"


def make_skill_check(
    skill: str,
    blocking_items: list[str],
    pending_reason: str,
    complete_reason: str,
    *,
    status_override: str | None = None,
    reason_override: str | None = None,
) -> dict:
    status = status_override or ("pending" if blocking_items else "completed")
    if reason_override is not None:
        reason = reason_override
    elif status in {"completed", "passed"}:
        reason = complete_reason
    else:
        reason = pending_reason
    return {
        "skill": skill,
        "status": status,
        "reason": reason,
        "blocking_items": blocking_items,
    }


def flatten_blocking_items(skill_checks: list[dict]) -> list[str]:
    items: list[str] = []
    for check in skill_checks:
        items.extend(check.get("blocking_items", []))
    return items


def select_recommended_skill(skill_checks: list[dict]) -> dict | None:
    actionable = [check for check in skill_checks if check["status"] not in {"completed", "passed"}]
    if not actionable:
        return None
    selected = sorted(
        actionable,
        key=lambda check: (SKILL_PRIORITY.get(check["status"], 99), skill_checks.index(check)),
    )[0]
    return {
        "skill": selected["skill"],
        "reason": selected["reason"],
        "blocking_items": selected.get("blocking_items", []),
        "status": selected["status"],
    }


def summarize_issue_prefix(items: list[object], label: str) -> list[str]:
    count = len(items)
    if count == 0:
        return []
    return [f"{label}: {count}"]


def inspect_intake(run_dir: Path, templates_dir: Path) -> dict:
    brief_path = run_dir / "briefs/landing_brief.json"
    brand_path = run_dir / "briefs/brand_constraints.json"
    metrics_path = run_dir / "briefs/success_metrics.json"
    brief = load_json(brief_path)
    brand = load_json(brand_path)
    metrics = load_json(metrics_path)

    intake_items: list[str] = []

    if not differs_from_template(brief_path, templates_dir / "landing_brief.template.json"):
        intake_items.append("briefs/landing_brief.json is still using the starter template")
    if not has_text(brief.get("problem")):
        intake_items.append("briefs/landing_brief.json missing `problem`")
    if not has_text(brief.get("promise")):
        intake_items.append("briefs/landing_brief.json missing `promise`")
    if not has_text(brief.get("primary_audience")):
        intake_items.append("briefs/landing_brief.json missing `primary_audience`")
    if not has_text(brief.get("primary_cta")):
        intake_items.append("briefs/landing_brief.json missing `primary_cta`")

    if not differs_from_template(brand_path, templates_dir / "brand_constraints.template.json"):
        intake_items.append("briefs/brand_constraints.json is still using the starter template")
    if not has_text(brand.get("tone", {}).get("voice")):
        intake_items.append("briefs/brand_constraints.json missing tone.voice")
    visual_direction = brand.get("visual_direction", {})
    if not (has_text(visual_direction.get("mood")) or has_text(visual_direction.get("color_biases"))):
        intake_items.append("briefs/brand_constraints.json missing visual direction")

    if not differs_from_template(metrics_path, templates_dir / "success_metrics.template.json"):
        intake_items.append("briefs/success_metrics.json is still using the starter template")
    business_targets = metrics.get("business_targets", {})
    if not (
        has_text(business_targets.get("primary_conversion"))
        or has_text(business_targets.get("secondary_conversion"))
    ):
        intake_items.append("briefs/success_metrics.json missing a business conversion target")

    skill_checks = [
        make_skill_check(
            "landing-intake",
            intake_items,
            "Brief, brand, or success metrics still need to be normalized.",
            "Intake artifacts are ready for downstream skills.",
        )
    ]
    ready = not intake_items
    return {
        "ready": ready,
        "missing": intake_items,
        "owner_skills": STAGE_OWNERS["intake"],
        "summary": (
            "Intake artifacts are ready for build."
            if ready
            else "Intake still needs brief, brand, or metric details."
        ),
        "checked_at": now_iso(),
        "skill_checks": skill_checks,
        "recommended_skill": select_recommended_skill(skill_checks),
    }


def inspect_build(run_dir: Path, templates_dir: Path) -> dict:
    plan_path = run_dir / "plans/pipeline_plan.md"
    build_status_path = run_dir / "plans/build_status.json"
    copy_path = run_dir / "content/landing-copy.md"
    tokens_path = run_dir / "design/tokens.json"
    layout_path = run_dir / "design/layout-spec.json"

    build_status = load_json(build_status_path)
    tokens = load_json(tokens_path)
    layout = load_json(layout_path)

    strategy_items: list[str] = []
    copy_items: list[str] = []
    design_items: list[str] = []
    ui_items: list[str] = []

    if not differs_from_template(plan_path, templates_dir / "pipeline_plan.template.md"):
        strategy_items.append("plans/pipeline_plan.md is still using the starter template")

    if not differs_from_template(copy_path, templates_dir / "landing-copy.template.md"):
        copy_items.append("content/landing-copy.md is still using the starter template")

    if not differs_from_template(tokens_path, templates_dir / "tokens.template.json"):
        design_items.append("design/tokens.json is still using the starter template")
    if not differs_from_template(layout_path, templates_dir / "layout-spec.template.json"):
        design_items.append("design/layout-spec.json is still using the starter template")
    if not has_text(tokens.get("colors", {}).get("accent")):
        design_items.append("design/tokens.json missing colors.accent")
    if not (
        has_text(tokens.get("typography", {}).get("display"))
        or has_text(tokens.get("typography", {}).get("body"))
    ):
        design_items.append("design/tokens.json missing typography choices")
    sections = layout.get("sections", [])
    if not sections or not has_text(sections[0].get("intent")):
        design_items.append("design/layout-spec.json missing section intent")

    if build_status.get("ui_status") != "implemented":
        ui_items.append("plans/build_status.json must set `ui_status` to `implemented`")
    if not has_text(build_status.get("entry_files")):
        ui_items.append("plans/build_status.json missing `entry_files`")

    skill_checks = [
        make_skill_check(
            "landing-strategy",
            strategy_items,
            "Section order and strategy notes still need to be written.",
            "Pipeline plan is ready for build execution.",
        ),
        make_skill_check(
            "landing-copy",
            copy_items,
            "Landing copy is still using the starter template.",
            "Landing copy has been drafted for the run.",
        ),
        make_skill_check(
            "landing-design-system",
            design_items,
            "Design tokens or layout spec are incomplete.",
            "Design tokens and layout spec are ready for implementation.",
        ),
        make_skill_check(
            "landing-ui-build",
            ui_items,
            "UI implementation marker is incomplete.",
            "UI implementation marker is ready for audit handoff.",
        ),
    ]
    missing = flatten_blocking_items(skill_checks)
    ready = not missing
    return {
        "ready": ready,
        "missing": missing,
        "owner_skills": STAGE_OWNERS["build"],
        "summary": (
            "Build artifacts and implementation marker are ready for audits."
            if ready
            else "Build stage still needs plan, copy, design, or UI implementation evidence."
        ),
        "checked_at": now_iso(),
        "skill_checks": skill_checks,
        "recommended_skill": select_recommended_skill(skill_checks),
    }


def inspect_audit(run_dir: Path) -> dict:
    pending_items: list[str] = []
    skill_checks: list[dict] = []
    audit_states: list[str] = []

    for skill_name, relative_path in AUDIT_FILES.items():
        audit = load_json(run_dir / relative_path)
        status = audit.get("status", "pending")
        critical_items = audit.get("critical_issues", [])
        audit_states.append(f"{skill_name}:{status}")

        if status == "pending":
            blocking_items = [f"{relative_path.as_posix()} still has status `pending`"]
            pending_items.extend(blocking_items)
            skill_checks.append(
                make_skill_check(
                    skill_name,
                    blocking_items,
                    "This audit has not been completed yet.",
                    "Audit completed without blocking findings.",
                )
            )
            continue

        if status == "failed" or critical_items:
            blocking_items = summarize_issue_prefix(critical_items, "blocking findings")
            skill_checks.append(
                make_skill_check(
                    skill_name,
                    blocking_items,
                    "This audit reported blocking issues that must be reviewed in release.",
                    "Audit completed without blocking findings.",
                    status_override="failed",
                    reason_override="This audit has blocking findings recorded in its report.",
                )
            )
            continue

        skill_checks.append(
            make_skill_check(
                skill_name,
                [],
                "This audit has not been completed yet.",
                "Audit completed without blocking findings.",
                status_override="passed",
            )
        )

    scorecard = load_json(run_dir / "release/qa-scorecard.json")
    generated_at = scorecard.get("summary", {}).get("generated_at")
    missing = list(pending_items)
    if not has_text(generated_at):
        missing.append("release/qa-scorecard.json has not been aggregated yet")

    ready = not missing
    return {
        "ready": ready,
        "missing": missing,
        "owner_skills": STAGE_OWNERS["audit"],
        "summary": (
            "Audit swarm is complete and release can begin."
            if ready
            else "Audit evidence is incomplete or scorecard has not been aggregated."
        ),
        "checked_at": now_iso(),
        "audit_states": audit_states,
        "skill_checks": skill_checks,
        "recommended_skill": select_recommended_skill(skill_checks),
    }


def build_release_repair_queue(summary: dict) -> list[dict]:
    grouped: dict[str, dict] = {}
    ordered_gates = list(summary.get("blocking_failures", [])) + list(summary.get("pending_gates", []))

    for gate in ordered_gates:
        skill_name, reason = RELEASE_GATE_SKILL_MAP.get(
            gate,
            ("landing-release", "Release evidence still needs review."),
        )
        status = "needs_repair" if gate in summary.get("blocking_failures", []) else "pending"
        entry = grouped.setdefault(
            skill_name,
            {
                "skill": skill_name,
                "status": status,
                "reason": reason,
                "blocking_items": [],
            },
        )
        if status == "needs_repair":
            entry["status"] = "needs_repair"
        entry["blocking_items"].append(gate)

    return list(grouped.values())


def inspect_release(run_dir: Path, templates_dir: Path) -> dict:
    scorecard = load_json(run_dir / "release/qa-scorecard.json")
    summary = scorecard.get("summary", {})
    outcome = summary.get("status", "pending")

    release_items: list[str] = []
    orchestrator_items: list[str] = []
    if not has_text(summary.get("generated_at")):
        orchestrator_items.append("release/qa-scorecard.json missing generated_at")

    preview_summary_path = run_dir / "release/preview-summary.md"
    release_notes_path = run_dir / "release/release-notes.md"
    if not differs_from_template(preview_summary_path, templates_dir / "preview-summary.template.md"):
        release_items.append("release/preview-summary.md is still using the starter template")
    if not differs_from_template(release_notes_path, templates_dir / "release-notes.template.md"):
        release_items.append("release/release-notes.md is still using the starter template")

    skill_checks = [
        make_skill_check(
            "landing-release",
            release_items,
            "Preview summary or release notes still need to be prepared.",
            "Release notes and preview summary are prepared.",
        ),
        make_skill_check(
            "landing-orchestrator",
            orchestrator_items,
            "Manifest or scorecard state still needs orchestration updates.",
            "Manifest and scorecard state are synchronized.",
        ),
    ]

    repair_queue = build_release_repair_queue(summary)
    missing = flatten_blocking_items(skill_checks)
    if repair_queue:
        missing.extend(flatten_blocking_items(repair_queue))

    if outcome == "passed" and not missing:
        stage_summary = "Release evidence is green and ready for preview approval."
    elif outcome == "failed":
        stage_summary = "Release is blocked by failing gates."
    else:
        stage_summary = "Release is waiting on missing evidence or manual review."

    recommended_skill = select_recommended_skill(repair_queue) or select_recommended_skill(skill_checks)
    return {
        "ready": outcome == "passed" and not missing,
        "missing": missing,
        "owner_skills": STAGE_OWNERS["release"],
        "summary": stage_summary,
        "checked_at": now_iso(),
        "outcome": outcome,
        "skill_checks": skill_checks,
        "repair_queue": repair_queue,
        "recommended_skill": recommended_skill,
    }


def inspect_run(run_dir: Path) -> dict:
    templates_dir = template_root(run_dir)
    return {
        "intake": inspect_intake(run_dir, templates_dir),
        "build": inspect_build(run_dir, templates_dir),
        "audit": inspect_audit(run_dir),
        "release": inspect_release(run_dir, templates_dir),
    }


def append_history(manifest: dict, stage: str, event: str, reason: str) -> None:
    manifest["history"].append(
        {
            "stage": stage,
            "event": event,
            "timestamp": now_iso(),
            "reason": reason,
        }
    )


def derive_status(manifest: dict) -> str:
    stage = manifest["stage"]
    if stage == "release":
        outcome = manifest["stage_status"]["release"].get("outcome", "pending")
        if outcome == "passed":
            return "ready_for_preview"
        if outcome == "failed":
            return "blocked"
        return "in_review"

    next_stage = NEXT_STAGE[stage]
    if manifest["stage_status"][stage]["ready"] and next_stage:
        return f"ready_for_{next_stage}"
    return "in_progress"


def derive_next_actions(manifest: dict) -> list[str]:
    stage = manifest["stage"]
    report = manifest["stage_status"][stage]
    actions: list[str] = []

    if report["missing"]:
        actions.append(f"Current stage `{stage}` still has unmet requirements.")
    elif stage != "release" and NEXT_STAGE[stage]:
        actions.append(
            f"Current stage `{stage}` is ready. Run sync with --auto-advance or advance manually to `{NEXT_STAGE[stage]}`."
        )
    else:
        outcome = manifest["stage_status"]["release"].get("outcome", "pending")
        if outcome == "passed":
            actions.append("Release gates passed. Ready for preview approval.")
        elif outcome == "failed":
            actions.append("Release is blocked. Fix failing audits or metrics and re-aggregate the scorecard.")
        else:
            actions.append("Release evidence is pending. Complete audits and re-run scorecard aggregation.")

    recommended_skill = report.get("recommended_skill")
    if recommended_skill:
        actions.append(
            "Recommended next skill: "
            f"{recommended_skill['skill']} - {recommended_skill['reason']}"
        )
        actions.extend(recommended_skill.get("blocking_items", [])[:3])
    else:
        owners = ", ".join(report["owner_skills"])
        actions.append(f"Recommended skills: {owners}")

    return actions


def run_scorecard_aggregation(run_dir: Path) -> None:
    script_path = Path(__file__).with_name("aggregate_scorecard.py")
    subprocess.run(
        [sys.executable, str(script_path), str(run_dir)],
        check=True,
        cwd=Path.cwd(),
    )


def refresh_manifest(run_dir: Path, *, auto_advance: bool, aggregate_scorecard: bool) -> dict:
    manifest_path = run_dir / "run-manifest.json"
    manifest = ensure_manifest_schema(load_json(manifest_path), run_dir)

    if aggregate_scorecard:
        run_scorecard_aggregation(run_dir)

    manifest["stage_status"] = inspect_run(run_dir)

    if auto_advance:
        while manifest["stage"] != "release" and manifest["stage_status"][manifest["stage"]]["ready"]:
            previous_stage = manifest["stage"]
            manifest["stage"] = NEXT_STAGE[previous_stage]
            append_history(
                manifest,
                manifest["stage"],
                "entered",
                f"Auto-advanced because `{previous_stage}` was ready.",
            )

    manifest["updated_at"] = now_iso()
    manifest["status"] = derive_status(manifest)
    manifest["next_actions"] = derive_next_actions(manifest)
    write_json(manifest_path, manifest)
    return manifest


def print_skill_checks(title: str, skill_checks: list[dict]) -> None:
    if not skill_checks:
        return
    print(title)
    for check in skill_checks:
        print(f"- [{check['status']}] {check['skill']}: {check['reason']}")
        for item in check.get("blocking_items", []):
            print(f"  - {item}")


def print_manifest_summary(run_dir: Path, manifest: dict) -> None:
    stage = manifest["stage"]
    current = manifest["stage_status"][stage]
    print(f"Run: {manifest['run_id']}")
    print(f"Directory: {run_dir}")
    print(f"Stage: {stage}")
    print(f"Status: {manifest['status']}")
    print(f"Summary: {current['summary']}")

    recommended_skill = current.get("recommended_skill")
    if recommended_skill:
        print(
            "Recommended next skill: "
            f"{recommended_skill['skill']} ({recommended_skill['status']})"
        )
        print(f"Why: {recommended_skill['reason']}")
    else:
        print("Recommended next skill: none")

    if current["missing"]:
        print("Missing:")
        for item in current["missing"]:
            print(f"- {item}")
    else:
        print("Missing: none")

    print_skill_checks("Skill checklist:", current.get("skill_checks", []))
    if stage == "release":
        print_skill_checks("Repair queue:", current.get("repair_queue", []))

    print("Next actions:")
    for action in manifest["next_actions"]:
        print(f"- {action}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage AI Landing Factory run stages and manifest state."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command_name in ("status", "sync"):
        command = subparsers.add_parser(command_name)
        command.add_argument("run_dir", help="Path to a single landing run directory.")
        command.add_argument(
            "--aggregate-scorecard",
            action="store_true",
            help="Recompute release/qa-scorecard.json before refreshing the manifest.",
        )
        if command_name == "status":
            command.add_argument("--json", action="store_true", help="Print the full manifest JSON.")
        if command_name == "sync":
            command.add_argument(
                "--auto-advance",
                action="store_true",
                help="Automatically move to the next stage when the current one is ready.",
            )

    advance = subparsers.add_parser("advance")
    advance.add_argument("run_dir", help="Path to a single landing run directory.")
    advance.add_argument("--to", choices=STAGES, required=True, help="Target stage.")
    advance.add_argument(
        "--force",
        action="store_true",
        help="Allow manual stage overrides even if prerequisites are not ready.",
    )
    advance.add_argument(
        "--reason",
        default="manual override",
        help="Short note recorded in manifest history.",
    )
    advance.add_argument(
        "--aggregate-scorecard",
        action="store_true",
        help="Recompute release/qa-scorecard.json before validating the transition.",
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()
    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        raise SystemExit(f"Run directory not found: {run_dir}")

    if args.command == "status":
        manifest = refresh_manifest(
            run_dir,
            auto_advance=False,
            aggregate_scorecard=args.aggregate_scorecard,
        )
        if args.json:
            print(json.dumps(manifest, indent=2, ensure_ascii=True))
        else:
            print_manifest_summary(run_dir, manifest)
        return 0

    if args.command == "sync":
        manifest = refresh_manifest(
            run_dir,
            auto_advance=args.auto_advance,
            aggregate_scorecard=args.aggregate_scorecard,
        )
        print_manifest_summary(run_dir, manifest)
        return 0

    manifest_path = run_dir / "run-manifest.json"
    manifest = refresh_manifest(
        run_dir,
        auto_advance=False,
        aggregate_scorecard=args.aggregate_scorecard,
    )
    current_stage = manifest["stage"]
    target_stage = args.to

    if not args.force:
        if stage_index(target_stage) > stage_index(current_stage):
            for stage in STAGES[: stage_index(target_stage)]:
                if not manifest["stage_status"][stage]["ready"] and stage != target_stage:
                    raise SystemExit(
                        f"Cannot advance to `{target_stage}` because `{stage}` is not ready. Use --force to override."
                    )
        elif stage_index(target_stage) < stage_index(current_stage):
            raise SystemExit(
                f"Refusing to move backwards from `{current_stage}` to `{target_stage}` without --force."
            )

    if target_stage != current_stage:
        manifest["stage"] = target_stage
        append_history(manifest, target_stage, "entered", args.reason)
        manifest["updated_at"] = now_iso()
        manifest["status"] = derive_status(manifest)
        manifest["next_actions"] = derive_next_actions(manifest)
        write_json(manifest_path, manifest)

    print_manifest_summary(run_dir, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
