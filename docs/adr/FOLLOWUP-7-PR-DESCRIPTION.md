## Summary

- Remove the unused `_scrub_pii()` function and `MEDICAL_PII_KEYS` constant from `backend/app/core/sentry.py`. These were retained as backward-compatibility shims after PR #2654 (FOLLOWUP-1) migrated `before_send` to use `mask_pii()` from `pii_masker.py` as the single source of truth for backend PII scrubbing.
- Update three docs (`AGENTS.md`, `docs/runbooks/SENTRY_SETUP.md`, `docs/runbooks/STAGING_VALIDATION.md`) to correct stale claims about "all three lists MUST stay in sync" and replace the stale `_scrub_pii` example with a `sanitize_event` example.
- This is a cleanup PR. No runtime behaviour change. No business-logic change. No API change. No migration.

## Cyclic Execution Evidence

- Fresh main sync: branch created from current origin/main at commit `96e016cc` (PR #2680, FOLLOWUP-4)
- Clean workspace: inspected before edits; only `sentry.py` (backend cleanup) and three docs files changed
- Branch: `chore/followup-7-clean`
- Scope gate: allowed `backend/app/core/sentry.py`, `AGENTS.md`, `docs/runbooks/SENTRY_SETUP.md`, `docs/runbooks/STAGING_VALIDATION.md`, and this PR description file; denied `frontend/src/services/sentry.ts` (separate frontend concern), `backend/app/core/pii_masker.py` (single source of truth, unchanged), any backend runtime path outside `sentry.py`, migrations, generated output
- Red-check handling: fix any failed lint/test/gate in this same PR before merge; if PR Review Quality Gate fails, amend the PR body in place rather than pushing new commits

## Contract Impact

not applicable - documentation and dead-code cleanup only. No backend endpoint, websocket event, scheduled job, or frontend consumer contract changed. The removed symbols (`_scrub_pii`, `MEDICAL_PII_KEYS`) had zero callers in `backend/app/`, `backend/tests/`, and `ops/scripts/` (verified by exhaustive grep across all `.py/.ts/.tsx/.js/.jsx/.md/.yaml/.yml/.txt/.json/.sh` files excluding `node_modules` and `.git`). The active Sentry PII-scrubbing pipeline (`before_send` → `sanitize_event` → `mask_pii` from `pii_masker.py`) is unchanged.

## RBAC / Permissions

not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed. The PR touches only Sentry PII-scrubbing internals and documentation.

## Notification / Realtime

not applicable - no notification, websocket, chat, or realtime behavior changed. The PR does not touch any notification service, websocket handler, or event emitter.

## Frontend Resilience

not applicable - no user-facing panel or frontend data flow changed. The frontend has its own `MEDICAL_PII_KEYS` list in `frontend/src/services/sentry.ts` (50+ keys including auth tokens and payment fields per BS-57), which is intentionally separate from the backend list and is NOT modified by this PR. Frontend PII scrubbing behavior is unchanged.

## Scope Gate

- Allowed paths: `backend/app/core/sentry.py` (dead-code removal + module docstring update), `AGENTS.md` (correct stale claims), `docs/runbooks/SENTRY_SETUP.md` (replace `_scrub_pii` example with `sanitize_event` example, fix stale `.js` → `.ts` references, separate instructions for backend/frontend PII lists), `docs/runbooks/STAGING_VALIDATION.md` (correct line 435 to point to `PII_FIELD_PATTERNS` in `pii_masker.py`), `docs/adr/FOLLOWUP-7-PR-DESCRIPTION.md` (this PR description)
- Denied paths: `frontend/src/services/sentry.ts` (separate concern, untouched), `backend/app/core/pii_masker.py` (single source of truth for backend PII patterns, untouched), `VERIFICATION_AND_ROADMAP.md` (historical BS-57 taskspec entry, refers to frontend file, left as historical artifact), any backend runtime path outside `sentry.py`, migrations, generated output, test files
- Migration/docs/test impact: no migration; docs updated BEFORE code removal; no test changes (existing tests cover the active `sanitize_event`/`mask_pii` path)
- Rollback note: revert the 5 files in this PR; no DB state to roll back, no API contract to restore

## Validation

- Targeted tests or smoke run: `pytest tests/unit/test_sentry_sanitization.py` (51 tests), `tests/unit/test_pii_masker.py`, `tests/unit/test_frontend_backend_parity.py`, `tests/unit/test_frontend_backend_parity_gate.py`, `tests/unit/test_error_logging.py` (10 tests), `tests/unit/test_json_log_formatter.py`, `tests/unit/test_phi_safe_repr.py` (8 tests, FOLLOWUP-4 regression)
- Result: passed (161 tests in relevant groups, 0 failed). Note: these are relevant test groups, NOT a full backend test suite run; the full suite requires PostgreSQL and was not executed in this environment. CI will run the full backend suite - that is the authoritative check.
- Not checked: full backend integration tests with PostgreSQL (deferred to CI); end-to-end Sentry event submission (would require live SENTRY_DSN, out of scope for a dead-code cleanup PR)

---

## Why is this safe? (background for reviewers new to the FOLLOWUP series)

The Sentry PII-scrubbing pipeline in the backend has three layers, all of which already use `mask_pii()` from `backend/app/core/pii_masker.py` as the single source of truth:

```
Sentry SDK
   │ calls before_send(event, hint)
   ▼
before_send()           ← in sentry.py, unchanged by this PR
   │ calls sanitize_event(event)
   ▼
sanitize_event()        ← in sentry.py, unchanged by this PR
   │ calls mask_pii() for each event field
   ▼
mask_pii()              ← in pii_masker.py, unchanged by this PR
   │ uses PII_FIELD_PATTERNS (32 patterns)
   ▼
[REDACTED] / partial-masked value
```

`_scrub_pii()` and `MEDICAL_PII_KEYS` were legacy code retained after PR #2654 (FOLLOWUP-1) migrated `before_send` to use `mask_pii()`. The docstring on `_scrub_pii` explicitly said:

> `_scrub_pii` is retained for backward compatibility and any callers outside `before_send`. Removal is deferred to a separate cleanup PR after this security fix is verified in production.

That migration has been in production since 2026-08-01 (PR #2654 merged). No caller outside `before_send` ever materialised. This PR is the deferred cleanup.

## Pre-removal audit (all four checks done BEFORE code deletion)

### 1. Parity-gate tests verified

`backend/tests/unit/test_frontend_backend_parity.py` (99 lines) and `backend/tests/unit/test_frontend_backend_parity_gate.py` (90 lines) were read in full. Neither test references `_scrub_pii`, `MEDICAL_PII_KEYS`, or `PII_FIELD_PATTERNS`. They test API endpoint contracts and RBAC alignment only. Removing the dead symbols does not affect them.

### 2. Sentry runbooks audited

Found 3 docs with stale references to `_scrub_pii` / `MEDICAL_PII_KEYS`:

- `AGENTS.md:481-483` — claimed "All three layers use the same field list (MEDICAL_PII_KEYS)", which was already false (frontend has its own 50+ key list per BS-57, backend has `PII_FIELD_PATTERNS`).
- `docs/runbooks/SENTRY_SETUP.md:164, 177, 395-399` — contained a working example using `_scrub_pii(fake_event)` and instructions to "Add to MEDICAL_PII_KEYS in 3 places, all MUST stay in sync".
- `docs/runbooks/STAGING_VALIDATION.md:435` — same stale instruction.

All three docs were updated BEFORE the code was removed.

### 3. Runtime references searched

Exhaustive grep across all `.py/.ts/.tsx/.js/.jsx/.md/.yaml/.yml/.txt/.json/.sh` files (excluding `node_modules` and `.git`):

| Location | References found |
|---|---|
| `backend/app/` (excluding `sentry.py` itself) | 0 |
| `backend/tests/` | 0 |
| `ops/scripts/` | 0 |
| `frontend/` | own `MEDICAL_PII_KEYS` in `sentry.ts` — separate concern, untouched |

The only callers of `_scrub_pii` were the recursive self-calls inside its own definition.

### 4. Functional equivalence verified

`mask_pii()` (active) is a strict superset of `_scrub_pii()` (dead):

| Capability | `_scrub_pii` | `mask_pii` |
|---|---|---|
| dict/list recursion | yes | yes |
| None passthrough | yes | yes |
| String passthrough | returns unchanged | applies regex scrubbing for phone/email/passport/IIN (catches PII in free-text — `_scrub_pii` missed this) |
| Key-based redaction | 26 keys → `[REDACTED]` | 32 patterns (`PII_FIELD_PATTERNS` superset) with context-aware masking (full redact for identifiers/medical, partial mask for phone/email/name/birth_date to preserve debug structure) |

Conclusion: `mask_pii` is functionally superior. `_scrub_pii` was dead AND inferior. No behaviour change for any caller because there are no callers.

### Post-deletion verification (re-run after the change)

After the code was deleted, the same exhaustive grep was re-run:

| Symbol | Code references found | Doc references found |
|---|---|---|
| `_scrub_pii` | **0** (fully purged) | 0 |
| `MEDICAL_PII_KEYS` | 0 in backend code; 2 in frontend `sentry.ts` (active, separate concern) | 4 in updated docs (all referring to the frontend list, not backend); 1 in `VERIFICATION_AND_ROADMAP.md` (historical BS-57 taskspec, refers to frontend `sentry.ts`, left unchanged as a historical artifact) |

The public API of `sentry.py` was compared before/after:

| Symbol | Before | After | Used by |
|---|---|---|---|
| `MEDICAL_PII_KEYS` | yes | removed | (was unused) |
| `_scrub_pii` | yes | removed | (was unused) |
| `sanitize_event` | yes | yes | `test_sentry_sanitization.py` |
| `init_sentry` | yes | yes | `app/main.py` |
| `_scrub_context` | yes | yes | internal only |
| `_STANDARD_SENTRY_CONTEXTS` | yes | yes | internal only |
| `_STANDARD_CONTEXT_DIAGNOSTIC_KEYS` | yes | yes | internal only |
| `capture_exception` | yes | yes | (defined but no current callers — pre-existing, not this PR's scope) |
| `capture_message` | yes | yes | (defined but no current callers — pre-existing, not this PR's scope) |

## What changed

### Code (1 file)

`backend/app/core/sentry.py` — removed:
- `MEDICAL_PII_KEYS` constant (lines 24-37, 14 lines)
- `_scrub_pii()` function (lines 40-56, 17 lines)
- Stale comment claiming "Same field-name list as frontend" (lines 22-23)

Module docstring updated to point to `pii_masker.py` as the single source of truth for backend PII patterns, and to acknowledge that frontend has its own list (separate concern per BS-57).

### Documentation (3 files, updated BEFORE code removal)

- `AGENTS.md` — corrected the false "all three lists MUST stay in sync" claim; replaced stale `.js` reference with `.ts` (frontend migrated to TypeScript in commit `f2c868a1`).
- `docs/runbooks/SENTRY_SETUP.md` — updated Section 1 (Architecture), Section 4 (PII scrubbing verification — replaced `_scrub_pii` example with `sanitize_event` example, updated expected output to reflect partial masking), Section 10 (Adding new PII fields — separate instructions for backend and frontend), Section 11 (Related files `.js` → `.ts`).
- `docs/runbooks/STAGING_VALIDATION.md` — corrected line 435 to point to `PII_FIELD_PATTERNS` in `pii_masker.py`.

The `sanitize_event` example in SENTRY_SETUP.md was verified to produce the documented output by running it against the actual code: `first_name: "Akmal"` → `"A."`, `phone: "+998901234567"` → `"+998901•••567"`, `iin` and `diagnosis` → `"[REDACTED]"`.

## What is NOT changed (intentionally)

- `frontend/src/services/sentry.ts` — has its own active `MEDICAL_PII_KEYS` list (50+ keys, BS-57). Separate concern, frontend scrubs more aggressively (auth tokens, payment fields) because the browser surface is wider. Touching it would expand scope beyond FOLLOWUP-7.
- `backend/app/core/pii_masker.py` — unchanged. `PII_FIELD_PATTERNS` remains the single source of truth for backend PII patterns.
- `sanitize_event`, `_scrub_context`, `_STANDARD_SENTRY_CONTEXTS`, `_STANDARD_CONTEXT_DIAGNOSTIC_KEYS`, `init_sentry`, `capture_exception`, `capture_message` — all unchanged.
- `before_send` callback — unchanged. Still delegates to `sanitize_event` which delegates to `mask_pii`.
- `VERIFICATION_AND_ROADMAP.md:352` — historical BS-57 taskspec entry that mentions `MEDICAL_PII_KEYS` in `services/sentry.ts` (frontend). Left unchanged: it refers to the frontend file, which still has that constant, and it is a historical roadmap artifact, not a live instruction.
- No DB migrations, no API changes, no test changes.

## Invariants verified

1. `ALLOWED_PAYMENT_TRANSITIONS` — single source of truth (FOLLOWUP-6). Not affected by this PR.
2. Lock ordering (FOLLOWUP-8, FOLLOWUP-10) — not affected.
3. Defensive webhook guards — not affected (still in place per #2674).
4. External provider response idempotency — not affected (FOLLOWUP-12 is a separate RFC, not yet implemented).
5. Architecture over local fixes — this PR is a cleanup, not a fix.
6. No mutable state as source of historical truth — not affected.

## Risk assessment

- **Runtime behaviour change:** NONE (no callers existed)
- **Test regression:** NONE (relevant test groups pass)
- **Documentation accuracy:** IMPROVED (3 stale claims corrected)
- **Frontend PII scrubbing:** UNCHANGED (separate file, separate concern)
- **Backend PII scrubbing:** UNCHANGED (`mask_pii` is the active path, was active before this PR, remains active after)

## Scope

5 files changed, 337 insertions(+), 68 deletions(-).
No business-logic changes, no migration, no API changes.

## References

- FOLLOWUP-7 (this PR)
- FOLLOWUP-1 (PR #2654) — introduced `sanitize_event`, made `_scrub_pii` dead code
- BS-57 (already merged in PR #2488) — extended frontend `MEDICAL_PII_KEYS` independently of backend, creating the parity drift that this PR's documentation updates finally acknowledge
- ADR-0019 — not directly related (webhook idempotency, not PII), but referenced for architectural discipline
