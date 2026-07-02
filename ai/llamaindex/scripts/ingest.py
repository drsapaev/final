#!/usr/bin/env python3
"""Build a local no-key DevBrain retrieval index."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from source_catalog import repo_root, source_records


DEFAULT_MAX_CHARS = 200_000
TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]+")
SYMBOL_RE = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class|const|let|var|def)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


def storage_dir(root: Path) -> Path:
    configured = os.getenv("LLAMAINDEX_STORAGE_DIR")
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else root / path
    return root / "ai" / "llamaindex" / "storage"


def index_path(root: Path) -> Path:
    return storage_dir(root) / "devbrain_index.json"


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


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def summarize_symbols(text: str) -> list[str]:
    symbols = []
    for match in SYMBOL_RE.finditer(text):
        name = match.group(1)
        if name not in symbols:
            symbols.append(name)
        if len(symbols) >= 40:
            break
    return symbols


def read_text(path: Path, max_chars: int) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars]
    return text


def build_index(
    root: Path | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> dict:
    root = root or repo_root()
    records, missing = source_records(root=root)
    documents = []

    for record in records:
        path = root / record["path"]
        try:
            text = read_text(path, max_chars)
        except OSError:
            missing.append(record["path"])
            continue

        stat = path.stat()
        digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
        documents.append(
            {
                "path": record["path"],
                "label": record["label"],
                "source": record["source"],
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "sha256": digest,
                "symbols": summarize_symbols(text),
                "search_text": text,
            }
        )

    return {
        "schema": "devbrain-llamaindex-fallback-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "commit": git_commit(root),
        "document_count": len(documents),
        "missing": sorted(set(missing)),
        "documents": documents,
    }


def write_index(index: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    root = repo_root()
    index = build_index(root=root, max_chars=args.max_chars)
    output = args.output or index_path(root)
    write_index(index, output)

    print("DevBrain LlamaIndex ingest")
    print(f"index: {output}")
    print(f"commit: {index['commit']}")
    print(f"documents: {index['document_count']}")
    print(f"missing: {len(index['missing'])}")
    if index["missing"]:
        for item in index["missing"][:20]:
            print(f"- missing: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
