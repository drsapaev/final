# W1.96 Environment Diff (Local vs CI)

Date: 2026-03-06  
Branch: `codex/w196-ci-recovery`  
Status: `done`

## Local Versions

Commands:

```bash
node -v
npm -v
python -V
```

Results:
- Node: `v22.17.1`
- npm: `10.9.2`
- Python: `3.11.1`

## CI Target Versions (`ci-cd-unified.yml`)

From workflow env:
- `NODE_VERSION: 20`
- `PYTHON_VERSION: 3.11.10`

From latest failed unified run logs (`22748643145`, job `🎨 Frontend тесты`):
- Node runtime: `v20.20.0`
- npm runtime: `10.8.2`

## Mismatch Summary

1. Node mismatch: local `22.17.1` vs CI `20.20.0`.
2. npm mismatch: local `10.9.2` vs CI `10.8.2`.
3. Python patch mismatch: local `3.11.1` vs CI `3.11.10`.

## Impact

- Mismatch exists and can affect reproducibility.
- Despite mismatch, clean local run reproduced the previously failing area (`TwoFactorManager` tests) and passed after applying/finalizing the targeted mock fix.

