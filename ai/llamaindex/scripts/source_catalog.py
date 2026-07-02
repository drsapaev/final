#!/usr/bin/env python3
"""Resolve the DevBrain LlamaIndex manifest into concrete source files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "storage",
    "indexes",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_manifest_path(root: Path | None = None) -> Path:
    root = root or repo_root()
    return root / "ai" / "llamaindex" / "data" / "manifest.json"


def load_manifest(path: Path | None = None) -> dict:
    manifest_path = path or default_manifest_path()
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _posix(path: Path) -> str:
    return path.as_posix()


def _is_excluded(path: Path) -> bool:
    return any(part in DEFAULT_EXCLUDED_DIRS for part in path.parts)


def _iter_dir(path: Path, extensions: set[str]) -> Iterable[Path]:
    for child in sorted(path.rglob("*")):
        if not child.is_file():
            continue
        if _is_excluded(child):
            continue
        if extensions and child.suffix.lower() not in extensions:
            continue
        yield child


def source_records(
    manifest_path: Path | None = None,
    root: Path | None = None,
) -> tuple[list[dict], list[str]]:
    root = root or repo_root()
    manifest = load_manifest(manifest_path)
    records: list[dict] = []
    missing: list[str] = []
    seen: set[str] = set()

    for entry in manifest.get("sources", []):
        rel_path = entry["path"].replace("\\", "/")
        source_path = root / rel_path
        label = entry.get("label", rel_path)
        entry_type = entry.get("type", "file")

        if entry_type == "file":
            if not source_path.is_file():
                missing.append(rel_path)
                continue
            paths = [source_path]
        elif entry_type == "dir":
            if not source_path.is_dir():
                missing.append(rel_path)
                continue
            extensions = {ext.lower() for ext in entry.get("extensions", [])}
            paths = list(_iter_dir(source_path, extensions))
        else:
            missing.append(f"{rel_path} (unsupported type: {entry_type})")
            continue

        for path in paths:
            rel = _posix(path.relative_to(root))
            if rel in seen:
                continue
            seen.add(rel)
            records.append(
                {
                    "path": rel,
                    "label": label,
                    "source": rel_path,
                    "type": entry_type,
                }
            )

    return sorted(records, key=lambda item: item["path"]), missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Emit JSON records.")
    args = parser.parse_args()

    records, missing = source_records(args.manifest)
    if args.json:
        print(json.dumps({"records": records, "missing": missing}, indent=2))
    else:
        print("DevBrain source catalog")
        print(f"sources: {len(records)}")
        if missing:
            print("missing:")
            for item in missing:
                print(f"- {item}")
        for record in records:
            print(f"- {record['path']} ({record['label']})")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
