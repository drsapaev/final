#!/usr/bin/env python3
"""Query the local DevBrain LightRAG relationship graph."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import ingest
from source_catalog import repo_root


TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]+")
DOMAIN_HINTS = {
    "registrar": {"registrar_payment_status"},
    "payment": {"registrar_payment_status"},
    "billing": {"registrar_payment_status"},
    "queue": {"queue_identity_fairness"},
    "doctor.id": {"queue_identity_fairness"},
    "specialist": {"queue_identity_fairness"},
    "telegram": {"telegram_token_security_storage"},
    "token": {"telegram_token_security_storage"},
    "alembic": {"alembic_migration_ownership"},
    "migration": {"alembic_migration_ownership"},
    "sqlalchemy": {"alembic_migration_ownership"},
    "notification": {"notification_catalog_anti_noise"},
    "preferences": {"notification_catalog_anti_noise"},
    "mute": {"notification_catalog_anti_noise"},
    "snooze": {"notification_catalog_anti_noise"},
    "dnd": {"notification_catalog_anti_noise"},
    "route": {"route_registry_ssot"},
    "routing": {"route_registry_ssot"},
    "emr": {"emr_lab_ownership"},
    "lab": {"emr_lab_ownership"},
    "service": {"service_catalog_truth"},
    "catalog": {"notification_catalog_anti_noise", "service_catalog_truth"},
}


def tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}


def load_graph(root: Path, fallback_build: bool = True) -> dict:
    path = ingest.graph_path(root)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    if not fallback_build:
        raise FileNotFoundError(f"graph not found: {path}")
    graph = ingest.build_graph(root=root)
    ingest.write_graph(graph, path)
    return graph


def concept_score(concept: dict, query_text: str, query_terms: set[str]) -> tuple[int, list[str]]:
    concept_terms = set(concept.get("terms", []))
    title_terms = tokenize(concept.get("title", ""))
    reasons = sorted((concept_terms | title_terms) & query_terms)
    score = len(reasons) * 20
    lowered = query_text.lower()
    for raw, concept_ids in DOMAIN_HINTS.items():
        if raw in lowered and concept["id"] in concept_ids:
            score += 45
            reasons.append(raw)
    return score, sorted(set(reasons))


def document_matches(graph: dict, concept_id: str, limit: int = 8) -> list[dict]:
    docs = []
    for edge in graph.get("edges", []):
        if edge.get("from") != f"concept:{concept_id}" or edge.get("type") != "mentions":
            continue
        doc_id = edge.get("to", "")
        if not doc_id.startswith("doc:"):
            continue
        path = doc_id.removeprefix("doc:")
        document = graph.get("documents", {}).get(path)
        if not document:
            continue
        docs.append(
            {
                "path": path,
                "label": document.get("label", ""),
                "weight": edge.get("weight", 0),
                "terms": edge.get("terms", []),
            }
        )
    return sorted(docs, key=lambda item: (-item["weight"], item["path"]))[:limit]


def search(query_text: str, top_k: int = 6, root: Path | None = None) -> list[dict]:
    root = root or repo_root()
    graph = load_graph(root)
    query_terms = tokenize(query_text)
    results = []

    for concept in graph.get("concepts", {}).values():
        score, reasons = concept_score(concept, query_text, query_terms)
        if score <= 0:
            continue
        results.append(
            {
                "concept": concept["id"],
                "title": concept.get("title", concept["id"]),
                "score": score,
                "reasons": reasons,
                "canonical_anchors": concept.get("canonical_anchors", []),
                "first_touch": concept.get("first_touch", []),
                "verification": concept.get("verification", []),
                "related_documents": document_matches(graph, concept["id"]),
            }
        )

    return sorted(results, key=lambda item: (-item["score"], item["concept"]))[:top_k]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="+")
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    query_text = " ".join(args.query)
    results = search(query_text, top_k=args.top_k)

    if args.json:
        print(json.dumps({"query": query_text, "results": results}, ensure_ascii=False, indent=2))
        return 0 if results else 1

    print("DevBrain LightRAG Query")
    print(f"query: {query_text}")
    print("")
    if not results:
        print("No relationship results.")
        return 1

    for index, result in enumerate(results, start=1):
        print(f"{index}. {result['concept']} score={result['score']}")
        print(f"   title: {result['title']}")
        print(f"   reasons: {', '.join(result['reasons'])}")
        print("   canonical anchors:")
        for path in result["canonical_anchors"][:8]:
            print(f"   - {path}")
        print("   first-touch:")
        for path in result["first_touch"][:8]:
            print(f"   - {path}")
        print("   verification:")
        for target in result["verification"][:8]:
            print(f"   - {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
