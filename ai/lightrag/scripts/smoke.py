#!/usr/bin/env python3
"""Smoke check for the DevBrain LightRAG relationship graph."""

from __future__ import annotations

import ingest
import query as query_module
from source_catalog import repo_root


SMOKE_QUERY = "fix registrar payment status persistence ownership"


def main() -> int:
    root = repo_root()
    graph = ingest.build_graph(root=root)
    output = ingest.graph_path(root)
    ingest.write_graph(graph, output)

    print("DevBrain LightRAG smoke")
    print(f"graph: {output}")
    print(f"documents: {graph['document_count']}")
    print(f"concepts: {graph['concept_count']}")
    print(f"edges: {graph['edge_count']}")
    print(f"provider: {graph['provider']}")

    if graph["edge_count"] <= 0:
        print("smoke: FAIL graph is empty")
        return 1

    results = query_module.search(SMOKE_QUERY, top_k=3, root=root)
    print(f"query: {SMOKE_QUERY}")
    for index, result in enumerate(results, start=1):
        print(f"{index}. {result['concept']} score={result['score']}")

    if not results or results[0]["concept"] != "registrar_payment_status":
        print("smoke: FAIL registrar ownership concept was not top result")
        return 1

    print("smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
