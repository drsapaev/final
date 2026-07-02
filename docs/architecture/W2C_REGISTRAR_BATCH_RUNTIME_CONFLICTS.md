# Wave 2C Registrar Batch Runtime Conflicts

Date: 2026-05-05
Mode: docs-only replacement for stale PR #78

## Conflict Summary

Old PR #78 documented useful review questions, but several terms no longer match current `main` after replacement PR #264.

| Area | Old #78 wording | Current-main compatible wording |
| --- | --- | --- |
| Owner identity | `specialist_user_id` | doctor profile id, `doctors.id` |
| Input field | specialist/user ambiguity | `specialist_id` resolves to doctor profile |
| Queue bucket | `queue_tag=None` | first service `queue_tag` resolves `DailyQueue` |
| Claim key | patient + specialist + day | patient + doctor + day + resolved queue bucket |
| Same-doctor services | broad specialist-level wording | one row in the first service queue bucket unless redesigned |

## Runtime Risks To Watch

### 1. User id vs doctor id drift

If a new change compares a doctor profile id with a user account id, duplicate checks can miss existing rows or reject valid requests inconsistently.

### 2. Queue bucket drift

If a new change falls back to `queue_tag=None`, it can create or search the wrong `DailyQueue` bucket and break the contract characterized in #264.

### 3. Hidden service-level redesign

If same-doctor services begin creating multiple rows without an explicit migration, queue numbering, cashier handoff, and specialist panel behavior can drift.

### 4. Active-status ambiguity

If the duplicate guard only checks `waiting` and `called`, but docs claim `in_service` and `diagnostics` are blocked too, reviewers should mark the PR as contract drift until tests and docs agree.

## Safe Review Position

Treat this document as a compatibility review note, not runtime proof. Runtime changes still need focused tests against the mounted endpoint and repository/service helpers.
