#!/usr/bin/env python3
"""Query the local DevBrain LlamaIndex fallback index."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from ingest import build_index, index_path
from source_catalog import repo_root


TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]+")


SYNONYMS = {
    "ws": {"ws", "websocket", "wss", "wsorigin", "buildwsurl"},
    "api": {"api", "apibaseurl", "apiorigin", "buildapiurl"},
    "origin": {"origin", "apiorigin", "wsorigin", "runtime"},
    "runtime": {"runtime", "getruntimeresolution", "buildruntimesnapshot"},
    "frontend": {"frontend", "src"},
}


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def expanded_terms(query: str) -> list[str]:
    terms: set[str] = set()
    for token in tokenize(query):
        terms.add(token)
        terms.update(SYNONYMS.get(token, set()))
    return sorted(terms)


def load_index(root: Path, fallback_build: bool = True) -> dict:
    path = index_path(root)
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    if not fallback_build:
        raise FileNotFoundError(f"index not found: {path}")
    return build_index(root=root)


def score_document(document: dict, terms: list[str]) -> tuple[int, list[str]]:
    path_text = document["path"].lower()
    label_text = document.get("label", "").lower()
    symbol_text = " ".join(document.get("symbols", [])).lower()
    body_text = document.get("search_text", "").lower()
    score = 0
    reasons: list[str] = []

    for term in terms:
        term_score = 0
        if term in path_text:
            term_score += 12
        if term in label_text:
            term_score += 4
        if term in symbol_text:
            term_score += 8
        count = body_text.count(term)
        if count:
            term_score += min(count, 8)
        if term_score:
            score += term_score
            if len(reasons) < 8:
                reasons.append(term)

    if "frontend/src/api/runtime" in path_text:
        if {"runtime", "origin", "api"} & set(terms):
            score += 30
            reasons.append("runtime-api-origin-path")
    if "frontend/src/api/ws" in path_text and "ws" in terms:
        score += 15
        reasons.append("ws-api-path")

    return score, sorted(set(reasons))


def matching_lines(root: Path, relative_path: str, terms: list[str], limit: int = 4) -> list[str]:
    path = root / relative_path
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    snippets: list[str] = []
    lower_terms = [term.lower() for term in terms if len(term) >= 3]
    for index, line in enumerate(lines, start=1):
        lower = line.lower()
        if any(term in lower for term in lower_terms):
            snippets.append(f"{index}: {line.strip()[:180]}")
        if len(snippets) >= limit:
            break
    return snippets


def search(query: str, top_k: int = 8, root: Path | None = None) -> list[dict]:
    root = root or repo_root()
    index = load_index(root)
    terms = expanded_terms(query)
    results = []
    for document in index.get("documents", []):
        score, reasons = score_document(document, terms)
        if score <= 0:
            continue
        results.append(
            {
                "path": document["path"],
                "label": document.get("label", ""),
                "score": score,
                "reasons": reasons,
                "snippets": matching_lines(root, document["path"], terms),
            }
        )
    return sorted(results, key=lambda item: (-item["score"], item["path"]))[:top_k]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="+")
    parser.add_argument("--top-k", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    query_text = " ".join(args.query)
    results = search(query_text, top_k=args.top_k)

    if args.json:
        print(json.dumps({"query": query_text, "results": results}, ensure_ascii=False, indent=2))
        return 0 if results else 1

    print("DevBrain LlamaIndex Query")
    print(f"query: {query_text}")
    print("")
    if not results:
        print("No results.")
        return 1
    for index, result in enumerate(results, start=1):
        print(f"{index}. {result['path']}  score={result['score']}")
        print(f"   label: {result['label']}")
        print(f"   reasons: {', '.join(result['reasons'])}")
        for snippet in result["snippets"]:
            print(f"   {snippet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
