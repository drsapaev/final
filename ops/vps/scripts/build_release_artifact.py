#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from clinic_lifecycle_common import app_root, fail, load_clinic_env, pass_message, run_command


_REF_FORBIDDEN_CHARS = set(":\\ \t\r\n")
_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    cleaned = cleaned.strip("-._")
    return cleaned or "release"


def _validate_build_ref(value: str) -> str:
    git_ref = value.strip()
    if not git_ref:
        fail("Release artifact --ref must not be empty")
    if git_ref.startswith("-") or any(char in _REF_FORBIDDEN_CHARS or ord(char) < 32 for char in git_ref):
        fail(f"Release artifact --ref is unsafe: {git_ref}")
    return git_ref


def _resolve_commit(git_ref: str) -> str:
    result = run_command(
        ["git", "rev-parse", "--verify", "--quiet", f"{git_ref}^{{commit}}"],
        cwd=app_root(),
        check=False,
    )
    commit_sha = result.stdout.strip()
    if result.returncode != 0 or not _COMMIT_SHA_RE.fullmatch(commit_sha):
        fail(f"Release artifact --ref does not resolve to a commit: {git_ref}")
    return commit_sha


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an approved release artifact for online or offline clinic updates."
    )
    parser.add_argument("--ref", dest="git_ref", default="HEAD", help="Release ref to package")
    parser.add_argument(
        "--output-dir",
        default=str(app_root() / "output" / "release-artifacts"),
        help="Directory where the artifact zip will be written",
    )
    parser.add_argument(
        "--release-name",
        default="",
        help="Optional release name for the artifact file and imported ref",
    )
    args = parser.parse_args()

    load_clinic_env()

    root = app_root()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    git_ref = _validate_build_ref(args.git_ref)
    commit_sha = _resolve_commit(git_ref)
    short_sha = commit_sha[:12]
    release_name = _safe_name(args.release_name or f"clinic-release-{short_sha}")

    with tempfile.TemporaryDirectory(prefix="clinic-release-artifact-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        bundle_path = temp_dir / "release.bundle"
        manifest_path = temp_dir / "release-manifest.json"

        run_command(
            ["git", "bundle", "create", str(bundle_path), git_ref],
            cwd=root,
        )

        manifest = {
            "format_version": 1,
            "artifact_kind": "approved_release_artifact",
            "release_name": release_name,
            "bundle_ref": git_ref,
            "commit_sha": commit_sha,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "delivery_modes": ["github_release_asset", "offline_package"],
            "notes": "Import this artifact into a clinic host repo, then deploy via UPDATE_RELEASE_REF.",
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        artifact_path = output_dir / f"{release_name}.zip"
        with zipfile.ZipFile(artifact_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(bundle_path, arcname="release.bundle")
            archive.write(manifest_path, arcname="release-manifest.json")

    print(f"ARTIFACT_FILE={artifact_path}", flush=True)
    print(f"ARTIFACT_RELEASE_NAME={release_name}", flush=True)
    print(f"ARTIFACT_RELEASE_REF={git_ref}", flush=True)
    print(f"ARTIFACT_COMMIT_SHA={commit_sha}", flush=True)
    pass_message("build_release_artifact completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
