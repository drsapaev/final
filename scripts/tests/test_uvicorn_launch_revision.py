"""Exercise the Windows launcher with a disposable repository and a child probe."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

LAUNCHER = Path(__file__).resolve().parents[1] / "run_uvicorn_prod.ps1"

HARNESS = r"""
$ErrorActionPreference = 'Stop'
$source = [IO.File]::ReadAllText($env:UVICORN_PROBE_SOURCE)
$rootAssignment = '$Repo   = ''C:\final'''
if (-not $source.Contains($rootAssignment)) {
    throw 'Production root assignment changed. Refusing to execute the launcher.'
}
$source = $source.Replace($rootAssignment, '$Repo = $env:UVICORN_PROBE_ROOT')
$env:ComSpec = 'Invoke-UvicornProbe'

if ($env:UVICORN_PROBE_SCENARIO -eq 'git-unavailable') {
    function Get-Command {
        [CmdletBinding()]
        param([string]$Name, [string]$CommandType)
        throw 'No Git executable in the synthetic service environment.'
    }
}

function Invoke-UvicornProbe {
    param([string]$Mode, [string]$Command)
    [ordered]@{
        revision = $env:APP_GIT_REVISION
        version = $env:APP_VERSION
        python_utf8 = $env:PYTHONUTF8
        io_encoding = $env:PYTHONIOENCODING
        cwd = (Get-Location).Path
        mode = $Mode
        command = $Command
    } | ConvertTo-Json -Compress
    $global:LASTEXITCODE = 17
}

& ([scriptblock]::Create($source))
exit $LASTEXITCODE
"""


@pytest.mark.parametrize("shell", ["powershell.exe", "pwsh.exe"])
@pytest.mark.parametrize(
    "scenario",
    [
        "clean-main",
        "ignored-file",
        "dirty-tracked",
        "untracked",
        "different-branch",
        "different-repository-root",
        "git-unavailable",
        "inherited-index",
    ],
)
def test_launcher_verifies_revision_and_still_boots_without_git_proof(
    tmp_path, scenario, shell
):
    powershell = shutil.which(shell)
    git_path = shutil.which("git.exe")
    if not powershell or not git_path:
        pytest.skip("Windows PowerShell and Git are required for the launcher harness")

    repo = tmp_path / "repo"
    backend = repo / "backend"
    backend.mkdir(parents=True)
    tracked_file = backend / "fixture.txt"
    tracked_file.write_text("initial\n", encoding="ascii")
    (repo / ".gitignore").write_text("ignored-*\n", encoding="ascii")

    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=str(tmp_path / "gitconfig"),
    )

    def git(*args: str) -> str:
        return subprocess.run(
            [git_path, "-C", str(repo), *args],
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        ).stdout.strip()

    git("init", "--quiet", "-b", "main")
    git("add", "--", ".")
    git(
        "-c",
        "user.name=Launcher Test",
        "-c",
        "user.email=launcher-test@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "Synthetic fixture",
    )
    revision = git("rev-parse", "HEAD")
    launch_root = repo
    if scenario == "dirty-tracked":
        tracked_file.write_text("changed\n", encoding="ascii")
    elif scenario == "untracked":
        (backend / "new.txt").write_text("untracked\n", encoding="ascii")
    elif scenario == "ignored-file":
        (backend / "ignored-fixture.txt").write_text("ignored\n", encoding="ascii")
    elif scenario == "different-branch":
        git("switch", "--quiet", "-c", "fixture")
    elif scenario == "different-repository-root":
        launch_root = repo / "nested"
        (launch_root / "backend").mkdir(parents=True)
    elif scenario == "inherited-index":
        env["GIT_INDEX_FILE"] = str(repo / ".git" / "index")

    harness = tmp_path / "launch_probe.ps1"
    harness.write_text(HARNESS, encoding="ascii")
    env.update(
        UVICORN_PROBE_SOURCE=str(LAUNCHER),
        UVICORN_PROBE_ROOT=str(launch_root),
        UVICORN_PROBE_SCENARIO=scenario,
        APP_GIT_REVISION="a" * 40,
        APP_VERSION="9.8.7",
    )
    outcome = subprocess.run(
        [powershell, "-NoProfile", "-File", str(harness)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert outcome.returncode == 17, outcome.stdout + outcome.stderr

    evidence = json.loads(outcome.stdout)
    expected = revision if scenario in {"clean-main", "ignored-file"} else "unverified"
    assert evidence == {
        "revision": expected,
        "version": "9.8.7",
        "python_utf8": "1",
        "io_encoding": "utf-8",
        "cwd": str(launch_root / "backend"),
        "mode": "/c",
        "command": (
            f'"{launch_root / "backend" / ".venv" / "Scripts" / "python.exe"}" '
            f'-m uvicorn app.main:app --host 127.0.0.1 --port 18000 --log-level warning '
            f'>> "{launch_root / "tools" / "uvicorn_backend.log"}" 2>&1'
        ),
    }
