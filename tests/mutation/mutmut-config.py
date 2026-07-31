#!/usr/bin/env python3
"""
Mutation testing configuration for backend Python code.

Per Phase 4 requirements:
  - mutmut on critical backend modules
  - mutation score >= 80% on critical modules

Usage:
  cd backend
  mutmut run --paths-to-mutate app/services/appointments.py,app/services/payments.py,app/services/queue.py,app/services/emr.py
  mutmut results
  mutmut html

Installation:
  pip install mutmut

This file documents the mutation testing setup. Actual mutation runs
require mutmut installed and a running test suite.
"""

# === Mutation Testing Configuration ===
#
# Tool: mutmut (Python)
# Target modules (critical business logic):
#   - backend/app/services/appointments.py
#   - backend/app/services/payments.py
#   - backend/app/services/queue.py
#   - backend/app/services/emr.py
#
# Configuration (in backend/setup.cfg or backend/pyproject.toml):
#
#   [tool.mutmut]
#   paths_to_mutate = [
#     "app/services/appointments.py",
#     "app/services/payments.py",
#     "app/services/queue.py",
#     "app/services/emr.py",
#   ]
#   tests_dir = "tests/"
#   do_not_mutate = [
#     "__init__",
#     "__main__",
#   ]
#
# Run:
#   cd backend
#   mutmut run
#   mutmut results
#   mutmut html  # generates html report in html/
#
# Target: mutation score >= 80%
#   mutmut shows: "⠋ 123/456 MUTATED  🎉 78 SURVIVED  ⏰ 0 TIMEOUT  🤔 0 SKIPPED"
#   Score = (killed + timeout) / total = (123 + 0) / 456 = 27%
#   Need >= 80% — add tests to kill surviving mutants.

MUTATION_TARGETS = {
    "appointments": "app/services/appointments.py",
    "payments": "app/services/payments.py",
    "queue": "app/services/queue.py",
    "emr": "app/services/emr.py",
}

MUTATION_SCORE_THRESHOLD = 80  # percent

if __name__ == "__main__":
    print("Mutation testing configuration for backend.")
    print(f"Target modules: {list(MUTATION_TARGETS.keys())}")
    print(f"Score threshold: {MUTATION_SCORE_THRESHOLD}%")
    print()
    print("To run mutation tests:")
    print("  cd backend")
    print("  pip install mutmut")
    print("  mutmut run")
    print("  mutmut results")
    print("  mutmut html")
