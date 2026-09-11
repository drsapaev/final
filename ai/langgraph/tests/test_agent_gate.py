from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
GATE_PATH = REPO_ROOT / "ai" / "langgraph" / "scripts" / "agent_gate.py"


def run_gate(task: str, *args: str) -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            str(GATE_PATH),
            task,
            "--repo-root",
            str(REPO_ROOT),
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def load_gate_module():
    spec = importlib.util.spec_from_file_location("agent_gate", GATE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_self_gate_mentions_of_strict_domains_do_not_trigger_migration() -> None:
    payload = run_gate(
        "Update agent gate while preserving strict DB/Alembic and deployment behavior",
        "--known-root-cause",
        "ai/langgraph/scripts/agent_gate.py",
    )

    assert payload["mode"] == "execute"
    assert payload["handoff_required"] is False
    assert payload["first_touch_files"] == ["ai/langgraph/scripts/agent_gate.py"]
    assert "execution_prompt" not in payload


def test_real_missing_table_task_remains_strict_migration() -> None:
    payload = run_gate(
        "TelegramStaffLinkToken model exists but table missing; add an Alembic migration",
        "--known-root-cause",
        "backend/app/models/telegram_config.py",
    )

    assert payload["mode"] == "migration"
    assert payload["handoff_required"] is True
    assert payload["first_touch_files"][0].startswith("backend/alembic/versions/")
    assert "execution_prompt" in payload


def test_narrow_known_root_cause_uses_compact_same_agent_contract() -> None:
    payload = run_gate(
        "Refine deterministic gate output",
        "--known-root-cause",
        "ai/langgraph/scripts/agent_gate.py",
    )

    assert payload["canonical_anchors"] == [
        "AGENTS.md",
        "docs/devbrain/PROJECT_MEMORY.md",
        "docs/devbrain/DEVBRAIN_STATUS.md",
    ]
    assert payload["handoff_required"] is False
    assert "execution_prompt" not in payload


def test_strict_queue_task_still_requires_handoff() -> None:
    payload = run_gate(
        "Fix queue fairness in queue_time ordering",
        "--known-root-cause",
        "backend/app/services/queue_service.py",
    )

    assert payload["mode"] == "execute"
    assert payload["handoff_required"] is True
    assert "execution_prompt" in payload


def test_text_renderer_omits_prompt_when_handoff_is_not_required() -> None:
    gate = load_gate_module()
    payload = gate.gate_payload(
        task="narrow task",
        model="gpt-5.5",
        mode="execute",
        first_touch=["ai/langgraph/scripts/agent_gate.py"],
        references=["AGENTS.md"],
        read_only_references=["backend/app/models/online_queue.py"],
        validations=["py_compile"],
        stops=["scope expands"],
        reasons=["known root"],
        known_root_cause="ai/langgraph/scripts/agent_gate.py",
        gate_misroute=False,
        override_used=False,
        handoff_required=False,
        include_execution_prompt=False,
    )

    rendered = gate.render_text(payload)
    assert "Handoff required: no" in rendered
    assert "Read-only reference files:" in rendered
    assert "backend/app/models/online_queue.py" in rendered
    assert "Ready-to-send execution prompt" not in rendered


def test_stop_result_is_machine_readable() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(GATE_PATH),
            "narrow unknown task",
            "--repo-root",
            str(REPO_ROOT),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 2
    assert json.loads(completed.stdout) == {
        "result": "stop",
        "reason": (
            "no first-touch files could be resolved; add an explicit path or rerun "
            "with --known-root-cause"
        ),
    }
