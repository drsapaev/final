# W1.5-T4 Security Slice A (Frontend Dependencies)

Date: 2026-03-06  
Task: Frontend dependency remediation (critical/high, minimal safe slice)  
Branch: `codex/w15-security-slice-a-frontend-deps`  
Status: `partial`

## Scope

- Frontend dependencies only.
- No build pipeline changes.
- No frontend business logic changes.

## Packages Updated

1. `axios`: `^1.13.2` -> `^1.13.6`
2. `react-router-dom`: `6.30.1` -> `^6.30.3`
3. `rollup` (dev): `3.29.4` -> `^3.30.0`
4. `jspdf-autotable`: `^5.0.2` -> `^5.0.7`

## Attempted But Not Applied

- Storybook patch train (`8.6.14` -> `8.6.17`) attempted, but blocked by peer-resolution conflict (`ERESOLVE`) in current dependency graph.
- `jspdf` critical fix requires major upgrade to `4.2.0` (flagged as semver-major by audit), intentionally deferred in this safe slice to avoid unverified breaking runtime changes in PDF generation.

## npm audit (before -> after)

- Before:
  - total: `16`
  - critical: `2`
  - high: `7`
  - moderate: `7`
- After:
  - total: `11`
  - critical: `1`
  - high: `3`
  - moderate: `7`

## Must-Run Commands and Results

```bash
cd frontend
npm audit
npm install
npm run build
npm run test:run
```

Results:

- `npm audit` -> vulnerabilities reduced but non-zero (expected for partial slice).
- `npm install` -> success.
- `npm run build` -> success.
- `npm run test:run` -> success (`24` files, `173` tests passed).

## Remaining High/Critical Items

1. `jspdf` critical/high advisories (`fixAvailable` points to major `4.2.0`).
2. Storybook advisories (`8.6.14` line; patch upgrade currently blocked by peer conflict).
3. Rollup high advisory remains in transitive `vite/vitest` sub-tree (`4.x` branch), not resolved by direct `rollup` pin alone.

## Recommended Next Safe Follow-up

1. Dedicated PR for `jspdf` major upgrade with focused PDF regression tests.
2. Separate dependency-resolution PR for Storybook 8.6.17 patch line.
3. Toolchain review slice for `vite`/`vitest` transitive rollup advisory closure.

