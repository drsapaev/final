#!/usr/bin/env python3
"""Build a local relationship graph for DevBrain LightRAG fallback retrieval."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import deepseek_bridge
from source_catalog import repo_root, source_records


TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]+")
DEFAULT_MAX_CHARS = 160_000


def storage_dir(root: Path) -> Path:
    configured = os.getenv("LIGHTRAG_STORAGE_DIR")
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else root / path
    return root / "ai" / "lightrag" / "indexes" / "lightrag_graph"


def graph_path(root: Path) -> Path:
    return storage_dir(root) / "graph.json"


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


def tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}


def read_text(path: Path, max_chars: int) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:max_chars] if len(text) > max_chars else text


def path_exists(root: Path, rel_path: str) -> bool:
    if "*" in rel_path:
        return True
    path = root / rel_path
    return path.exists()


def build_graph(root: Path | None = None, max_chars: int = DEFAULT_MAX_CHARS) -> dict:
    root = root or repo_root()
    records, missing, focus_sources = source_records(root=root)
    documents: dict[str, dict] = {}
    edges: list[dict] = []
    concepts: dict[str, dict] = {}

    for record in records:
        path = root / record["path"]
        try:
            text = read_text(path, max_chars)
        except OSError:
            missing.append(record["path"])
            continue

        text_terms = tokenize(text)
        path_terms = tokenize(record["path"])
        digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
        documents[record["path"]] = {
            "id": f"doc:{record['path']}",
            "path": record["path"],
            "label": record["label"],
            "source": record["source"],
            "sha256": digest,
            "terms": sorted((text_terms | path_terms))[:4000],
        }

    for focus in focus_sources:
        concept_id = focus["id"]
        focus_terms = {term.lower() for term in focus.get("terms", [])}
        concepts[concept_id] = {
            "id": concept_id,
            "title": focus.get("title", concept_id),
            "terms": sorted(focus_terms),
            "canonical_anchors": focus.get("canonical_anchors", []),
            "first_touch": focus.get("first_touch", []),
            "verification": focus.get("verification", []),
        }

        for rel_path in focus.get("canonical_anchors", []) + focus.get("first_touch", []) + focus.get("verification", []):
            if path_exists(root, rel_path):
                edges.append(
                    {
                        "from": f"concept:{concept_id}",
                        "to": f"path:{rel_path}",
                        "type": "declares_ownership_path",
                        "weight": 10,
                    }
                )

        for path, document in documents.items():
            path_text = path.lower()
            doc_terms = set(document["terms"])
            overlap = focus_terms & doc_terms
            if any(term in path_text for term in focus_terms):
                overlap = overlap | {term for term in focus_terms if term in path_text}
            if not overlap:
                continue
            edges.append(
                {
                    "from": f"concept:{concept_id}",
                    "to": document["id"],
                    "type": "mentions",
                    "weight": len(overlap),
                    "terms": sorted(overlap),
                }
            )

    graph = {
        "schema": "devbrain-lightrag-relationship-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "commit": git_commit(root),
        "provider": deepseek_bridge.provider_status(),
        "embedding_mode": "local term relationships",
        "document_count": len(documents),
        "concept_count": len(concepts),
        "edge_count": len(edges),
        "missing": sorted(set(missing)),
        "concepts": concepts,
        "documents": documents,
        "edges": edges,
    }
    return graph


def write_graph(graph: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    root = repo_root()
    graph = build_graph(root=root, max_chars=args.max_chars)
    output = args.output or graph_path(root)
    write_graph(graph, output)

    print("DevBrain LightRAG ingest")
    print(f"graph: {output}")
    print(f"commit: {graph['commit']}")
    print(f"provider: {graph['provider']}")
    print(f"documents: {graph['document_count']}")
    print(f"concepts: {graph['concept_count']}")
    print(f"edges: {graph['edge_count']}")
    print(f"missing: {len(graph['missing'])}")
    return 0 if graph["edge_count"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
