#!/usr/bin/env python3
"""Acceptance checks for DevBrain LightRAG relationship retrieval."""

from __future__ import annotations

import argparse
from pathlib import Path

import ingest
import query as query_module
import update_status
from source_catalog import repo_root


SCENARIOS = [
    {
        "id": "simple_locate",
        "query": "Where is runtime API/WS origin resolution implemented on the frontend?",
        "expected_concept": None,
        "required_any": ["frontend/src/api/runtime.js"],
    },
    {
        "id": "telegram_mixed_contract",
        "query": "align Telegram frontend manager with backend contract",
        "expected_concept": "telegram_token_security_storage",
        "required_any": ["backend/app/api/v1/endpoints/admin_telegram.py", "frontend/src/components/TelegramManager.jsx"],
    },
    {
        "id": "registrar_payment_status_persistence",
        "query": "fix registrar payment status persistence ownership",
        "expected_concept": "registrar_payment_status",
        "required_any": ["backend/app/services/billing_service.py", "backend/app/models/payment.py", "frontend/src/api/registrarBatch.js"],
        "requires_relationship_packet": True,
    },
    {
        "id": "alembic_migration_ownership",
        "query": "add Alembic revision for existing SQLAlchemy model table missing",
        "expected_concept": "alembic_migration_ownership",
        "required_any": ["backend/alembic/versions/00XX_*.py", "backend/app/models"],
    },
    {
        "id": "notification_catalog_anti_noise",
        "query": "implement notification preferences mute snooze DND runtime policy",
        "expected_concept": "notification_catalog_anti_noise",
        "required_any": ["backend/app/services/notifications.py", "backend/app/schemas/notification.py", "frontend/src/api/services.js"],
    },
    {
        "id": "queue_identity_fairness",
        "query": "fix queue specialist id Doctor.id canonical ownership",
        "expected_concept": "queue_identity_fairness",
        "required_any": ["backend/app/services/queue_service.py", "backend/app/models/online_queue.py"],
    },
]


def result_paths(result: dict) -> set[str]:
    paths = set(result.get("canonical_anchors", []))
    paths.update(result.get("first_touch", []))
    paths.update(result.get("verification", []))
    for document in result.get("related_documents", []):
        paths.add(document.get("path", ""))
    return paths


def find_expected(results: list[dict], concept_id: str | None) -> dict | None:
    if concept_id is None:
        return results[0] if results else None
    for result in results:
        if result.get("concept") == concept_id:
            return result
    return None


def scenario_check(scenario: dict) -> tuple[str, list[str]]:
    results = query_module.search(scenario["query"], top_k=6)
    reasons: list[str] = []
    if not results:
        return "FAIL", ["no relationship results"]

    result = find_expected(results, scenario.get("expected_concept"))
    if result is None:
        return "FAIL", [f"expected concept missing: {scenario.get('expected_concept')}"]

    paths = result_paths(result)
    required = scenario.get("required_any", [])
    if required and not any(path in paths for path in required):
        return "FAIL", [f"none of required paths present: {', '.join(required)}"]

    if scenario.get("requires_relationship_packet"):
        packet_fields = [
            bool(result.get("canonical_anchors")),
            bool(result.get("first_touch")),
            bool(result.get("verification")),
        ]
        if sum(1 for item in packet_fields if item) < 3:
            return "FAIL", ["registrar case did not return complete anchors/first-touch/verification packet"]
        reasons.append("relationship packet includes canonical anchors, first-touch, and verification")

    if scenario["id"] == "simple_locate":
        if not any("frontend/src/api/runtime.js" in result_paths(item) for item in results):
            return "FAIL", ["simple locate did not surface frontend/src/api/runtime.js"]

    return "PASS", reasons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-status", action="store_true")
    args = parser.parse_args()

    root = repo_root()
    graph = ingest.build_graph(root=root)
    output = ingest.graph_path(root)
    ingest.write_graph(graph, output)

    print("DevBrain LightRAG Acceptance")
    print(f"graph: {output}")
    print(f"documents: {graph['document_count']}")
    print(f"concepts: {graph['concept_count']}")
    print(f"edges: {graph['edge_count']}")
    print("")

    if graph["edge_count"] <= 0:
        print("[FAIL] graph storage exists but graph is empty")
        return 1

    failures = 0
    for scenario in SCENARIOS:
        status, reasons = scenario_check(scenario)
        if status != "PASS":
            failures += 1
        print(f"[{status}] {scenario['id']}")
        print(f"  query: {scenario['query']}")
        for reason in reasons:
            print(f"  note: {reason}")
        print("")

    if failures:
        print(f"acceptance: FAIL ({failures} scenario(s))")
        return 1

    if args.update_status:
        update_status.update_status(
            root=root,
            commit=graph["commit"],
            document_count=graph["document_count"],
            concept_count=graph["concept_count"],
            edge_count=graph["edge_count"],
        )
        print("status updated: yes")

    print("acceptance: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
