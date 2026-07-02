#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

from clinic_lifecycle_common import app_root, fail, load_clinic_env, pass_message, run_command


_RELEASE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_REF_FORBIDDEN_CHARS = set(":\\ \t\r\n")
_IMPORTED_REF_NAMESPACE = "refs/clinic-releases"


def _validate_release_name(value: str) -> str:
    release_name = value.strip()
    if not _RELEASE_NAME_RE.fullmatch(release_name):
        fail(
            "Artifact manifest has an invalid release_name. "
            "Use 1-128 ASCII letters, digits, dots, underscores, or hyphens, starting with a letter or digit."
        )
    return release_name


def _validate_ref_component(value: str, *, field_name: str) -> str:
    ref = value.strip()
    if not ref:
        fail(f"Missing release artifact {field_name}")
    if ref.startswith("-") or any(char in _REF_FORBIDDEN_CHARS or ord(char) < 32 for char in ref):
        fail(f"Unsafe release artifact {field_name}: {ref}")
    return ref


def _validate_ref_prefix(value: str) -> str:
    ref_prefix = _validate_ref_component(value.rstrip("/"), field_name="ref-prefix")
    if ref_prefix != _IMPORTED_REF_NAMESPACE and not ref_prefix.startswith(f"{_IMPORTED_REF_NAMESPACE}/"):
        fail(f"Imported release ref-prefix must stay under {_IMPORTED_REF_NAMESPACE}: {ref_prefix}")
    return ref_prefix


def _validate_imported_ref(ref: str) -> None:
    if subprocess.run(
        ["git", "check-ref-format", ref],
        cwd=str(app_root()),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode != 0:
        fail(f"Imported release ref is not a valid git ref: {ref}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import an approved release artifact into the local clinic host git repo."
    )
    parser.add_argument(
        "--artifact-file",
        required=True,
        help="Path to the approved release artifact zip created by build_release_artifact.py",
    )
    parser.add_argument(
        "--ref-prefix",
        default="refs/clinic-releases",
        help="Local release ref namespace used for imported release artifacts",
    )
    args = parser.parse_args()

    load_clinic_env()

    artifact_file = Path(args.artifact_file).expanduser().resolve()
    if not artifact_file.exists():
        fail(f"Artifact file not found: {artifact_file}")

    with tempfile.TemporaryDirectory(prefix="clinic-import-artifact-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        with zipfile.ZipFile(artifact_file) as archive:
            try:
                archive.extract("release.bundle", path=temp_dir)
                archive.extract("release-manifest.json", path=temp_dir)
            except KeyError as exc:
                fail(f"Artifact is missing required file: {exc}")

        bundle_path = temp_dir / "release.bundle"
        manifest_path = temp_dir / "release-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        bundle_ref = _validate_ref_component(str(manifest.get("bundle_ref") or ""), field_name="bundle_ref")
        release_name = _validate_release_name(str(manifest.get("release_name") or ""))

        ref_prefix = _validate_ref_prefix(args.ref_prefix)
        imported_ref = f"{ref_prefix}/{release_name}"
        _validate_imported_ref(imported_ref)
        run_command(
            ["git", "fetch", "--force", str(bundle_path), f"{bundle_ref}:{imported_ref}"],
            cwd=app_root(),
        )

    print(f"IMPORTED_ARTIFACT_FILE={artifact_file}", flush=True)
    print(f"IMPORTED_RELEASE_NAME={release_name}", flush=True)
    print(f"IMPORTED_RELEASE_REF={imported_ref}", flush=True)
    pass_message("import_release_artifact completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
