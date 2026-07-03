#!/usr/bin/env python3
"""
Standalone MCP server: synthetic patient/visit data generator for IDEs.

Lets Claude/Cursor/Codex generate synthetic patients on demand:

    User: "Generate 50 synthetic cardiology patients for staging"
    Agent: calls mcp tool 'generate_patients' with count=50, specialty=cardiology
    Server: spawns `python -m app.synthetic_seed ...` in backend/
    Returns: summary JSON

This is a stdlib-only MCP server (no `mcp` package dependency). Implements
the minimum JSON-RPC 2.0 subset that MCP needs: initialize, tools/list,
tools/call. Works on any Python 3.11+ checkout.

Registration (in .mcp.json):
    "synthetic-data": {
        "command": "python",
        "args": ["mcp-servers/synthetic_data_server.py"],
        "env": {
            "DATABASE_URL": "${DATABASE_URL}",
            "BACKEND_DIR": "${workspaceFolder}/backend"
        }
    }

Run manually to test:
    echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python mcp-servers/synthetic_data_server.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "clinic-synthetic-data"
SERVER_VERSION = "1.0.0"

# Backend dir — where `python -m app.synthetic_seed` runs from.
BACKEND_DIR = Path(os.environ.get("BACKEND_DIR", Path(__file__).resolve().parent.parent / "backend"))

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "generate_patients",
        "description": (
            "Generate synthetic patients for the staging/dev database. "
            "Records are tagged with SYNTHETIC- prefix in last_name for easy cleanup. "
            "Refuses to run against production-looking database names. "
            "Use this when you need test data for: load testing, demo recordings, "
            "AI/ML training data, UI screenshots that should not contain real PII."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "default": 100, "minimum": 1, "maximum": 100000},
                "database_url": {
                    "type": "string",
                    "description": "PostgreSQL URL. If omitted, uses $DATABASE_URL env var. Must contain 'staging'/'dev'/'test'/'synthetic'/'sandbox' in DB name.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "generate_visits",
        "description": (
            "Generate synthetic visits (appointments) for existing synthetic patients. "
            "Complaints and ICD-10 codes are specialty-specific (cardiology, dermatology, dental). "
            "Visits are distributed across the last 90 days with realistic statuses."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "default": 500, "minimum": 1, "maximum": 100000},
                "specialty": {"type": "string", "enum": ["cardiology", "dermatology", "dental"], "default": "cardiology"},
                "database_url": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "cleanup_synthetic",
        "description": (
            "Delete all synthetic records (patients + their visits) from the database. "
            "Safe to run on any DB — only deletes records with SYNTHETIC- prefix in last_name. "
            "Use after a demo or test run to leave the DB clean."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "database_url": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "list_synthetic",
        "description": (
            "Count synthetic records currently in the database. "
            "Returns counts of synthetic patients and visits. Read-only."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "database_url": {"type": "string"},
            },
            "required": [],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations — shell out to backend/app/synthetic_seed.py
# ---------------------------------------------------------------------------

def _run_seed_cmd(args: list[str], database_url: str | None) -> dict[str, Any]:
    """Run synthetic_seed.py with the given args. Returns parsed result dict."""
    if not BACKEND_DIR.exists():
        return {"error": f"Backend dir not found: {BACKEND_DIR}"}

    cmd = [sys.executable, "-m", "app.synthetic_seed"] + args
    if database_url:
        env = {**os.environ, "DATABASE_URL": database_url}
    else:
        env = os.environ

    try:
        result = subprocess.run(
            cmd,
            cwd=str(BACKEND_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min max for bulk inserts
        )
    except subprocess.TimeoutExpired:
        return {"error": "Synthetic seed timed out after 600s"}

    return {
        "returncode": result.returncode,
        "stdout": result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
        "stderr": result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr,
    }


def tool_generate_patients(args: dict[str, Any]) -> dict[str, Any]:
    count = int(args.get("count", 100))
    db_url = args.get("database_url") or os.environ.get("DATABASE_URL")
    if not db_url:
        return {"error": "DATABASE_URL not provided. Set it in .mcp.json env or pass --database-url."}

    result = _run_seed_cmd(
        ["--count-patients", str(count), "--count-visits", "0", "--confirm-synthetic-seed"],
        db_url,
    )
    result["action"] = "generate_patients"
    result["count"] = count
    return result


def tool_generate_visits(args: dict[str, Any]) -> dict[str, Any]:
    count = int(args.get("count", 500))
    specialty = args.get("specialty", "cardiology")
    db_url = args.get("database_url") or os.environ.get("DATABASE_URL")
    if not db_url:
        return {"error": "DATABASE_URL not provided."}

    result = _run_seed_cmd(
        ["--count-patients", "0", "--count-visits", str(count), "--specialty", specialty, "--confirm-synthetic-seed"],
        db_url,
    )
    result["action"] = "generate_visits"
    result["count"] = count
    result["specialty"] = specialty
    return result


def tool_cleanup_synthetic(args: dict[str, Any]) -> dict[str, Any]:
    db_url = args.get("database_url") or os.environ.get("DATABASE_URL")
    if not db_url:
        return {"error": "DATABASE_URL not provided."}

    result = _run_seed_cmd(
        ["--cleanup-only", "--confirm-synthetic-seed"],
        db_url,
    )
    result["action"] = "cleanup_synthetic"
    return result


def tool_list_synthetic(args: dict[str, Any]) -> dict[str, Any]:
    """Count synthetic records. Uses psql via subprocess — no Python ORM needed."""
    db_url = args.get("database_url") or os.environ.get("DATABASE_URL")
    if not db_url:
        return {"error": "DATABASE_URL not provided."}

    # Use sqlalchemy if available (likely is, since backend is installed)
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(db_url)
        with engine.connect() as conn:
            patients = conn.execute(text("SELECT COUNT(*) FROM patients WHERE last_name LIKE 'SYNTHETIC-%'")).scalar() or 0
            visits = conn.execute(text("""
                SELECT COUNT(*) FROM visits WHERE patient_id IN (
                    SELECT id FROM patients WHERE last_name LIKE 'SYNTHETIC-%'
                )
            """)).scalar() or 0
        return {"synthetic_patients": patients, "synthetic_visits": visits}
    except Exception as e:
        return {"error": f"DB query failed: {e}", "hint": "Ensure backend deps are installed and DATABASE_URL is reachable."}


TOOL_HANDLERS = {
    "generate_patients": tool_generate_patients,
    "generate_visits": tool_generate_visits,
    "cleanup_synthetic": tool_cleanup_synthetic,
    "list_synthetic": tool_list_synthetic,
}


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 over stdio — minimal MCP server
# ---------------------------------------------------------------------------

def send(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def handle_request(req: dict[str, Any]) -> dict[str, Any] | None:
    """Process one JSON-RPC request. Returns response dict, or None for notifications."""
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }

    if method == "notifications/initialized":
        return None  # notification — no response

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }
        try:
            result = handler(tool_args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}],
                    "isError": bool(result.get("error") or result.get("returncode", 0) != 0),
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": f"Tool execution failed: {e}"},
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> int:
    """Read JSON-RPC messages line-by-line from stdin, write responses to stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {e}"}})
            continue

        response = handle_request(req)
        if response is not None:  # None = notification, no response
            send(response)

    return 0


if __name__ == "__main__":
    sys.exit(main())
