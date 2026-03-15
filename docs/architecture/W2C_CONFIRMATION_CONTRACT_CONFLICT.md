# Wave 2C Confirmation Contract Conflict

Date: 2026-03-07
Mode: analysis-first, docs-only

## Sources Compared

- `docs/architecture/W2C_QUEUE_NUMBERING_CONTRACT.md`
- `docs/architecture/W2C_DUPLICATE_POLICY_CONTRACT.md`
- `docs/architecture/W2C_ACTIVE_ENTRY_CONTRACT.md`
- `docs/architecture/W2C_CONFIRMATION_DESIGN_INTENT.md`
- `docs/architecture/W2C_CONFIRMATION_RUNTIME_BEHAVIOR.md`

## Main Question

Does the current confirmation flow conflict with the defined queue domain
contracts?

## Answer

Yes.

The current confirmation flow conflicts with:

- the duplicate-policy contract
- the numbering contract's pre-allocation rule
- the active-entry contract

## Contract-by-Contract Comparison

### Duplicate policy contract

Canonical rule in `W2C_DUPLICATE_POLICY_CONTRACT.md`:

- there must be at most one active queue entry per identity per queue/day
- duplicate policy should be checked before ticket allocation
- blanket source-based bypass is not the target contract

Current confirmation runtime:

- performs no canonical duplicate check before allocation
- may create a new `source="confirmation"` row even if the patient already has
  an active row in the same queue/day

Verdict:

- direct conflict

### Active entry contract

Canonical active statuses in `W2C_ACTIVE_ENTRY_CONTRACT.md` include:

- `waiting`
- `called`
- `in_service`
- `diagnostics`

The contract states that an existing active row should block a new allocation in
the same queue/day unless an explicit override contract applies.

Current confirmation runtime:

- allows allocation even when an active `waiting` row already exists
- has no explicit override flag or audit reason for that duplicate

Verdict:

- direct conflict

### Numbering contract

`W2C_QUEUE_NUMBERING_CONTRACT.md` requires:

- allocation remains monotonic, queue-local, day-scoped
- duplicate policy must be checked before issuing a new ticket

Current confirmation runtime still satisfies monotonic numbering, but it does
not satisfy the required pre-allocation duplicate-policy gate.

Verdict:

- partial conflict
- numbering sequence itself is not the issue
- allocation preconditions are the issue

## Nature Of The Conflict

The problem is not that confirmation assigns ticket numbers incorrectly.

The problem is that confirmation may allocate a fresh number for a queue claim
that, under the target domain contracts, should already be considered occupied
by an existing active row.

## Conflict Verdict

Current confirmation behavior is contract-incompatible in this specific case:

- same patient
- same queue/day
- existing active queue row
- confirmation still creates another active row

That makes the confirmation family a domain-drift case, not merely an
unmigrated caller.
