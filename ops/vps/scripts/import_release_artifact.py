#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

from clinic_lifecycle_common import app_root, fail, load_clinic_env, pass_message, run_command


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

        bundle_ref = str(manifest.get("bundle_ref") or "").strip()
        release_name = str(manifest.get("release_name") or "").strip()
        if not bundle_ref:
            fail("Artifact manifest is missing bundle_ref")
        if not release_name:
            fail("Artifact manifest is missing release_name")

        imported_ref = f"{args.ref_prefix.rstrip('/')}/{release_name}"
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
