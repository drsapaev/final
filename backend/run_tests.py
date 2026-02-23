"""Run the canonical backend test suite."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    backend_dir = Path(__file__).resolve().parent
    cmd = [sys.executable, "-m", "pytest", "tests", *sys.argv[1:]]
    return subprocess.call(cmd, cwd=backend_dir)


if __name__ == "__main__":
    raise SystemExit(main())
