#!/usr/bin/env python3
"""Resolve the DevBrain LightRAG manifest into concrete source files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


EXCLUDED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "indexes",
    "node_modules",
    "storage",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_manifest_path(root: Path | None = None) -> Path:
    root = root or repo_root()
    return root / "ai" / "lightrag" / "data" / "manifest.json"


def load_manifest(path: Path | None = None) -> dict:
    manifest_path = path or default_manifest_path()
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)


def _iter_dir(path: Path, extensions: set[str]) -> Iterable[Path]:
    for child in sorted(path.rglob("*")):
        if not child.is_file() or _is_excluded(child):
            continue
        if extensions and child.suffix.lower() not in extensions:
            continue
        yield child


def source_records(
    manifest_path: Path | None = None,
    root: Path | None = None,
) -> tuple[list[dict], list[str], list[dict]]:
    root = root or repo_root()
    manifest = load_manifest(manifest_path)
    records: list[dict] = []
    missing: list[str] = []
    seen: set[str] = set()

    for entry in manifest.get("sources", []):
        rel_path = entry["path"].replace("\\", "/")
        source_path = root / rel_path
        entry_type = entry.get("type", "file")
        label = entry.get("label", rel_path)

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
            rel = path.relative_to(root).as_posix()
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

    focus = manifest.get("priority_focus_sources", [])
    return sorted(records, key=lambda item: item["path"]), missing, focus


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    records, missing, focus = source_records(args.manifest)
    if args.json:
        print(json.dumps({"records": records, "missing": missing, "focus": focus}, indent=2))
    else:
        print("DevBrain LightRAG source catalog")
        print(f"sources: {len(records)}")
        print(f"focus domains: {len(focus)}")
        if missing:
            print("missing:")
            for item in missing:
                print(f"- {item}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
