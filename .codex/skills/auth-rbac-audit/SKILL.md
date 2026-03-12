---
name: auth-rbac-audit
description: Audit auth and RBAC behavior across frontend, backend, tests, and docs in drsapaev/final. Use when reviewing access-control integrity or role drift.
argument-hint: "[auth scope]"
---

# auth-rbac-audit

## Goal

- Detect auth and RBAC drift before it turns into unsafe behavior changes.

## Inputs

- A target flow, role, route, endpoint, or auth document set.

## Constraints

- Human review is mandatory for any resulting auth or RBAC edit.
- Do not rewrite login, token, or 2FA flows under this skill.
- Prefer findings and minimal drift fixes.

## Workflow

1. Compare backend role checks, frontend guards, route mappings, and docs.
2. Verify against RBAC-focused tests and role-routing checks.
3. Record mismatches, unsafe assumptions, and missing test coverage.
4. Only apply small, approved drift corrections.

## Verification

- Run `backend/test_role_routing.py`, the RBAC matrix test, and frontend route parity checks when relevant.

## Expected Artifacts

- RBAC findings, any approved drift fix, and explicit protected-domain notes.
