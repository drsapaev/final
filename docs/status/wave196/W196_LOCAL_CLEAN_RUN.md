# W1.96 Local Clean Run

Date: 2026-03-06  
Branch: `codex/w196-ci-recovery`  
Status: `done`

## Clean Environment Preparation

### Frontend

```bash
cd frontend
rm -rf node_modules
npm ci
```

Result:
- `npm ci` completed successfully.
- Installed packages: `800`.
- Audit summary after install: `11` vulnerabilities (`1 critical`, `3 high`, `7 moderate`).

### Backend

```bash
cd backend
pip install -r requirements.txt
```

Result:
- install completed successfully.
- requirements-aligned packages were installed/updated in local environment (including `fastapi`, `aiohttp`, `weasyprint`, `protobuf`, `pillow`, `aiogram`, `python-multipart`).
- pip reported non-blocking resolver warnings for external tool deps (`mcp`) not part of app runtime gate.

## Mandatory Post-Install Test Check

### Frontend tests

```bash
cd frontend
npm run test:run
```

Result:
- exit code `0`
- `24` test files passed
- `173` tests passed

### Backend tests

```bash
cd backend
pytest -q
```

Result:
- exit code `0`
- `645 passed, 3 skipped`

