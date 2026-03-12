---
name: frontend-backend-contract-audit
description: Audit API and behavior parity between frontend clients and backend contracts in drsapaev/final. Use when checking payload drift, route drift, or parity regressions.
argument-hint: "[feature or API area]"
---

# frontend-backend-contract-audit

## Goal

- Verify that frontend expectations still match backend endpoints and contracts.

## Inputs

- A feature area, API namespace, or specific frontend service/client path.

## Constraints

- Avoid protected-domain behavior changes without explicit approval.
- Prefer evidence from generated contracts, tests, and live route definitions.

## Workflow

1. Read the frontend client or service code.
2. Compare it with backend endpoints, schemas, and generated OpenAPI artifacts.
3. Check parity tests or add targeted parity coverage if approved.
4. Record mismatches and keep changes narrow.

## Verification

- Run OpenAPI or parity checks relevant to the touched contract surface.

## Expected Artifacts

- Drift matrix, changed files, and verification command results.
