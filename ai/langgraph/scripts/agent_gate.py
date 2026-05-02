#!/usr/bin/env python3
"""Local pre-execute gate for risky repository changes.

The gate intentionally avoids calling a remote model. Older versions of this
tool depended on model-specific prompting; this replacement keeps the contract
deterministic and treats the requested model as metadata for the downstream
agent prompt.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


MODEL_ALIASES = {
    "chatgpt 5.5": "gpt-5.5",
    "chatgpt-5.5": "gpt-5.5",
    "gpt 5.5": "gpt-5.5",
    "gpt5.5": "gpt-5.5",
    "gpt-5.5": "gpt-5.5",
}


EXPLICIT_PATH_RE = re.compile(
    r"(?P<path>(?:[A-Za-z0-9_.-]+[\\/])+[A-Za-z0-9_.-]+\."
    r"(?:py|js|jsx|ts|tsx|json|md|yml|yaml|toml|sh|ps1|bat|txt))"
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
            "ai/langgraph/README.md",
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
            "frontend/src/components/doctor/DoctorQueuePanel.jsx",
            "frontend/src/components/doctor/__tests__/DoctorQueuePanel.test.jsx",
            "frontend/src/api/runtime.js",
        ),
        "frontend runtime-origin and doctor queue contract ownership",
    ),
    Rule(
        r"\b(npm audit|audit|vulnerabilit|dependency|dependencies|axios|jspdf|dompurify|vite|vitest|react-router)\b",
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
            "frontend/src/routing/routeRegistry.js",
            "frontend/src/routing/routeSelectors.js",
        ),
        "routing SSOT ownership",
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
        r"\b(telegram|bot webhook|telegram webhook)\b",
        (
            "backend/app/api/v1/endpoints/admin_telegram.py",
            "backend/app/api/v1/endpoints/telegram_webhook.py",
            "frontend/src/components/TelegramManager.jsx",
        ),
        "Telegram mixed frontend/backend ownership",
    ),
)


REFERENCE_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    ".ai-factory/DESCRIPTION.md",
    ".ai-factory/ARCHITECTURE.md",
    ".ai-factory/RULES.md",
)


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[3]


def normalize_model(value: str | None) -> str:
    raw = (value or os.getenv("AGENT_GATE_MODEL") or "gpt-5.5").strip()
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


def explicit_paths(task: str, repo_root: Path, tracked: set[str]) -> list[str]:
    candidates = [match.group("path") for match in EXPLICIT_PATH_RE.finditer(task)]
    return unique_existing(repo_root, tracked, candidates)


def rule_matches(task: str, repo_root: Path, tracked: set[str]) -> tuple[list[str], list[str]]:
    found: list[str] = []
    reasons: list[str] = []
    for rule in RULES:
        if re.search(rule.pattern, task, flags=re.IGNORECASE):
            found.extend(rule.files)
            reasons.append(rule.reason)
    return unique_existing(repo_root, tracked, found), reasons


def validation_targets(files: list[str]) -> list[str]:
    targets: list[str] = []
    py_files = [path for path in files if path.endswith(".py")]
    if py_files:
        joined = " ".join(py_files)
        targets.append(f"python -m py_compile {joined}")

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


def render_prompt(
    *,
    task: str,
    model: str,
    first_touch: list[str],
    references: list[str],
    validations: list[str],
    stops: list[str],
    reasons: list[str],
    known_root_cause: str | None,
    gate_misroute: bool,
    override_used: bool,
) -> str:
    reason_text = "; ".join(dict.fromkeys(reasons)) if reasons else "explicit task paths only"
    known = known_root_cause or "none"
    return f"""Result: {'narrow override' if override_used else 'gate ok'}
Model target: {model}
Mode: execute
Handoff required: yes
Reason: {reason_text}
Known root cause: {known}
gate_misroute: {'yes' if gate_misroute else 'no'}
override_used: {'yes' if override_used else 'no'}

Canonical anchors:
{render_list(references)}

First-touch files:
{render_list(first_touch)}

Validation targets:
{render_list(validations)}

Stop conditions:
{render_list(stops)}

Ready-to-send execution prompt
You are fixing this repository task:
{task}

Use model target `{model}` if you need to name the model in prompts or follow-up
agent instructions. Do not rely on older GPT-specific formatting assumptions.

Work only inside the First-touch files listed above for the first patch slice.
Use the Canonical anchors as reference-only context unless the user explicitly
asks to update instructions. Treat Stop conditions as hard stops and report
instead of widening scope. After changing files, run the Validation targets and
report exact pass/fail results.
"""


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
        help="Model metadata for the downstream prompt. Defaults to AGENT_GATE_MODEL or gpt-5.5.",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root. Defaults to the parent of ai/langgraph.",
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

    initial_first_touch = unique_existing(repo_root, tracked, files)
    known = normalize_rel_path(args.known_root_cause) if args.known_root_cause else None
    gate_misroute = False
    override_used = False

    if known:
        if not path_exists(repo_root, known, tracked):
            print(f"Result: stop\nReason: known root cause does not exist: {known}")
            return 2
        if known not in initial_first_touch:
            gate_misroute = bool(initial_first_touch)
            override_used = True
            reasons.append("known-root-cause override")
            initial_first_touch.insert(0, known)

    first_touch = unique_existing(repo_root, tracked, initial_first_touch)
    if not first_touch:
        print(
            "Result: stop\n"
            "Reason: no first-touch files could be resolved. Add an explicit path "
            "or rerun with --known-root-cause."
        )
        return 2

    references = unique_existing(repo_root, tracked, list(REFERENCE_FILES))
    validations = validation_targets(first_touch)
    stops = stop_conditions(first_touch)

    print(
        render_prompt(
            task=task,
            model=model,
            first_touch=first_touch,
            references=references,
            validations=validations,
            stops=stops,
            reasons=reasons,
            known_root_cause=known,
            gate_misroute=gate_misroute,
            override_used=override_used,
        ).rstrip()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
