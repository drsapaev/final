#!/usr/bin/env python3
"""Update DevBrain status after successful LightRAG acceptance."""

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
    concept_count: int | None = None,
    edge_count: int | None = None,
) -> None:
    root = root or repo_root()
    commit = commit or git_commit(root)
    verified_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    status_path = root / "docs" / "devbrain" / "DEVBRAIN_STATUS.md"
    text = status_path.read_text(encoding="utf-8")

    text = text.replace(
        "| LightRAG | missing unless verified | Do not assume active unless graph storage and query commands exist. |",
        "| LightRAG | active relationship fallback | `ai/lightrag` exists; relationship graph acceptance passed; generated graph storage remains gitignored. |",
    )
    text = text.replace(
        "| LightRAG graph/query path | missing unless verified | Must be proven by filesystem checks and query command before use. |",
        "| LightRAG relationship graph | active relationship fallback | Uses `ai/lightrag` scripts; acceptance passed; generated graph storage is gitignored. |",
    )

    light_body = f"""- Current status: `active relationship fallback`.
- Evidence file: `ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md`.
- Relationship graph storage: `ai/lightrag/indexes/lightrag_graph/graph.json` (gitignored).
- Required checks:
  - `Test-Path ai/lightrag`
  - `Test-Path ai/lightrag/scripts/query.py`
  - `Test-Path ai/lightrag/scripts/ingest.py`
  - `Test-Path ai/lightrag/indexes/lightrag_graph/graph.json`
  - `./ai/lightrag/scripts/run_acceptance.ps1`
- Last indexed commit: `{commit}`
- Last verification date: `{verified_at}`
- Indexed document count: `{document_count}`
- Relationship concept count: `{concept_count}`
- Relationship edge count: `{edge_count}`
- Acceptance result: `simple locate, Telegram mixed-contract, registrar payment/status persistence, Alembic migration, notification anti-noise, and queue identity scenarios passed`
- Provider mode: `no-key fallback; DeepSeek bridge optional when DEEPSEEK_API_KEY is set`"""

    text = replace_section(text, "LightRAG Status", light_body, "Acceptance Gates")

    replacements = {
        "simple locate": "passed via LightRAG acceptance",
        "Telegram mixed-contract": "passed via LightRAG acceptance",
        "registrar payment/status persistence ownership": "passed via LightRAG acceptance",
        "Alembic migration ownership": "passed via LightRAG acceptance",
        "notification catalog anti-noise ownership": "passed via LightRAG acceptance",
        "queue identity/fairness ownership": "passed via LightRAG acceptance",
    }
    for gate, status in replacements.items():
        text = re.sub(
            rf"(?ms)(\d+\. `{re.escape(gate)}`\n   - Expected: .*?\n   - Status: `).*?(`\.)",
            rf"\g<1>{status}\2",
            text,
        )

    text = re.sub(
        r"\| LightRAG \| `TBD` \| `TBD` \| Missing unless verified\. \|",
        f"| LightRAG | `{commit}` | `{verified_at}` | Active relationship fallback; acceptance passed without external API. |",
        text,
    )

    status_path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", default=None)
    parser.add_argument("--document-count", type=int, default=None)
    parser.add_argument("--concept-count", type=int, default=None)
    parser.add_argument("--edge-count", type=int, default=None)
    args = parser.parse_args()
    update_status(
        commit=args.commit,
        document_count=args.document_count,
        concept_count=args.concept_count,
        edge_count=args.edge_count,
    )
    print("DEVBRAIN_STATUS.md updated for LightRAG.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
