#!/usr/bin/env python3
"""Deterministic, low-token pre-execute gate for risky repository changes."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast


MODEL_ALIASES = {
    "chatgpt 5.5": "gpt-5.5",
    "chatgpt-5.5": "gpt-5.5",
    "chatgpt 5.5 pro": "gpt-5.5",
    "chatgpt-5.5-pro": "gpt-5.5",
    "chatgpt-5.5 pro": "gpt-5.5",
    "gpt 5.5": "gpt-5.5",
    "gpt 5.5 pro": "gpt-5.5",
    "gpt5.5": "gpt-5.5",
    "gpt5.5 pro": "gpt-5.5",
    "gpt-5.5": "gpt-5.5",
    "gpt-5.5-pro": "gpt-5.5",
    "gpt-5.5 pro": "gpt-5.5",
}


EXPLICIT_PATH_RE = re.compile(
    r"(?P<path>(?:[A-Za-z0-9_.-]+[\\/])+[A-Za-z0-9_.-]+\."
    r"(?:jsx|tsx|js|ts|py|json|yaml|yml|toml|ps1|bat|sh|md|txt))"
)

MIGRATION_INTENT_RE = re.compile(
    r"(?:\b(?:add|create|generate|write|ship|apply|fix|repair|update|alter|remove)\b"
    r".{0,60}\b(?:alembic|migration|revision|database schema|table)\b|"
    r"\b(?:model exists|table missing|missing table|storage migration|"
    r"schema change|create table)\b)",
    re.IGNORECASE,
)

SELF_TOOLING_RE = re.compile(
    r"\b(agent[_ -]?gate|repo[_ -]?gate|dev[_ -]?brain)\b", re.IGNORECASE
)

STRICT_TASK_RE = re.compile(
    r"\b(?:alembic|migration|sqlalchemy|database schema|postgres(?:ql)?|rbac|"
    r"billing|payment|emr|medical record|queue fairness|queue_time|telegram|"
    r"token storage|ci/cd|deploy(?:ment)?|production)\b",
    re.IGNORECASE,
)

MIGRATION_STOP_CONDITIONS = (
    "multi-head ambiguity in Alembic revision chain",
    "existing table detected for the requested storage table",
    "destructive migration operation is needed",
    "model/table mismatch between SQLAlchemy model and migration DDL",
)


@dataclass(frozen=True)
class Rule:
    pattern: str
    files: tuple[str, ...]
    reason: str


RULES: tuple[Rule, ...] = (
    Rule(
        r"\b(agent[_ -]?gate|repo[_ -]?gate|dev[_ -]?brain|handoff|lightrag)\b",
        (
            "ai/langgraph/scripts/agent_gate.py",
            "ai/langgraph/scripts/run_agent_gate.ps1",
        ),
        "dev-brain gate/tooling ownership",
    ),
    Rule(
        r"\b(docker|entrypoint|create_all|alembic|sqlite|postgres|postgresql)\b",
        (
            "ops/backend.entrypoint.sh",
            "backend/docker/entrypoint.staging.sh",
            "ops/backend.Dockerfile",
            "backend/Dockerfile.staging",
            "ops/docker-compose.yml",
            "ops/compose.staging.yml",
        ),
        "runtime packaging and database-source-of-truth ownership",
    ),
    Rule(
        r"\b(docker[- ]?compose|compose\.ya?ml|compose)\b",
        (
            "ops/docker-compose.yml",
            "ops/compose.staging.yml",
        ),
        "compose runtime ownership",
    ),
    Rule(
        r"\b(profile_tokens|runtime tokens?|jwt|secret|credential|\.env)\b",
        (
            ".ai-factory/profile_tokens.json",
            ".gitignore",
        ),
        "secrets and tracked runtime artifact ownership",
    ),
    Rule(
        r"\b(doctorqueuepanel|doctor queue panel|canonical origin|localhost|127\.0\.0\.1)\b",
        (
            "frontend/src/components/doctor/DoctorQueuePanel.tsx",
            "frontend/src/components/doctor/__tests__/DoctorQueuePanel.test.tsx",
            "frontend/src/api/runtime.ts",
        ),
        "frontend runtime-origin and doctor queue contract ownership",
    ),
    Rule(
        r"\b(npm audit|dependency audit|security audit|vulnerabilit|dependency|dependencies|axios|jspdf|dompurify|vite|vitest|react-router)\b",
        (
            "frontend/package.json",
            "frontend/package-lock.json",
            "package.json",
            "package-lock.json",
        ),
        "dependency security ownership",
    ),
    Rule(
        r"\b(route|routing|alias|route registry|router)\b",
        (
            "frontend/src/routing/routeRegistry.ts",
            "frontend/src/routing/routeSelectors.ts",
        ),
        "routing SSOT ownership",
    ),
    Rule(
        r"\b(registrar\b.*\b(payment|billing|status|persistence)|"
        r"(payment|billing|status|persistence)\b.*\bregistrar)\b",
        (
            "backend/app/services/billing_service.py",
            "backend/app/services/billing_api_service.py",
            "backend/app/models/payment.py",
            "backend/app/api/v1/endpoints/billing.py",
        ),
        "registrar backend payment/status persistence ownership",
    ),
    Rule(
        r"\b(queue_time|queue fairness|specialist|dailyqueue|online queue|queue mapping)\b",
        (
            "backend/app/services/queue_service.py",
            "backend/app/models/online_queue.py",
            "backend/tests/unit/test_queue_time_window.py",
        ),
        "queue fairness and queue-time ownership",
    ),
    Rule(
        r"\b(notification|notifications|preferences|mute|snooze|dnd|anti-noise|anti noise)\b",
        (
            "backend/app/services/notifications.py",
            "backend/app/services/notification_platform_service.py",
            "backend/app/schemas/notification.py",
            "backend/app/models/notification.py",
        ),
        "notification catalog/settings runtime policy ownership",
    ),
    Rule(
        r"\b(telegram|bot webhook|telegram webhook)\b",
        (
            "backend/app/api/v1/endpoints/admin_telegram/_management.py",
            "backend/app/api/v1/endpoints/telegram_webhook/_routes.py",
            "frontend/src/components/TelegramManager.tsx",
        ),
        "Telegram mixed frontend/backend ownership",
    ),
)


REFERENCE_FILES = (
    "AGENTS.md",
    "docs/devbrain/PROJECT_MEMORY.md",
    "docs/devbrain/DEVBRAIN_STATUS.md",
)


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[3]


def normalize_model(value: str | None) -> str:
    raw = (value or os.getenv("AGENT_GATE_MODEL") or "current-agent").strip()
    return MODEL_ALIASES.get(raw.lower(), raw)


def git_files(repo_root: Path) -> set[str]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files"],
            cwd=repo_root,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        return {
            str(path.relative_to(repo_root)).replace("\\", "/")
            for path in repo_root.rglob("*")
            if path.is_file() and ".git" not in path.parts
        }
    return {line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()}


def normalize_rel_path(path: str) -> str:
    rel = path.strip().strip('"').strip("'").replace("\\", "/")
    if rel.startswith("./"):
        return rel[2:]
    return rel


def path_exists(repo_root: Path, rel_path: str, tracked: set[str]) -> bool:
    rel = normalize_rel_path(rel_path)
    return rel in tracked or (repo_root / rel).exists()


def unique_existing(repo_root: Path, tracked: set[str], paths: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        rel = normalize_rel_path(path)
        if rel in seen or not path_exists(repo_root, rel, tracked):
            continue
        seen.add(rel)
        result.append(rel)
    return result


def unique_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for path in paths:
        rel = normalize_rel_path(path)
        if rel in seen:
            continue
        seen.add(rel)
        result.append(rel)
    return result


def explicit_paths(task: str, repo_root: Path, tracked: set[str]) -> list[str]:
    candidates = [match.group("path") for match in EXPLICIT_PATH_RE.finditer(task)]
    seen: set[str] = set()
    result: list[str] = []
    for path in candidates:
        rel = normalize_rel_path(path)
        if rel in seen:
            continue
        # Explicit first-touch paths may name a new file for extraction work.
        # Allow that only when the parent directory already exists in checkout.
        if path_exists(repo_root, rel, tracked) or (repo_root / rel).parent.exists():
            seen.add(rel)
            result.append(rel)
    return result


def rule_matches(task: str, repo_root: Path, tracked: set[str]) -> tuple[list[str], list[str]]:
    found: list[str] = []
    reasons: list[str] = []
    for rule in RULES:
        if re.search(rule.pattern, task, flags=re.IGNORECASE):
            found.extend(rule.files)
            reasons.append(rule.reason)
    return unique_existing(repo_root, tracked, found), reasons


def is_self_tooling_task(task: str, known_root_cause: str | None) -> bool:
    return bool(
        SELF_TOOLING_RE.search(task)
        and known_root_cause
        and known_root_cause.startswith("ai/langgraph/")
    )


def is_migration_task(task: str, known_root_cause: str | None = None) -> bool:
    if is_self_tooling_task(task, known_root_cause):
        return False
    return bool(MIGRATION_INTENT_RE.search(task))


def requires_handoff(
    task: str,
    mode: str,
    first_touch: list[str],
    known_root_cause: str | None,
) -> bool:
    if mode == "migration":
        return True
    if is_self_tooling_task(task, known_root_cause):
        return False
    if STRICT_TASK_RE.search(task):
        return True
    return known_root_cause is None or len(first_touch) > 1


def latest_numeric_migration(tracked: set[str]) -> str | None:
    candidates: list[tuple[int, str]] = []
    for rel in tracked:
        if not rel.startswith("backend/alembic/versions/") or not rel.endswith(".py"):
            continue
        match = re.match(r"^backend/alembic/versions/(\d{4})_", rel)
        if not match:
            continue
        candidates.append((int(match.group(1)), rel))
    if not candidates:
        return None
    return sorted(candidates)[-1][1]


def next_migration_pattern(tracked: set[str]) -> str:
    latest = latest_numeric_migration(tracked)
    next_number = 1
    if latest:
        match = re.match(r"backend/alembic/versions/(\d{4})_", latest)
        if match:
            next_number = int(match.group(1)) + 1
    return f"backend/alembic/versions/{next_number:04d}_*.py"


def model_references_for_task(task: str, repo_root: Path, tracked: set[str]) -> list[str]:
    task_lower = task.lower()
    references: list[str] = []
    model_files = sorted(
        path
        for path in tracked
        if path.startswith("backend/app/models/") and path.endswith(".py")
    )
    for rel_path in model_files:
        try:
            text = (repo_root / rel_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        class_names = re.findall(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.MULTILINE)
        table_names = re.findall(r"__tablename__\s*=\s*[\"']([^\"']+)[\"']", text)
        class_hits = [
            name
            for name in class_names
            if len(name) >= 5
            and re.search(rf"\b{re.escape(name.lower())}\b", task_lower)
        ]
        table_hits = [
            name for name in table_names if len(name) >= 6 and name.lower() in task_lower
        ]
        if class_hits or table_hits:
            references.append(rel_path)
    return unique_existing(repo_root, tracked, references)


def migration_read_only_references(
    task: str,
    repo_root: Path,
    tracked: set[str],
    known_root_cause: str | None,
) -> list[str]:
    references: list[str] = [
        "backend/alembic/env.py",
    ]
    latest = latest_numeric_migration(tracked)
    if latest:
        references.append(latest)
    references.extend(model_references_for_task(task, repo_root, tracked))
    if known_root_cause:
        references.insert(0, known_root_cause)
    return unique_existing(repo_root, tracked, references)


def powershell_quote(value: Path | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def repo_location_command(repo_root: Path) -> str:
    return f"Set-Location -LiteralPath {powershell_quote(repo_root)}"


def python_launcher_command(repo_root: Path) -> str:
    launcher = repo_root / "scripts" / "run_python.ps1"
    return f"& {powershell_quote(launcher)}"


def migration_validation_targets(repo_root: Path, new_revision_pattern: str) -> list[str]:
    placeholder = new_revision_pattern.replace("*", "<slug>")
    python_launcher = python_launcher_command(repo_root)
    return [
        f"{repo_location_command(repo_root)}; {python_launcher} -m py_compile {placeholder}",
        f"Set-Location -LiteralPath {powershell_quote(repo_root / 'backend')}; alembic heads",
        f"Set-Location -LiteralPath {powershell_quote(repo_root / 'backend')}; alembic history --verbose",
        f"Set-Location -LiteralPath {powershell_quote(repo_root / 'backend')}; alembic upgrade head  # against a disposable/test Postgres database",
    ]


def validation_targets(repo_root: Path, files: list[str]) -> list[str]:
    targets: list[str] = []
    py_files = [path for path in files if path.endswith(".py")]
    if py_files:
        joined = " ".join(py_files)
        targets.append(
            f"{repo_location_command(repo_root)}; "
            f"{python_launcher_command(repo_root)} -m py_compile {joined}"
        )

    frontend_tests = [
        path.removeprefix("frontend/")
        for path in files
        if path.startswith("frontend/") and re.search(r"\.test\.[jt]sx?$", path)
    ]
    for test_path in frontend_tests:
        targets.append(f"cd frontend; npm.cmd run test:run -- {test_path}")

    if any(path.startswith("frontend/") for path in files):
        targets.append("cd frontend; npm.cmd run build")

    if any(path in {"frontend/package.json", "frontend/package-lock.json"} for path in files):
        targets.append("cd frontend; npm.cmd audit --audit-level=moderate")

    if any(path.endswith((".yml", ".yaml")) for path in files):
        targets.append("docker compose config for touched compose file, if Docker is available")

    if not targets:
        targets.append("manual review of generated first-touch file list")
    return targets


def stop_conditions(files: list[str]) -> list[str]:
    stops = [
        "required edit falls outside First-touch files",
        "canonical owner or legacy/adapter boundary is unclear",
        "validation target cannot be made concrete",
    ]
    if any(path.startswith("backend/") for path in files) and any(
        path.startswith("frontend/") for path in files
    ):
        stops.append("frontend/backend contract ownership becomes ambiguous")
    if any("profile_tokens" in path or path.endswith(".env") for path in files):
        stops.append("fix requires git history rewrite or secret rotation policy decision")
    if any(path.startswith("ops/") or "entrypoint" in path for path in files):
        stops.append("runtime behavior decision is needed beyond Postgres + Alembic SSOT")
    return stops


def render_list(values: list[str]) -> str:
    if not values:
        return "- none"
    return "\n".join(f"- {value}" for value in values)


def gate_payload(
    *,
    task: str,
    model: str,
    mode: str,
    first_touch: list[str],
    references: list[str],
    read_only_references: list[str],
    validations: list[str],
    stops: list[str],
    reasons: list[str],
    known_root_cause: str | None,
    gate_misroute: bool,
    override_used: bool,
    handoff_required: bool,
    include_execution_prompt: bool,
) -> dict[str, object]:
    reason_text = "; ".join(dict.fromkeys(reasons)) if reasons else "explicit task paths only"
    payload: dict[str, object] = {
        "result": "narrow_override" if override_used else "gate_ok",
        "mode": mode,
        "handoff_required": handoff_required,
        "reason": reason_text,
        "known_root_cause": known_root_cause,
        "gate_misroute": gate_misroute,
        "override_used": override_used,
        "canonical_anchors": references,
        "first_touch_files": first_touch,
        "read_only_reference_files": read_only_references,
        "validation_targets": validations,
        "stop_conditions": stops,
    }
    if include_execution_prompt:
        payload["execution_prompt"] = (
            f"Task: {task}\nModel metadata: {model}\n"
            f"Edit only: {', '.join(first_touch)}\n"
            f"Validate: {'; '.join(validations)}\n"
            f"Stop if: {'; '.join(stops)}"
        )
    return payload


def render_text(payload: dict[str, object]) -> str:
    lines = [
        f"Result: {payload['result']}",
        f"Mode: {payload['mode']}",
        f"Handoff required: {'yes' if payload['handoff_required'] else 'no'}",
        f"Reason: {payload['reason']}",
        f"Known root cause: {payload['known_root_cause'] or 'none'}",
        f"gate_misroute: {'yes' if payload['gate_misroute'] else 'no'}",
        f"override_used: {'yes' if payload['override_used'] else 'no'}",
        "Canonical anchors:",
        render_list(cast(list[str], payload["canonical_anchors"])),
        "First-touch files:",
        render_list(cast(list[str], payload["first_touch_files"])),
        "Read-only reference files:",
        render_list(cast(list[str], payload["read_only_reference_files"])),
        "Validation targets:",
        render_list(cast(list[str], payload["validation_targets"])),
        "Stop conditions:",
        render_list(cast(list[str], payload["stop_conditions"])),
    ]
    if "execution_prompt" in payload:
        lines.extend(["Ready-to-send execution prompt", str(payload["execution_prompt"])])
    return "\n".join(lines)


def emit_payload(payload: dict[str, object], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return
    print(render_text(payload))


def emit_stop(reason: str, output_format: str) -> None:
    payload: dict[str, object] = {"result": "stop", "reason": reason}
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        return
    print(f"Result: stop\nReason: {reason}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local pre-execute repo gate")
    parser.add_argument("task", help="User task to gate")
    parser.add_argument(
        "--known-root-cause",
        dest="known_root_cause",
        help="Confirmed relative source file that must be included in the patch slice",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=(
            "Optional model metadata for a downstream handoff. Defaults to "
            "AGENT_GATE_MODEL or current-agent."
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root. Defaults to the parent of ai/langgraph.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format. Compact JSON is the default.",
    )
    parser.add_argument(
        "--handoff",
        action="store_true",
        help="Include a compact execution prompt even when handoff is optional.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve() if args.repo_root else repo_root_from_script()
    model = normalize_model(args.model)
    tracked = git_files(repo_root)
    task = args.task.strip()

    print(
        f"[agent_gate] repo={repo_root} model={model} task_chars={len(task)}",
        file=sys.stderr,
    )

    files: list[str] = []
    reasons: list[str] = []
    explicit = explicit_paths(task, repo_root, tracked)
    if explicit:
        files.extend(explicit)
        reasons.append("explicit file paths in task")

    matched_files, matched_reasons = rule_matches(task, repo_root, tracked)
    files.extend(matched_files)
    reasons.extend(matched_reasons)

    initial_first_touch = unique_paths(files)
    known = normalize_rel_path(args.known_root_cause) if args.known_root_cause else None
    gate_misroute = False
    override_used = False

    if known:
        if not path_exists(repo_root, known, tracked):
            emit_stop(f"known root cause does not exist: {known}", args.format)
            return 2

    # A confirmed gate/dev-brain owner takes precedence over incidental mentions
    # of the strict domains that the tooling itself is expected to protect.
    if is_self_tooling_task(task, known):
        initial_first_touch = [known]
        reasons = ["dev-brain gate/tooling ownership"]

    if is_migration_task(task, known):
        new_revision = next_migration_pattern(tracked)
        first_touch = unique_paths([new_revision])
        read_only_references = migration_read_only_references(
            task, repo_root, tracked, known
        )
        references = unique_existing(
            repo_root,
            tracked,
            list(REFERENCE_FILES) + read_only_references,
        )
        validations = migration_validation_targets(repo_root, new_revision)
        stops = unique_paths(
            stop_conditions(first_touch) + list(MIGRATION_STOP_CONDITIONS)
        )
        emit_payload(
            gate_payload(
                task=task,
                model=model,
                mode="migration",
                first_touch=first_touch,
                references=references,
                read_only_references=read_only_references,
                validations=validations,
                stops=stops,
                reasons=[
                    "DB migration ownership",
                    "SQLAlchemy model/table storage gap starts with a new Alembic revision",
                ],
                known_root_cause=known,
                gate_misroute=False,
                override_used=False,
                handoff_required=True,
                include_execution_prompt=True,
            ),
            args.format,
        )
        return 0

    if known:
        if known not in initial_first_touch:
            gate_misroute = bool(initial_first_touch)
            override_used = True
            reasons.append("known-root-cause override")
            initial_first_touch.insert(0, known)

    strict_task = bool(STRICT_TASK_RE.search(task)) and not is_self_tooling_task(task, known)
    if known and not strict_task:
        first_touch = [known]
    else:
        first_touch = unique_paths(initial_first_touch)
    read_only_references: list[str] = []
    if not first_touch:
        emit_stop(
            "no first-touch files could be resolved; add an explicit path or rerun "
            "with --known-root-cause",
            args.format,
        )
        return 2

    references = unique_existing(repo_root, tracked, list(REFERENCE_FILES))
    validations = validation_targets(repo_root, first_touch)
    stops = stop_conditions(first_touch)
    handoff_required = requires_handoff(task, "execute", first_touch, known)

    emit_payload(
        gate_payload(
            task=task,
            model=model,
            mode="execute",
            first_touch=first_touch,
            references=references,
            read_only_references=read_only_references,
            validations=validations,
            stops=stops,
            reasons=reasons,
            known_root_cause=known,
            gate_misroute=gate_misroute,
            override_used=override_used,
            handoff_required=handoff_required,
            include_execution_prompt=handoff_required or args.handoff,
        ),
        args.format,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
