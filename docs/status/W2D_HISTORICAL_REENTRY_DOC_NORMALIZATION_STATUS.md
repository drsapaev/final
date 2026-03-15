# W2D Historical Re-Entry Doc Normalization Status

Status: completed

What changed:

- `W2D_THREAD_HANDOFF.md`, `OPENHANDS_FIRST_10_TASKS.md`, and
  `AI_FACTORY_OPENHANDS_PRECHECK.md` now include explicit historical/current
  SSOT framing
- the status navigation index was updated to note that those re-entry docs are
  normalized historical records
- the next docs-only follow-up moved out of status navigation and toward
  broader docs-vs-code verification

Validation:

- normalized re-entry docs were re-checked for `Historical status` and
  `Current SSOT` markers
- `pytest tests/test_openapi_contract.py -q` -> `14 passed`
- the broader backend baseline remains `841 passed, 3 skipped`

Result:

- the current status stack now has a clear landing page plus normalized
  historical re-entry docs
- the remaining low-risk docs work sits outside the status stack
