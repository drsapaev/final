"""Machine-evaluate a chaos k6 run against the #2774 contract.

Reads a k6 JSON output (--out json=...) and enforces the contract
assertions from docs/runbooks/CHAOS_REAL_INJECTION_CONTRACT.md:

  a) fast-fail ceiling: no request exceeded --ceiling-ms (a hang is worse
     than a fast failure) — violations are contract FAILs;
  b) DB durability: the committed-write COUNT taken before the injection
     equals the count taken after recovery (--before-file +
     --after-count, S1 only);
  c) observations exist at all (a vacuous run FAILS — same anti-vacuous
     rule as load.yml).

Exit code 0 = PASS, 1 = FAIL. The CI step runs this with
continue-on-error so ALL scenarios evaluate and appear in the summary;
the final job verdict aggregates the per-step outcomes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _extract_points(data) -> list[dict]:
    """k6 --out json emits interleaved metric/point objects; collect points
    for the built-in http_req_duration metric (each carries 'value' ms)."""
    points: list[dict] = []
    if isinstance(data, dict):
        data = [data]
    for obj in data:
        if not isinstance(obj, dict):
            continue
        if obj.get("metric") == "http_req_duration" and isinstance(
            obj.get("data"), dict
        ):
            value = obj["data"].get("value")
            if isinstance(value, (int, float)):
                points.append({"value": value, **obj.get("data", {})})
    return points


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k6-json", required=True)
    parser.add_argument("--ceiling-ms", type=int, required=True)
    parser.add_argument("--scenario", default="chaos")
    parser.add_argument(
        "--before-file",
        help="file with the committed-write COUNT taken before injection "
        "(durability check runs only when provided)",
    )
    parser.add_argument(
        "--after-count",
        choices=["visits"],
        help="which table to re-count after recovery (S1: visits)",
    )
    args = parser.parse_args()

    failures: list[str] = []

    raw = Path(args.k6_json).read_text(encoding="utf-8", errors="replace")
    # k6 json output is line-delimited objects.
    objects = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            objects.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    points = _extract_points(objects)
    if not points:
        failures.append("vacuous run: no http_req_duration observations")
    else:
        violations = [p for p in points if p["value"] > args.ceiling_ms]
        if violations:
            worst = max(p["value"] for p in violations)
            failures.append(
                f"ceiling breaches: {len(violations)} request(s) over "
                f"{args.ceiling_ms}ms (worst {worst:.0f}ms) — hangs are "
                "contract violations"
            )
        else:
            print(
                f"  ceiling OK: {len(points)} requests, none over "
                f"{args.ceiling_ms}ms"
            )

    if args.before_file and args.after_count:
        before = Path(args.before_file).read_text().strip()
        # The durability re-count runs inside the app container env where
        # DATABASE_URL is set; reuse the app session module.
        from app.db.session import SessionLocal
        from sqlalchemy import text

        table = {"visits": "visits"}[args.after_count]
        db = SessionLocal()
        try:
            after = db.execute(
                text(f"SELECT COUNT(*) FROM {table}")
            ).scalar()
        finally:
            db.close()
        if str(after) != before:
            failures.append(
                f"durability: committed {args.after_count} count changed "
                f"({before} -> {after})"
            )
        else:
            print(f"  durability OK: {args.after_count} count == {before}")

    print(f"[{args.scenario}] {'PASS' if not failures else 'FAIL'}")
    for failure in failures:
        print(f"  ✗ {failure}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
