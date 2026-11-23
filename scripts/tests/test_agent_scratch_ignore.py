"""Exercise session-artifact ignores without touching the production checkout."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRATCH_ROOTS = (".scratch", ".gate_artifacts")


def git_environment() -> dict[str, str]:
    # A caller's GIT_INDEX_FILE/GIT_WORK_TREE must never redirect the fixture.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return env


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=git_environment(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def initialize_repo(path: Path) -> Path:
    # An empty template avoids installing hooks in this disposable repository.
    git(path, "init", "--template=")
    shutil.copyfile(ROOT / ".gitignore", path / ".gitignore")
    (path / "tracked.txt").write_text("original\n", encoding="utf-8")
    git(path, "add", ".gitignore", "tracked.txt")
    commit_fixture(path)
    return path


def commit_fixture(path: Path) -> None:
    git(
        path,
        "-c",
        "user.name=SYNTHETIC-Agent",
        "-c",
        "user.email=synthetic@example.invalid",
        "commit",
        "--no-gpg-sign",
        "-m",
        "Synthetic fixture",
    )


def write_file(repo: Path, relative: str) -> Path:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("synthetic session artifact\n", encoding="utf-8")
    return path


class ScratchIgnoreTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="agent-scratch-ignore-")
        self.addCleanup(temporary.cleanup)
        self.repo = initialize_repo(Path(temporary.name))

    def test_root_session_artifacts_leave_git_status_clean(self):
        for scratch_root in SCRATCH_ROOTS:
            with self.subTest(root=scratch_root):
                artifact = write_file(self.repo, f"{scratch_root}/session/receipt.json")
                self.assertEqual(git(self.repo, "status", "--porcelain"), "")
                self.assertEqual(
                    artifact.read_text(encoding="utf-8"),
                    "synthetic session artifact\n",
                )

    def test_other_untracked_files_remain_visible(self):
        for relative in (
            "backend/.scratch/source.py",
            "frontend/.gate_artifacts/source.ts",
            ".scratch-notes/receipt.json",
            ".gate_artifacts-notes/receipt.json",
            "backend/unexpected_source.py",
        ):
            with self.subTest(path=relative):
                artifact = write_file(self.repo, relative)
                try:
                    self.assertEqual(
                        git(self.repo, "status", "--porcelain", "--untracked-files=all").strip(),
                        f"?? {relative}",
                    )
                finally:
                    artifact.unlink()

    def test_tracked_changes_remain_visible_beside_ignored_scratch(self):
        for scratch_root in SCRATCH_ROOTS:
            write_file(self.repo, f"{scratch_root}/receipt.json")
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")

        self.assertEqual(git(self.repo, "status", "--porcelain").strip(), "M tracked.txt")

    def test_force_tracked_file_inside_scratch_remains_visible_when_modified(self):
        artifact = write_file(self.repo, ".scratch/source.txt")
        git(self.repo, "add", "--force", ".scratch/source.txt")
        commit_fixture(self.repo)
        artifact.write_text("changed\n", encoding="utf-8")

        self.assertEqual(
            git(self.repo, "status", "--porcelain").strip(), "M .scratch/source.txt"
        )


class SourceReservationTests(unittest.TestCase):
    def test_session_artifact_roots_contain_no_tracked_source(self):
        tracked = git(ROOT, "ls-files", "-z").split("\0")
        reserved = tuple(f"{root}/" for root in SCRATCH_ROOTS)

        self.assertEqual(
            [path for path in tracked if path.casefold().startswith(reserved)], []
        )
