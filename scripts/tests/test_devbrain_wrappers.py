"""Behavioral checks for the legacy DevBrain PowerShell wrappers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")
MEMORY_PROBE_FACT = (
    "Memory probe protocol was created after PR #1332 optimized the PR Lifecycle Recommendation workflow."
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_repo(tmp_path: Path, *, with_artifacts: bool) -> tuple[Path, list[Path]]:
    repo = tmp_path / "fixture"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)

    for name in (
        "devbrain_inventory.ps1",
        "devbrain_regression_matrix.ps1",
        "devbrain_markdown_index_coverage.ps1",
        "devbrain_refresh_memory.ps1",
    ):
        shutil.copy2(REPO_ROOT / "scripts" / name, scripts / name)

    _write(
        scripts / "run_devbrain_memory.ps1",
        """
param([string] $Action)
if ($Action -eq 'status') {
    Write-Output '{"status":"OK","event_count":7,"corrupt_count":0,"errors":[]}'
}
exit 0
""",
    )
    _write(scripts / "devbrain_acceptance.ps1", "exit 0\n")
    _write(
        repo / ".ai-factory" / "logs" / "memory-probes.md",
        MEMORY_PROBE_FACT + "\n",
    )
    status = _write(
        repo / "docs" / "devbrain" / "DEVBRAIN_STATUS.md",
        "Current status: active local fallback\nstatus sentinel\n",
    )

    marker_script = """
param([string[]] $Arguments)
Add-Content -LiteralPath $env:DEVBRAIN_TEST_LEGACY_CALLS -Value $MyInvocation.MyCommand.Name
exit 0
"""
    query_script = """
param([string] $Query)
Add-Content -LiteralPath $env:DEVBRAIN_TEST_QUERY_CALLS -Value $MyInvocation.MyCommand.Name
Write-Output 'frontend/src/api/runtime.js frontend/src/api/ws.js local_dev_runtime_contour scripts/start_dev_clinic.ps1 docs/runbooks/LOCAL_DEV_ONBOARDING.md memory_probe_protocol .ai-factory/logs/memory-probes.md registrar_payment_status backend/app/services/billing_service.py backend/app/models/payment.py alembic_migration_ownership backend/alembic/versions backend/app/models notification_catalog_anti_noise backend/app/services/notifications.py backend/app/schemas/notification.py queue_identity_fairness backend/app/services/queue_service.py backend/app/models/online_queue.py'
exit 0
"""

    llama_query = _write(repo / "ai" / "llamaindex" / "scripts" / "run_query.ps1", query_script)
    light_query = _write(repo / "ai" / "lightrag" / "scripts" / "run_query.ps1", query_script)
    for path in (
        repo / "ai" / "llamaindex" / "scripts" / "run_smoke.ps1",
        repo / "ai" / "lightrag" / "scripts" / "run_acceptance.ps1",
        repo / "ai" / "lightrag" / "scripts" / "run_artifacts.ps1",
        repo / "ai" / "lightrag" / "scripts" / "run_artifact_check.ps1",
    ):
        _write(path, marker_script)
    for path in (
        repo / "ai" / "llamaindex" / "scripts" / "smoke.py",
        repo / "ai" / "lightrag" / "scripts" / "acceptance.py",
        repo / "ai" / "lightrag" / "scripts" / "export_artifacts.py",
        repo / "ai" / "lightrag" / "scripts" / "check_artifacts.py",
    ):
        _write(path, "# fixture entrypoint\n")

    metadata_files: list[Path] = []
    if with_artifacts:
        metadata_files.extend(
            [
                _write(
                    repo / "ai" / "llamaindex" / "storage" / "devbrain_index.json",
                    '{"commit":"fixture-commit","document_count":1}\n',
                ),
                _write(
                    repo / "ai" / "lightrag" / "indexes" / "lightrag_graph" / "graph.json",
                    '{"commit":"fixture-commit","edges":[{}]}\n',
                ),
                _write(
                    repo
                    / "ai"
                    / "lightrag"
                    / "indexes"
                    / "lightrag_graph"
                    / "artifacts"
                    / "metadata.json",
                    '{"commit":"fixture-commit"}\n',
                ),
            ]
        )
    else:
        metadata_files.extend(
            [
                repo / "ai" / "llamaindex" / "storage" / "devbrain_index.json",
                repo / "ai" / "lightrag" / "indexes" / "lightrag_graph" / "graph.json",
                repo
                / "ai"
                / "lightrag"
                / "indexes"
                / "lightrag_graph"
                / "artifacts"
                / "metadata.json",
            ]
        )

    _write(
        scripts / "run_python.ps1",
        """
param([string[]] $PythonArgs)
Add-Content -LiteralPath $env:DEVBRAIN_TEST_PYTHON_CALLS -Value (ConvertTo-Json -InputObject @($PythonArgs) -Compress)
exit 0
""",
    )

    return repo, [status, llama_query, light_query, *metadata_files]


def _run(repo: Path, script: str, *arguments: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    if not POWERSHELL:
        pytest.skip("PowerShell is not installed; wrapper behavior tests require pwsh or powershell")

    env = os.environ.copy()
    env["DEVBRAIN_TEST_LEGACY_CALLS"] = str(tmp_path / "legacy-calls.txt")
    env["DEVBRAIN_TEST_QUERY_CALLS"] = str(tmp_path / "query-calls.txt")
    env["DEVBRAIN_TEST_PYTHON_CALLS"] = str(tmp_path / "python-calls.jsonl")
    return subprocess.run(
        [POWERSHELL, "-NoLogo", "-NoProfile", "-File", str(repo / "scripts" / script), *arguments],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )


def _assert_ok(result: subprocess.CompletedProcess[str]) -> str:
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    return result.stdout


def test_default_wrappers_skip_legacy_retrieval_and_leave_sentinels_unchanged(tmp_path: Path) -> None:
    repo, tracked_sentinels = _make_repo(tmp_path, with_artifacts=True)
    before = {path: path.read_bytes() for path in tracked_sentinels}

    inventory = _assert_ok(_run(repo, "devbrain_inventory.ps1", tmp_path=tmp_path))
    regression = _assert_ok(_run(repo, "devbrain_regression_matrix.ps1", tmp_path=tmp_path))
    coverage = _assert_ok(_run(repo, "devbrain_markdown_index_coverage.ps1", tmp_path=tmp_path))
    refresh = _assert_ok(_run(repo, "devbrain_refresh_memory.ps1", tmp_path=tmp_path))

    assert "LlamaIndex legacy retrieval (dormant" in inventory
    assert "legacy retrieval checks intentionally skipped" in inventory
    assert "SKIP: intentional" in regression
    assert "SKIP: intentional" in coverage
    assert "LlamaIndex refresh: skip" in refresh
    assert "Portable regression: pass" in refresh
    assert not (tmp_path / "legacy-calls.txt").exists()
    assert not (tmp_path / "query-calls.txt").exists()
    assert {path: path.read_bytes() for path in tracked_sentinels} == before


def test_explicit_diagnostics_do_not_create_missing_legacy_indexes(tmp_path: Path) -> None:
    repo, _ = _make_repo(tmp_path, with_artifacts=False)

    inventory = _assert_ok(
        _run(repo, "devbrain_inventory.ps1", "-IncludeRetrieval", tmp_path=tmp_path)
    )
    regression = _assert_ok(
        _run(repo, "devbrain_regression_matrix.ps1", "-IncludeRetrieval", tmp_path=tmp_path)
    )

    assert "artifacts inspected (read-only)" in inventory
    assert "artifacts are missing; query was not run or created" in regression
    assert "graph is missing; queries were not run or created" in regression
    assert not (tmp_path / "query-calls.txt").exists()
    assert not (repo / "ai" / "llamaindex" / "storage").exists()
    assert not (repo / "ai" / "lightrag" / "indexes").exists()

    with_artifacts, _ = _make_repo(tmp_path / "with-artifacts", with_artifacts=True)
    inventory = _assert_ok(
        _run(with_artifacts, "devbrain_inventory.ps1", "-IncludeRetrieval", tmp_path=tmp_path)
    )
    assert "LlamaIndex artifact commit: fixture-commit" in inventory
    assert "LightRAG artifact commit: fixture-commit" in inventory


def test_refresh_skips_missing_lightrag_graph_without_status_write(tmp_path: Path) -> None:
    repo, _ = _make_repo(tmp_path, with_artifacts=False)
    status = repo / "docs" / "devbrain" / "DEVBRAIN_STATUS.md"
    status_before = status.read_bytes()

    output = _assert_ok(
        _run(repo, "devbrain_refresh_memory.ps1", "-RefreshRetrieval", tmp_path=tmp_path)
    )

    calls = [
        json.loads(line)
        for line in (tmp_path / "python-calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [Path(call[0]).name for call in calls] == ["smoke.py"]
    assert "LightRAG graph is absent; acceptance/export/check skipped without creating it" in output
    assert not (repo / "ai" / "lightrag" / "indexes").exists()
    assert status.read_bytes() == status_before


def test_explicit_refresh_uses_python_entrypoints_without_status_updates(tmp_path: Path) -> None:
    repo, _ = _make_repo(tmp_path, with_artifacts=True)
    status = repo / "docs" / "devbrain" / "DEVBRAIN_STATUS.md"
    status_before = status.read_bytes()

    output = _assert_ok(
        _run(repo, "devbrain_refresh_memory.ps1", "-RefreshRetrieval", tmp_path=tmp_path)
    )

    calls = [
        json.loads(line)
        for line in (tmp_path / "python-calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    scripts = [Path(call[0]).name for call in calls]
    assert scripts == ["smoke.py", "acceptance.py", "export_artifacts.py", "check_artifacts.py"]
    assert all("--update-status" not in call for call in calls)
    assert "LightRAG artifact check: pass" in output
    assert "Retrieval regression: pass" in output
    assert (tmp_path / "query-calls.txt").exists()
    assert not (tmp_path / "legacy-calls.txt").exists()
    assert status.read_bytes() == status_before
