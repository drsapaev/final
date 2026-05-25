#!/usr/bin/env python3
"""No-key smoke test for the DevBrain LlamaIndex fallback layer."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import ingest
import query as query_module
import update_status
from source_catalog import repo_root, source_records


SMOKE_QUERY = "Where is runtime API/WS origin resolution implemented on the frontend?"
EXPECTED_TOP_PATH = "frontend/src/api/runtime.js"
REQUIRED_ANCHORS = {
    "AGENTS.md",
    "docs/devbrain/PROJECT_MEMORY.md",
    "docs/devbrain/DEVBRAIN_STATUS.md",
}


def git_diff_has_status_change(root: Path) -> bool:
    try:
        output = subprocess.check_output(
            ["git", "diff", "--", "docs/devbrain/DEVBRAIN_STATUS.md"],
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception:
        return False
    return bool(output.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-status", action="store_true")
    args = parser.parse_args()

    root = repo_root()
    records, missing = source_records(root=root)
    paths = {record["path"] for record in records}
    missing_anchors = sorted(REQUIRED_ANCHORS - paths)
    if missing_anchors:
        print("Smoke failed: required anchors missing from manifest:")
        for path in missing_anchors:
            print(f"- {path}")
        return 1

    index = ingest.build_index(root=root)
    output = ingest.index_path(root)
    ingest.write_index(index, output)
    print("DevBrain LlamaIndex smoke")
    print(f"index: {output}")
    print(f"documents: {index['document_count']}")
    print(f"manifest missing: {len(missing)}")

    results = query_module.search(SMOKE_QUERY, top_k=5, root=root)
    print(f"query: {SMOKE_QUERY}")
    for position, result in enumerate(results, start=1):
        print(f"{position}. {result['path']} score={result['score']}")

    if not any(result["path"] == EXPECTED_TOP_PATH for result in results[:3]):
        print(f"Smoke failed: expected {EXPECTED_TOP_PATH} in top 3 results.")
        return 1

    if args.update_status:
        update_status.update_status(
            root=root,
            commit=index["commit"],
            document_count=index["document_count"],
            smoke_query=SMOKE_QUERY,
            smoke_result=EXPECTED_TOP_PATH,
        )
        changed = git_diff_has_status_change(root)
        print(f"status updated: {'yes' if changed else 'already current'}")

    print("smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
