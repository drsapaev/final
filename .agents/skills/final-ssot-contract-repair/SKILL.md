---
name: final-ssot-contract-repair
description: Project-specific workflow for repairing frontend/backend contract leaks before adding BFF-lite endpoints. Use when React appears to make backend-owned decisions such as record_type branching, payment_status normalization, queue ordering, endpoint selection, role policy, EMR/lab/payment/Telegram action rules, or when a task says SSOT contract repair, frontend presentation-only, Registrar/Queue contract, or boundary cleanup.
---

# Final SSOT Contract Repair

Use this skill before adding screen/read-model endpoints when the frontend may be acting as a second source of truth.

This project is a clinic operations system. Backend services own business rules, role/security policy, audit, queue fairness, EMR locking/signing/amending, payment status transitions, lab finalization/version rules, Telegram security policy, and setup/activation transactions. React should render backend facts and submit commands; it should not decide workflow truth.

## Context Gate

Read the smallest relevant set before advising or editing:

- `AGENTS.md`
- `.ai-factory/ARCHITECTURE.md`
- `.ai-factory/DESCRIPTION.md`
- `.ai-factory/RULES.md`
- relevant frontend page/component/service/API client
- relevant backend endpoint, service, schema, model, and tests
- OpenAPI/contract tests if present

For Registrar/Queue work, first inspect `frontend/src/pages/RegistrarPanel.jsx`, `frontend/src/pages/QueueJoin.jsx`, queue/registrar backend endpoints, and queue/registrar tests.

## Repair Targets

Look for concrete frontend-owned decisions:

- Choosing backend command endpoints based on `record_type`, local status, or guessed object shape.
- Normalizing canonical statuses such as `payment_status`, queue status, visit status, lab status, or EMR status.
- Sorting or rewriting queue order, `queue_time`, queue numbers, fairness, or call state.
- Deciding whether payment, cancellation, signing, finalization, amendment, role action, or Telegram action is allowed.
- Mapping doctor/specialty/profile/department/service ownership where backend already has SSOT data.
- Falling back across legacy/current endpoints without a backend-provided compatibility contract.
- Combining multiple API responses into workflow state that drives commands.

Presentation labels, icons, colors, local form state, and obvious client-side required-field checks are allowed if they do not change canonical behavior.

## Workflow

1. Classify the task using `AGENTS.md` mode rules.
2. Identify the canonical backend owner: service, endpoint, schema, model, migration, contract test, or runbook.
3. Separate read concerns from command concerns.
4. Name the exact frontend leak and the backend fact or command contract that should replace it.
5. Prefer a narrow contract repair before introducing `/ui/*` endpoints.
6. Keep command behavior in existing domain services; add wrappers only when they delegate to those services.
7. Add or update tests that prove the frontend no longer decides backend-owned truth.

## Safe Patch Shape

For code changes, keep the first slice small:

- Backend: add a canonical field, `available_actions`, or unified command response only if backed by an existing service rule.
- Frontend: remove local branching/normalization and consume the canonical backend field.
- Tests: one backend contract/integration test plus one focused frontend adapter/component test when available.

Stop if canonical vs legacy ownership is unclear, command semantics are ambiguous, or the change would spread across unrelated domains.

## Output

Report:

- Contract leak found
- Canonical backend owner
- Proposed repair
- Files touched or proposed
- Tests/validation
- What remains presentation-only
- What must wait for BFF-lite
