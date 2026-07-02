#!/usr/bin/env python3
"""Export LightRAG fallback graph artifacts without committing generated storage."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import ingest
from source_catalog import repo_root


DEFAULT_VECTOR_DIMS = 256


def artifact_dir(root: Path) -> Path:
    configured = os.getenv("LIGHTRAG_ARTIFACT_DIR")
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else root / path
    return ingest.storage_dir(root) / "artifacts"


def load_graph(root: Path, build_if_missing: bool = False) -> dict:
    path = ingest.graph_path(root)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    if not build_if_missing:
        raise FileNotFoundError(
            f"LightRAG graph not found: {path}. Run ai/lightrag/scripts/run_ingest.ps1 first."
        )
    graph = ingest.build_graph(root=root)
    ingest.write_graph(graph, path)
    return graph


def stable_vector_id(entity_id: str) -> str:
    digest = hashlib.sha256(entity_id.encode("utf-8")).hexdigest()[:16]
    return f"vec:{digest}"


def term_index(term: str, dims: int) -> int:
    digest = hashlib.sha256(term.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % dims


def sparse_vector(terms: Iterable[str], dims: int) -> dict[str, float]:
    counts: dict[int, int] = {}
    for raw_term in terms:
        term = str(raw_term).strip().lower()
        if not term:
            continue
        index = term_index(term, dims)
        counts[index] = counts.get(index, 0) + 1

    if not counts:
        return {}

    max_count = max(counts.values())
    return {
        str(index): round(count / max_count, 6)
        for index, count in sorted(counts.items())
    }


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
            count += 1
    return count


def concept_entities(graph: dict) -> list[dict]:
    entities = []
    for concept_id, concept in sorted(graph.get("concepts", {}).items()):
        entity_id = f"concept:{concept_id}"
        entities.append(
            {
                "id": entity_id,
                "kind": "concept",
                "concept_id": concept_id,
                "title": concept.get("title", concept_id),
                "terms": concept.get("terms", []),
                "canonical_anchors": concept.get("canonical_anchors", []),
                "first_touch": concept.get("first_touch", []),
                "verification": concept.get("verification", []),
            }
        )
    return entities


def document_entities(graph: dict) -> list[dict]:
    entities = []
    for path, document in sorted(graph.get("documents", {}).items()):
        entities.append(
            {
                "id": document.get("id", f"doc:{path}"),
                "kind": "document",
                "path": path,
                "label": document.get("label", ""),
                "source": document.get("source", ""),
                "sha256": document.get("sha256", ""),
                "terms": document.get("terms", []),
            }
        )
    return entities


def relationship_rows(graph: dict) -> list[dict]:
    rows = []
    for index, edge in enumerate(graph.get("edges", []), start=1):
        rows.append(
            {
                "id": f"rel:{index:06d}",
                "from": edge.get("from"),
                "to": edge.get("to"),
                "type": edge.get("type", "related"),
                "weight": edge.get("weight", 1),
                "terms": edge.get("terms", []),
            }
        )
    return rows


def doc_store_rows(graph: dict) -> list[dict]:
    rows = []
    for path, document in sorted(graph.get("documents", {}).items()):
        rows.append(
            {
                "id": document.get("id", f"doc:{path}"),
                "path": path,
                "label": document.get("label", ""),
                "source": document.get("source", ""),
                "sha256": document.get("sha256", ""),
                "term_count": len(document.get("terms", [])),
            }
        )
    return rows


def vector_rows(entities: Iterable[dict], dims: int) -> list[dict]:
    rows = []
    for entity in entities:
        entity_id = entity["id"]
        vector_terms = entity.get("terms", [])
        rows.append(
            {
                "id": stable_vector_id(entity_id),
                "entity_id": entity_id,
                "kind": entity.get("kind", ""),
                "vector_mode": "local_sparse_term_hash",
                "dimensions": dims,
                "sparse_values": sparse_vector(vector_terms, dims),
            }
        )
    return rows


def graph_store(graph: dict, entities: list[dict], relationships: list[dict]) -> dict:
    adjacency: dict[str, list[dict]] = {}
    for relationship in relationships:
        source = relationship.get("from")
        if not source:
            continue
        adjacency.setdefault(str(source), []).append(
            {
                "to": relationship.get("to"),
                "type": relationship.get("type"),
                "weight": relationship.get("weight"),
            }
        )

    return {
        "schema": "devbrain-lightrag-artifacts-v1",
        "source_schema": graph.get("schema"),
        "commit": graph.get("commit"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entity_count": len(entities),
        "relationship_count": len(relationships),
        "adjacency": adjacency,
    }


def export_artifacts(root: Path, output_dir: Path, build_if_missing: bool, dims: int) -> dict:
    graph = load_graph(root, build_if_missing=build_if_missing)
    concepts = concept_entities(graph)
    documents = document_entities(graph)
    entities = concepts + documents
    relationships = relationship_rows(graph)
    vectors = vector_rows(entities, dims=dims)
    docs = doc_store_rows(graph)
    store = graph_store(graph, entities, relationships)

    files = {
        "entities": output_dir / "entities.jsonl",
        "relationships": output_dir / "relationships.jsonl",
        "vector_store": output_dir / "vector_store.jsonl",
        "doc_store": output_dir / "doc_store.jsonl",
        "graph_store": output_dir / "graph_store.json",
        "metadata": output_dir / "metadata.json",
    }

    counts = {
        "entities": write_jsonl(files["entities"], entities),
        "relationships": write_jsonl(files["relationships"], relationships),
        "vector_store": write_jsonl(files["vector_store"], vectors),
        "doc_store": write_jsonl(files["doc_store"], docs),
    }
    write_json(files["graph_store"], store)

    metadata = {
        "schema": "devbrain-lightrag-artifact-metadata-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_graph": str(ingest.graph_path(root)),
        "output_dir": str(output_dir),
        "commit": graph.get("commit"),
        "provider": graph.get("provider"),
        "embedding_mode": graph.get("embedding_mode"),
        "vector_mode": "local_sparse_term_hash",
        "vector_dimensions": dims,
        "counts": {
            **counts,
            "graph_store": 1,
            "metadata": 1,
        },
        "files": {name: str(path) for name, path in files.items()},
    }
    write_json(files["metadata"], metadata)
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--build-if-missing", action="store_true")
    parser.add_argument("--vector-dims", type=int, default=DEFAULT_VECTOR_DIMS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = repo_root()
    output_dir = args.output_dir or artifact_dir(root)
    metadata = export_artifacts(
        root=root,
        output_dir=output_dir,
        build_if_missing=args.build_if_missing,
        dims=args.vector_dims,
    )

    if args.json:
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        return 0

    print("DevBrain LightRAG artifact export")
    print(f"output: {metadata['output_dir']}")
    print(f"commit: {metadata['commit']}")
    print(f"vector_mode: {metadata['vector_mode']}")
    for name, count in metadata["counts"].items():
        print(f"{name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
