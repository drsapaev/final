# Legacy tests

These are one-off debugging scripts that accumulated at the repo root and at
`backend/` root during development. They are **not** collected by pytest
(`backend/pytest.ini` declares `testpaths = tests`) and should not be relied
on for CI signal.

## Layout

```
scripts/legacy_tests/
├── root/       ← files that were at repo root (57 files)
└── backend/    ← files that were at backend/ root (109 files)
```

## What to do with them

- **If you need a quick smoke check**, look here first — these scripts are
  usually more current than the formal test suite because they were written
  during debugging.
- **Do NOT add new files here.** New tests go into `backend/tests/unit/` or
  `backend/tests/integration/`.
- **Delete aggressively.** If a script here hasn't been touched in 6 months
  and doesn't reproduce a current bug, it's safe to delete.
- **Migrate useful ones.** If a script tests something useful, port it to a
  proper pytest test under `backend/tests/` and delete the original.

## Why this matters

Stray `test_*.py` files at the root pollute AI agent context windows, get
accidentally picked up by `python -m pytest` without the `testpaths`
directive, and create the impression that there's test coverage where there
isn't. The pre-commit hook `no-stray-root-tests` (see `.pre-commit-config.yaml`)
now blocks any new `test_*.py` from being committed at the root.
