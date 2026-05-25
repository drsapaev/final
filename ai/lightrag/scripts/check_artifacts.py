#!/usr/bin/env python3
"""Read-only integrity check for generated DevBrain LightRAG artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import export_artifacts
import ingest
from source_catalog import repo_root


REQUIRED_FILES = {
    "entities": "entities.jsonl",
    "relationships": "relationships.jsonl",
    "vector_store": "vector_store.jsonl",
    "doc_store": "doc_store.jsonl",
    "graph_store": "graph_store.json",
    "metadata": "metadata.json",
}


class CheckResult:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def fail(self, message: str) -> None:
        self.failures.append(message)
        print(f"FAIL: {message}")

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        print(f"WARN: {message}")

    def pass_(self, message: str) -> None:
        print(f"PASS: {message}")


def read_json(path: Path, result: CheckResult) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - surfaced in CLI output
        result.fail(f"cannot read JSON {path}: {exc}")
        return {}


def count_jsonl(path: Path, result: CheckResult) -> int:
    count = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    json.loads(line)
                except json.JSONDecodeError as exc:
                    result.fail(f"invalid JSONL in {path} at line {line_number}: {exc}")
                count += 1
    except OSError as exc:
        result.fail(f"cannot read JSONL {path}: {exc}")
    return count


def git_output(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def git_check_ignore(root: Path, path: Path) -> bool:
    completed = subprocess.run(
        ["git", "check-ignore", "-q", str(path)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def resolve_output_dir(root: Path, raw_output_dir: Path | None) -> Path:
    if raw_output_dir is None:
        return export_artifacts.artifact_dir(root)
    if raw_output_dir.is_absolute():
        return raw_output_dir
    return root / raw_output_dir


def check_required_files(output_dir: Path, result: CheckResult) -> dict[str, Path]:
    files = {name: output_dir / file_name for name, file_name in REQUIRED_FILES.items()}
    for name, path in files.items():
        if path.is_file():
            result.pass_(f"{name} artifact exists: {path}")
        else:
            result.fail(f"{name} artifact missing: {path}")
    return files


def check_counts(files: dict[str, Path], metadata: dict, graph_store: dict, result: CheckResult) -> None:
    counts = metadata.get("counts", {})
    jsonl_counts = {
        "entities": count_jsonl(files["entities"], result),
        "relationships": count_jsonl(files["relationships"], result),
        "vector_store": count_jsonl(files["vector_store"], result),
        "doc_store": count_jsonl(files["doc_store"], result),
    }

    for name, actual in jsonl_counts.items():
        expected = counts.get(name)
        if expected == actual:
            result.pass_(f"{name} count matches metadata: {actual}")
        else:
            result.fail(f"{name} count mismatch: metadata={expected} actual={actual}")

    graph_entity_count = graph_store.get("entity_count")
    graph_relationship_count = graph_store.get("relationship_count")
    if graph_entity_count == counts.get("entities"):
        result.pass_(f"graph_store entity_count matches metadata: {graph_entity_count}")
    else:
        result.fail(
            f"graph_store entity_count mismatch: graph_store={graph_entity_count} "
            f"metadata={counts.get('entities')}"
        )

    if graph_relationship_count == counts.get("relationships"):
        result.pass_(f"graph_store relationship_count matches metadata: {graph_relationship_count}")
    else:
        result.fail(
            f"graph_store relationship_count mismatch: graph_store={graph_relationship_count} "
            f"metadata={counts.get('relationships')}"
        )


def check_graph_alignment(root: Path, metadata: dict, graph_store: dict, result: CheckResult) -> None:
    graph_path = ingest.graph_path(root)
    if not graph_path.is_file():
        result.fail(f"source graph missing: {graph_path}")
        return

    graph = read_json(graph_path, result)
    graph_commit = graph.get("commit")
    metadata_commit = metadata.get("commit")
    graph_store_commit = graph_store.get("commit")

    if graph_commit == metadata_commit == graph_store_commit:
        result.pass_(f"graph, metadata, and graph_store commit match: {metadata_commit}")
    else:
        result.fail(
            "graph commit mismatch: "
            f"graph={graph_commit} metadata={metadata_commit} graph_store={graph_store_commit}"
        )

    concept_count = len(graph.get("concepts", {}))
    document_count = len(graph.get("documents", {}))
    edge_count = len(graph.get("edges", []))
    expected_entities = concept_count + document_count
    counts = metadata.get("counts", {})

    if counts.get("entities") == expected_entities:
        result.pass_(f"entity count matches source graph: {expected_entities}")
    else:
        result.fail(
            f"entity count does not match source graph: metadata={counts.get('entities')} "
            f"graph={expected_entities}"
        )

    if counts.get("relationships") == edge_count:
        result.pass_(f"relationship count matches source graph: {edge_count}")
    else:
        result.fail(
            f"relationship count does not match source graph: metadata={counts.get('relationships')} "
            f"graph={edge_count}"
        )


def check_freshness(root: Path, metadata: dict, result: CheckResult, warn_stale: bool) -> None:
    try:
        head = git_output(root, "rev-parse", "HEAD")
    except subprocess.CalledProcessError as exc:
        result.fail(f"git rev-parse HEAD failed: {exc}")
        return

    artifact_commit = metadata.get("commit")
    print(f"HEAD: {head}")
    print(f"artifact commit: {artifact_commit}")

    if artifact_commit == head:
        result.pass_("artifact metadata is fresh at HEAD")
        return

    message = f"STALE / NEEDS REEXPORT: artifact commit {artifact_commit} differs from HEAD {head}"
    if warn_stale:
        result.warn(message)
    else:
        result.fail(message)


def check_gitignored(root: Path, files: dict[str, Path], result: CheckResult) -> None:
    for name, path in files.items():
        if git_check_ignore(root, path):
            result.pass_(f"{name} artifact is gitignored")
        else:
            result.fail(f"{name} artifact is not gitignored: {path}")


def check_artifacts(output_dir: Path, warn_stale: bool) -> CheckResult:
    root = repo_root()
    result = CheckResult()
    print("DevBrain LightRAG artifact check")
    print(f"output: {output_dir}")

    files = check_required_files(output_dir, result)
    if result.failures:
        return result

    metadata = read_json(files["metadata"], result)
    graph_store = read_json(files["graph_store"], result)
    if result.failures:
        return result

    if metadata.get("schema") == "devbrain-lightrag-artifact-metadata-v1":
        result.pass_("metadata schema is devbrain-lightrag-artifact-metadata-v1")
    else:
        result.fail(f"unexpected metadata schema: {metadata.get('schema')}")

    if graph_store.get("schema") == "devbrain-lightrag-artifacts-v1":
        result.pass_("graph_store schema is devbrain-lightrag-artifacts-v1")
    else:
        result.fail(f"unexpected graph_store schema: {graph_store.get('schema')}")

    if metadata.get("vector_mode") == "local_sparse_term_hash":
        result.pass_("vector mode is local_sparse_term_hash")
    else:
        result.fail(f"unexpected vector mode: {metadata.get('vector_mode')}")

    check_counts(files, metadata, graph_store, result)
    check_graph_alignment(root, metadata, graph_store, result)
    check_freshness(root, metadata, result, warn_stale=warn_stale)
    check_gitignored(root, files, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--warn-stale",
        action="store_true",
        help="report stale artifact commits as WARN instead of FAIL",
    )
    args = parser.parse_args()

    root = repo_root()
    output_dir = resolve_output_dir(root, args.output_dir)
    result = check_artifacts(output_dir=output_dir, warn_stale=args.warn_stale)

    print("")
    print("Summary:")
    print(f"- failures: {len(result.failures)}")
    print(f"- warnings: {len(result.warnings)}")

    return 1 if result.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
