# Wave 2C QR Direct SQL Policy Coupling

Date: 2026-03-09
Mode: policy-coupling review
Scope: remaining QR direct-SQL allocator family

## Summary

The direct-SQL QR family is tightly coupled, but the coupling is now localized.
The high-risk surface is the mounted `full_update_online_entry()` endpoint rather
than the public QR join/complete family.

## Coupling Map

### Numbering

Severity: high

- direct SQL `MAX(number)+1` is used in mounted runtime
- numbering is not delegated through `QueueDomainService.allocate_ticket()`
- two separate mounted branches perform their own numbering decisions

### Duplicate policy

Severity: medium-high

- public QR join flow still benefits from legacy duplicate logic through boundary
- direct-SQL full-update additional-service creation does not run a canonical
  duplicate gate before creating independent entries
- this is not yet a proven runtime bug for characterized scenarios, but it is
  a migration blocker because duplicate ownership is embedded inside a monolith

### Active-entry semantics

Severity: medium

- `get_or_create_session_id(...)` only reuses sessions for:
  - `waiting`
  - `called`
  - `in_service`
- `diagnostics` is excluded from session reuse
- this matters for future contract alignment, especially if full-update behavior
  later depends on active-entry reuse by session

### QR time-window rules

Severity: low-medium

- QR token time-window enforcement is handled in join flow before allocation
- direct-SQL full-update path is post-join registrar/admin editing, so it does
  not itself own QR token window validation

### Queue fairness

Severity: high

- original QR consultation row preserves original `queue_time`
- additional-service independent rows use current local time
- this is a deliberate runtime split and must be preserved during migration-prep
- any future migration must keep this fairness distinction intact

### Token / session identity

Severity: medium

- public QR join flow is session-token-based and already characterized
- direct-SQL full-update path no longer depends on QR join session token, but
  still assigns `session_id` via queue-session helper
- this creates a mixed model: token identity at join time, session grouping at
  post-join service fan-out time

### Multi-specialist semantics

Severity: medium

- clinic-wide QR join uses `QueueProfile.id` selection and `QueueProfile.key`
  as resulting `queue_tag`
- this behavior is characterized and stable enough for prep, but must be kept
  explicit because it diverges from doctor-specialty assumptions

### Visit linkage

Severity: high

- full-update path creates/updates Visit and synchronizes patient/entry state in
  the same endpoint that also performs direct-SQL numbering
- this is the main reason a seam extraction is safer than a direct migration

### Source ownership

Severity: medium

- characterized QR join path uses `source="online"`
- direct-SQL full-update branches inherit `entry.source or "online"`
- migration must preserve this source inheritance exactly

## What This Means

The remaining QR direct-SQL problem is not primarily a numbering algorithm bug.
It is a coupling problem:

- direct numbering
- queue_time policy
- session_id assignment
- visit linkage
- patient sync

all coexist inside one mounted endpoint.

That makes the next safe step a seam-extraction prep slice, not a broad behavior
rewrite and not an immediate allocator redesign.
