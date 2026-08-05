# ADR-0019 — Idempotent Webhook Responses Require Immutable Pre-Transition State

**Status:** Accepted
**Created:** 2026-08-03
**Discovered via:** PR #2675 (FOLLOWUP-9 discovery), Codex P1 review

## Summary

When an external provider (Payme, Click, Kaspi, or any JSON-RPC/REST
webhook caller) sends a request whose correct response depends on the
**state of an entity before the request was applied**, the system must
not derive that response from the entity's **current** (mutable) state.
The pre-transition state must either be persisted explicitly or be
recoverable from an immutable log. Using the mutable current state as
the source of truth breaks idempotency on retries.

## Context

### Discovery scenario (Payme CancelTransaction)

The Payme Merchant API specification
(`developer.help.paycom.uz/metody-merchant-api/tipy-dannykh`)
defines transaction states:

| state | meaning | initial state |
|------:|---------|---------------|
| 1 | created, awaiting confirmation | 0 |
| 2 | completed | 1 |
| -1 | cancelled (from state 1) | 1 |
| -2 | cancelled after completion (from state 2) | 2 |

The `CancelTransaction` JSON-RPC response must include a `state` field
whose value depends on the **previous** state of the transaction:
`-1` if it was in state 1, `-2` if it was in state 2.

### The bug

PR #2675 attempted to fix a spec violation where `CancelTransaction`
always returned `state: -1`, regardless of whether the transaction had
been performed (state 2) or not (state 1). The fix computed:

```python
was_completed = (existing_transaction.status == "completed")
state = -2 if was_completed else -1
```

This works for the **first** `CancelTransaction` call. But
`_apply_existing_payme_transaction_state()` mutates
`existing_transaction.status` (e.g. `completed → refunded`), so a
**retry** of the same `CancelTransaction` sees the post-mutation
status and returns `-1` instead of `-2`.

Reproduced locally:

```
1st CancelTransaction (Tx.status=completed) → response state=-2 ✅
   (Tx.status mutates to "refunded")
2nd CancelTransaction (retry, same Tx ID) → response state=-1 ❌
```

Payme sees two different `state` values for the same cancellation —
violating the JSON-RPC idempotency contract.

### Architectural audit

An audit of all potential sources of the pre-cancel state found **no
existing immutable source** in the system:

| Source | Immutable? | Contains pre-state? | Verdict |
|--------|-----------|---------------------|---------|
| `PaymentWebhook.raw_data` | ✅ append-only | ❌ only `{id, reason, amount}` in CancelTransaction request; Payme doesn't send state in requests | unusable |
| `AuditLog` | ✅ DB trigger | ❌ Payme webhook handler doesn't write to AuditLog | unusable as-is |
| `WebhookEvent` | ✅ | ❌ for outgoing webhooks, not incoming Payme JSON-RPC | unusable |
| `PaymentTransaction.provider_data` | ❌ mutable | ❌ overwritten on every webhook | unusable |
| `Payment.provider_data` | ❌ mutable | ❌ overwritten on every webhook | unusable |
| `PaymentWebhook` history (by `transaction_id`) | ✅ | ❌ existing-flow doesn't create PaymentWebhook rows; only new-flow does, and `transaction_id` is `order_id`, not `payme_transaction_id` | unusable |

## Decision

### Principle

> If a webhook response must be idempotent and depends on the state of
> an entity **before** the request was applied, that pre-transition
> state must either be:
>
> 1. **Persisted explicitly** in an immutable field/log, or
> 2. **Recoverable from an immutable journal** (e.g. audit log, event
>    log, append-only webhook history).
>
> Using the entity's **current mutable state** as the source of truth
> is insufficient — it will produce different responses on retries,
> violating idempotency.

### Scope of application

This principle applies to **all webhook integrations** in the system,
not only Payme:

- **Payme** (`CancelTransaction`, `PerformTransaction` responses
  include `state`)
- **Click** (response includes `error` and `error_note` that may
  depend on previous state)
- **Kaspi** (response includes `status` that may depend on previous
  state)
- Any future provider integration where the response spec depends on
  pre-transition state

### Implementation options for FOLLOWUP-12

When fixing PR #2675 / FOLLOWUP-9, the pre-cancel state must be
persisted via one of:

1. **AuditLog** (recommended) — use existing immutable infrastructure
   (DB trigger prevents UPDATE/DELETE). Write a `PAYME_TX_CANCELLED`
   event with `payload.pre_cancel_status` before mutating
   `Transaction.status`. On retry, query the latest AuditLog entry
   for the Tx to recover the pre-cancel state.

2. **Explicit immutable field** — add `PaymentTransaction.pre_cancel_status`
   column with a DB migration. Heaviest, most explicit.

3. **`provider_data` extension** (Codex proposal) — store
   `pre_cancel_status` in `PaymentTransaction.provider_data`. Mutable,
   but the first write is the source of truth. Lightest code, but
   extends the storage model semantically.

4. **PaymentWebhook in existing-flow** — start writing PaymentWebhook
   rows for Perform/Cancel on existing transactions, with `raw_data`
   containing the response. Most complex, changes many things.

Option 1 (AuditLog) is recommended because it uses existing immutable
infrastructure and doesn't extend the storage model.

## Consequences

### Positive

- Webhook responses become truly idempotent across retries.
- The principle generalises to Click, Kaspi, and future providers.
- Audit trail is enriched — every state transition is logged with
  pre/post values.

### Negative

- Additional DB write per CancelTransaction (AuditLog insert).
- Requires a read query on retry to recover the pre-cancel state.
- New behaviour in webhook handler (AuditLog writes) — needs testing
  for failure modes (what if AuditLog write fails?).

### Mitigations

- AuditLog write failure should not block the webhook response —
  log a warning and fall back to the current (mutable-state) behavior.
  This degrades idempotency but preserves availability.
- Add a regression test that reproduces the original Codex P1 scenario
  (two CancelTransaction calls, assert same `state` in both responses).

### Confirmed limitation of Strategy 2 (documented post-implementation)

Strategy 2 (fall back to mutable-state derivation on AuditLog failure)
was implemented in FOLLOWUP-12 (PR #2684) and refined in PR #2685
(terminal-status guard). **This is a mitigation, not a complete fix.**
When the first CancelTransaction's AuditLog INSERT fails, idempotency
for that specific Tx is **lost** — the system cannot recover the true
pre-cancel state, and all subsequent retries will return the wrong
`state` value (`-1` instead of `-2` for a completed-then-cancelled Tx).

**Scenario where idempotency is lost:**

```
1. CancelTransaction on Tx(status='completed')
   → AuditLog INSERT FAILS (DB error, connection drop, etc.)
   → Strategy 2: fall back to was_completed=(status=='completed')=True
   → response state=-2 (correct for this call)
   → Tx.status mutates to 'refunded', commits in a fresh transaction
   → AuditLog record is NOT persisted (INSERT failed)

2. Retry CancelTransaction on Tx(status='refunded')
   → AuditLog SELECT returns None (no record from step 1)
   → current_tx_status='refunded' (terminal)
   → terminal-status guard (PR #2685): return was_completed=False
     WITHOUT persisting (avoids recording wrong immutable data)
   → response state=-1 (WRONG — should be -2)

3. All future retries: same as step 2 — permanently state=-1
```

**Why this is acceptable (per architectural decision in Issue #2679):**

1. **Availability over perfect idempotency.** Strategy 1 (abort webhook
   on AuditLog failure) would make the webhook unavailable whenever
   AuditLog has a transient failure. Payme may interpret this as a
   merchant outage. Strategy 2 preserves availability at the cost of
   idempotency for the affected Tx.

2. **Terminal-status guard prevents making it worse.** PR #2685 added
   a guard that refuses to persist a terminal status as `pre_cancel_status`.
   Without this guard, step 2 above would persist `pre_cancel_status='refunded'`
   in an immutable AuditLog record, which would make the wrong answer
   permanent AND block any future recovery. The guard ensures that if
   AuditLog recovers later, a future retry could still (in theory) get
   the right answer — though in practice the pre-cancel state is already
   lost by step 1.

3. **AuditLog failure is rare.** AuditLog uses the same DB connection as
   the Tx.status mutation. If AuditLog INSERT fails, the Tx.status
   mutation is likely to fail too (same transaction). The scenario
   above requires AuditLog to fail WHILE Tx.status mutation succeeds —
   which only happens because Strategy 2 does a full `db.rollback()`
   on AuditLog failure, then re-applies the Tx.status mutation in a
   fresh transaction. This is a narrow window.

**When to revisit:** if production logs show that the "AuditLog INSERT
failed" warning appears with any frequency, or if Payme reports
idempotency violations in production, the project should reconsider
Strategy 1 (abort webhook) or Option C (dedicated immutable column
with trigger — see RFC #2679). The current implementation is a
conscious trade-off, not a complete solution.

**Do not treat this as fully solved.** Future developers reading this
ADR should understand: FOLLOWUP-12 + PR #2685 make the Payme
CancelTransaction response idempotent **in the common case** (AuditLog
INSERT succeeds). In the failure case (AuditLog INSERT fails),
idempotency degrades to Strategy 2's mutable-state derivation, which
is wrong on retry. This is the accepted limitation of the chosen
architecture.

## References

- PR #2675 (blocked, superseded) — discovery artifact with full analysis.
  Superseded by FOLLOWUP-12 (PR #2684) which implemented the same
  spec compliance fix with AuditLog-based pre-cancel state recovery,
  addressing the idempotency defect that PR #2675 could not solve.
- FOLLOWUP-9 — Payme `result.state` spec compliance (resolved by
  FOLLOWUP-12).
- FOLLOWUP-12 (PR #2684, merged) — implementation: AuditLog-based
  pre-cancel state persistence with Strategy 2 fallback.
- PR #2685 (merged) — terminal-status guard refinement: prevents
  persisting wrong immutable data when Strategy 2 fallback is triggered
  on a retry after AuditLog failure.
- RFC #2679 (Issue #2679) — architecture decision: Option A (AuditLog),
  inline `db.add()+db.flush()`, Strategy 2, no migrations, Payme-only.
- Payme spec: https://developer.help.paycom.uz/metody-merchant-api/tipy-dannykh
- Codex P1 review on PR #2675: "Preserve the original cancel state across retries"
