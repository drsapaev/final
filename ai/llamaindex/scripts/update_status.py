#!/usr/bin/env python3
"""Update DevBrain status after a successful LlamaIndex smoke."""

from __future__ import annotations

import argparse
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from source_catalog import repo_root


def git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).strip()
    except Exception:
        return "unknown"


def replace_section(text: str, header: str, body: str, next_header: str) -> str:
    pattern = rf"(?ms)^## {re.escape(header)}\n\n.*?(?=^## {re.escape(next_header)}\n)"
    replacement = f"## {header}\n\n{body.rstrip()}\n\n"
    updated, count = re.subn(pattern, replacement, text)
    if count != 1:
        raise RuntimeError(f"could not update section: {header}")
    return updated


def update_status(
    root: Path | None = None,
    commit: str | None = None,
    document_count: int | None = None,
    smoke_query: str = "Where is runtime API/WS origin resolution implemented on the frontend?",
    smoke_result: str = "frontend/src/api/runtime.js",
) -> None:
    root = root or repo_root()
    commit = commit or git_commit(root)
    verified_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    status_path = root / "docs" / "devbrain" / "DEVBRAIN_STATUS.md"
    text = status_path.read_text(encoding="utf-8")

    text = text.replace(
        "| LlamaIndex | missing unless verified | Do not assume active unless `ai/llamaindex` and index/query commands exist. |",
        "| LlamaIndex | active local fallback | `ai/llamaindex` exists; smoke passed without external API; generated storage remains gitignored. |",
    )
    text = text.replace(
        "| LlamaIndex docs/references | documented | Not an active retrieval source without local index evidence. |",
        "| LlamaIndex portable retrieval | active local fallback | Uses `ai/llamaindex` scripts; no-key smoke passed; generated storage is gitignored. |",
    )

    doc_count = document_count if document_count is not None else "TBD"
    llamaindex_body = f"""- Current status: `active local fallback`.
- Required checks:
  - `Test-Path ai/llamaindex`
  - `Test-Path ai/llamaindex/scripts/query.py`
  - `Test-Path ai/llamaindex/scripts/ingest.py`
  - `Test-Path ai/llamaindex/storage/devbrain_index.json`
  - `./ai/llamaindex/scripts/run_smoke.ps1`
- Last indexed commit: `{commit}`
- Last verification date: `{verified_at}`
- Indexed document count: `{doc_count}`
- Acceptance result: `simple locate smoke passed in no-key fallback mode`
- Smoke query: `{smoke_query}`
- Smoke result: `{smoke_result}`"""

    text = replace_section(text, "LlamaIndex Status", llamaindex_body, "LightRAG Status")

    text = re.sub(
        r"(?ms)1\. `simple locate`\n   - Expected: reliably finds canonical files for a narrow known task\.\n   - Status: `.*?`\.",
        "1. `simple locate`\n   - Expected: reliably finds canonical files for a narrow known task.\n   - Status: `passed via ai/llamaindex smoke in no-key fallback mode`.",
        text,
    )
    text = re.sub(
        r"(?m)^\| LlamaIndex \| `[^`]*` \| `[^`]*` \| .* \|$",
        f"| LlamaIndex | `{commit}` | `{verified_at}` | Active local fallback; smoke passed without external API. |",
        text,
    )

    status_path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", default=None)
    parser.add_argument("--document-count", type=int, default=None)
    parser.add_argument("--smoke-query", default="Where is runtime API/WS origin resolution implemented on the frontend?")
    parser.add_argument("--smoke-result", default="frontend/src/api/runtime.js")
    args = parser.parse_args()

    update_status(
        commit=args.commit,
        document_count=args.document_count,
        smoke_query=args.smoke_query,
        smoke_result=args.smoke_result,
    )
    print("DEVBRAIN_STATUS.md updated for LlamaIndex.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
