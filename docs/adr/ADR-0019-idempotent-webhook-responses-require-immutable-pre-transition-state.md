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

## References

- PR #2675 (blocked) — discovery artifact with full analysis
- FOLLOWUP-9 — Payme `result.state` spec compliance (blocked on this ADR)
- FOLLOWUP-12 — implementation task to persist pre-cancel state
- Payme spec: https://developer.help.paycom.uz/metody-merchant-api/tipy-dannykh
- Codex P1 review on PR #2675: "Preserve the original cancel state across retries"
