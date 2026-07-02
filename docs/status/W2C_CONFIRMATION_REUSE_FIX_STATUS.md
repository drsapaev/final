# Wave 2C Confirmation Reuse Fix Status

Date: 2026-05-05
Status: replacement-ready
Mode: runtime compatibility slice

## Replacement source

Old PR: #74, `fix: reuse active queue entries on confirmation`.
Replacement parent: #261, merged current-main confirmation contract docs.

## Preserved behavior

- Existing active queue entry is reused for a clear same-queue confirmation claim.
- Reuse does not allocate a new ticket number.
- Reuse preserves existing queue_time/fairness ordering.
- Ambiguous active ownership returns explicit `409` through the domain error path.
- Registrar confirmation now delegates queue assignment to `VisitConfirmationService`.

## Guardrails

- No frontend files changed.
- No RBAC files changed.
- No notification or realtime files changed.
- No migrations changed.
- Fresh allocation remains on the legacy creation branch when no active row exists.

## Focused proof targets

- `backend/tests/unit/test_confirmation_reuse_existing_entry.py`
- `backend/tests/characterization/test_confirmation_split_flow_characterization.py`
- Python syntax compilation for touched runtime/test files
- PR body gate and exact allowlist check