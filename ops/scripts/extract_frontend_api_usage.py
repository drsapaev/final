#!/usr/bin/env python3
"""Extract frontend API call inventory for parity analysis."""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

LOGGER = logging.getLogger("frontend_api_inventory")

API_REQUEST_CALL_PATTERN = re.compile(r"\bapiRequest\s*\(", re.IGNORECASE)
AXIOS_METHOD_CALL_PATTERN = re.compile(
    r"\bapi\.(?P<method>get|post|put|patch|delete|options|head)\s*\(",
    re.IGNORECASE,
)
SINGLE_QUOTE_LITERAL = re.compile(r"^'([^'\\]|\\.)*'$")
DOUBLE_QUOTE_LITERAL = re.compile(r'^"([^"\\]|\\.)*"$')
BACKTICK_LITERAL = re.compile(r"^`([^`\\]|\\.)*`$")


@dataclass(slots=True)
class ApiCall:
    file: str
    line: int
    call: str
    method: str
    endpoint_expr: str
    endpoint_literal: str | None
    endpoint_kind: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build inventory of frontend API usage.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/reports/frontend_api_usage_inventory.json"),
        help="Where to save JSON inventory.",
    )
    parser.add_argument(
        "--frontend-root",
        type=Path,
        default=Path("frontend/src"),
        help="Frontend source root.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser.parse_args()


def _line_number(content: str, match_start: int) -> int:
    return content.count("\n", 0, match_start) + 1


def _extract_call_body(content: str, open_paren_idx: int) -> tuple[str | None, int | None]:
    depth = 0
    quote: str | None = None
    escaped = False
    body_chars: list[str] = []

    for index in range(open_paren_idx, len(content)):
        char = content[index]
        if index == open_paren_idx:
            depth = 1
            continue

        if quote is not None:
            body_chars.append(char)
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == quote:
                quote = None
            continue

        if char in {"'", '"', "`"}:
            quote = char
            body_chars.append(char)
            continue

        if char == "(":
            depth += 1
            body_chars.append(char)
            continue
        if char == ")":
            depth -= 1
            if depth == 0:
                return "".join(body_chars), index
            body_chars.append(char)
            continue

        body_chars.append(char)

    return None, None


def _split_top_level_arguments(args_body: str) -> list[str]:
    result: list[str] = []
    current: list[str] = []
    quote: str | None = None
    escaped = False
    paren = 0
    brace = 0
    bracket = 0

    for char in args_body:
        if quote is not None:
            current.append(char)
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == quote:
                quote = None
            continue

        if char in {"'", '"', "`"}:
            quote = char
            current.append(char)
            continue

        if char == "(":
            paren += 1
            current.append(char)
            continue
        if char == ")":
            paren = max(paren - 1, 0)
            current.append(char)
            continue
        if char == "{":
            brace += 1
            current.append(char)
            continue
        if char == "}":
            brace = max(brace - 1, 0)
            current.append(char)
            continue
        if char == "[":
            bracket += 1
            current.append(char)
            continue
        if char == "]":
            bracket = max(bracket - 1, 0)
            current.append(char)
            continue

        if char == "," and paren == 0 and brace == 0 and bracket == 0:
            result.append("".join(current).strip())
            current = []
            continue

        current.append(char)

    tail = "".join(current).strip()
    if tail:
        result.append(tail)
    return result


def _cleanup_endpoint_expr(endpoint_expr: str) -> str:
    normalized = endpoint_expr.strip()
    # Collapse whitespace-only newlines to keep expressions compact in report.
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _extract_literal(endpoint_expr: str) -> tuple[str | None, str]:
    expr = endpoint_expr.strip()

    if SINGLE_QUOTE_LITERAL.match(expr) or DOUBLE_QUOTE_LITERAL.match(expr):
        return expr[1:-1], "literal"

    if BACKTICK_LITERAL.match(expr):
        literal = expr[1:-1]
        if "${" in literal:
            return None, "template_dynamic"
        return literal, "template_literal"

    if expr.startswith("API_ENDPOINTS.") or expr.startswith("createEndpoints."):
        return None, "constant_ref"

    if "${" in expr or "+" in expr:
        return None, "dynamic_expr"

    return None, "unknown_expr"


def _collect_api_request_calls(
    content: str,
    file_path: Path,
) -> list[ApiCall]:
    calls: list[ApiCall] = []
    for match in API_REQUEST_CALL_PATTERN.finditer(content):
        call_body, closing_idx = _extract_call_body(content, match.end() - 1)
        if call_body is None or closing_idx is None:
            continue
        args = _split_top_level_arguments(call_body)
        if len(args) < 2:
            continue

        method_expr = args[0].strip()
        endpoint_expr = _cleanup_endpoint_expr(args[1])
        if len(method_expr) < 2:
            continue
        method = method_expr.strip("'\"`").upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
            continue

        endpoint_literal, endpoint_kind = _extract_literal(endpoint_expr)
        call = ApiCall(
            file=str(file_path.as_posix()),
            line=_line_number(content, match.start()),
            call="apiRequest",
            method=method,
            endpoint_expr=endpoint_expr,
            endpoint_literal=endpoint_literal,
            endpoint_kind=endpoint_kind,
        )
        calls.append(call)
    return calls


def _collect_api_method_calls(
    content: str,
    file_path: Path,
) -> list[ApiCall]:
    calls: list[ApiCall] = []
    for match in AXIOS_METHOD_CALL_PATTERN.finditer(content):
        method = match.group("method").upper()
        call_body, closing_idx = _extract_call_body(content, match.end() - 1)
        if call_body is None or closing_idx is None:
            continue
        args = _split_top_level_arguments(call_body)
        if not args:
            continue

        endpoint_expr = _cleanup_endpoint_expr(args[0])
        endpoint_literal, endpoint_kind = _extract_literal(endpoint_expr)
        call = ApiCall(
            file=str(file_path.as_posix()),
            line=_line_number(content, match.start()),
            call=f"api.{method.lower()}",
            method=method,
            endpoint_expr=endpoint_expr,
            endpoint_literal=endpoint_literal,
            endpoint_kind=endpoint_kind,
        )
        calls.append(call)
    return calls


def collect_frontend_calls(frontend_root: Path) -> list[ApiCall]:
    targets: list[Path] = []
    targets.extend(sorted((frontend_root / "api").glob("*.js")))
    targets.extend(sorted((frontend_root / "services").glob("*.js")))
    targets.extend(sorted((frontend_root / "hooks").rglob("*.js")))
    targets.extend(sorted((frontend_root / "hooks").rglob("*.jsx")))

    seen: set[str] = set()
    calls: list[ApiCall] = []
    for file_path in targets:
        normalized = str(file_path.resolve())
        if normalized in seen:
            continue
        seen.add(normalized)

        content = file_path.read_text(encoding="utf-8", errors="ignore")
        file_calls: list[ApiCall] = []
        file_calls.extend(_collect_api_request_calls(content, file_path))
        file_calls.extend(_collect_api_method_calls(content, file_path))

        file_calls.sort(key=lambda call: (call.line, call.call, call.method))
        calls.extend(file_calls)

        LOGGER.info("frontend_api_inventory.file_scanned file=%s calls=%d", file_path.as_posix(), len(file_calls))
        for call in file_calls:
            LOGGER.debug(
                "frontend_api_inventory.call file=%s line=%d method=%s endpoint=%s kind=%s",
                call.file,
                call.line,
                call.method,
                call.endpoint_expr,
                call.endpoint_kind,
            )

    calls.sort(key=lambda call: (call.file, call.line, call.method, call.call))
    return calls


def build_summary(calls: list[ApiCall]) -> dict:
    by_method = Counter(call.method for call in calls)
    by_kind = Counter(call.endpoint_kind for call in calls)
    by_file = Counter(call.file for call in calls)
    return {
        "total_calls": len(calls),
        "unique_files": len(by_file),
        "by_method": dict(sorted(by_method.items())),
        "by_endpoint_kind": dict(sorted(by_kind.items())),
        "top_files": [
            {"file": file_name, "calls": count}
            for file_name, count in by_file.most_common(20)
        ],
    }


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    LOGGER.info("frontend_api_inventory.start frontend_root=%s", args.frontend_root.as_posix())
    calls = collect_frontend_calls(args.frontend_root)
    summary = build_summary(calls)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frontend_root": args.frontend_root.as_posix(),
        "summary": summary,
        "calls": [asdict(call) for call in calls],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info(
        "frontend_api_inventory.done output=%s total_calls=%d unique_files=%d",
        args.output.as_posix(),
        summary["total_calls"],
        summary["unique_files"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
