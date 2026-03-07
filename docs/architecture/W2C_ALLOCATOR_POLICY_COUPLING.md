# Wave 2C Allocator Policy Coupling

Date: 2026-03-07
Mode: analysis-first, docs-only

## Coupling Scale

- `None`: no meaningful coupling observed
- `Low`: coupling exists but is narrow and mostly read-only
- `Medium`: migration could drift policy if not characterized
- `High`: allocator family is tightly coupled to that policy area

## Family Coupling Matrix

| Family | Numbering | Duplicate policy | Fairness ordering | QR window rules | Visit lifecycle | Registrar workflow | Doctor workflow | Payment coupling | Legacy `OnlineDay` semantics | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| Registrar batch and wizard flows | High | High | Medium | None | High | High | Medium | Low | Medium | Batch path already uses `queue_service`, but wizard and same-day legacy paths still own allocation details and specialist normalization |
| Confirmation split-flow | High | Medium | Medium | None | High | Medium | Low | None | Low | Confirmation allocates queue numbers during visit status change and still splits number lookup from row creation |
| `qr_queue.py` direct SQL allocator branches | High | High | High | High | High | High | High | High | Low | One handler owns queue edits, patient creation, visit updates, invoice checks, and queue branching |
| Force majeure allocator paths | High | Medium | High | None | Medium | Low | Medium | Low | None | Transfer path resets `queue_time`, changes `priority`, and cancels old entries while notifying patients |
| `OnlineDay` and other legacy allocator paths | High | High | High | High | Low | Medium | Low | None | High | Legacy path uses independent `last_ticket` counters and separate identity memory |
| Unmounted or duplicate queue entry services | Medium | Medium | Medium | Medium | Low | Low | Low | None | Medium | Risk is mainly ownership ambiguity and drift between mounted and duplicate helper paths |

## Observations

### Registrar family

- `create_queue_entries_batch()` is closest to boundary migration because it
  already delegates the final row creation to `queue_service`.
- The broader family remains high-risk because the same family still includes:
  - legacy `start_number + current_count`
  - wizard split allocation
  - confirmation-style manual row creation in wizard helpers

### Confirmation family

- The allocator itself is not direct SQL, but it is coupled to visit lifecycle.
- Any migration mistake can change:
  - when queue rows are created
  - how same-day visits flip from `confirmed` to `open`
  - how printable ticket payloads are populated

### `qr_queue.py` family

- This is the most policy-coupled family in the current queue domain.
- Numbering, duplicate behavior, fairness, QR semantics, patient creation,
  visit creation, and payment-sensitive `all_free` behavior all converge in one
  mutation-heavy handler.

### Force majeure family

- The path is not legacy, but it behaves like a domain exception.
- It changes numbering and fairness together because it:
  - allocates new numbers
  - resets `queue_time`
  - sets transfer priority
  - cancels original entries

### Legacy `OnlineDay` family

- This family is not a thin wrapper over the new SSOT path.
- It is a different counter model with:
  - separate `last_ticket`
  - separate duplicate memory by phone or Telegram
  - separate day-open rules

### Unmounted or duplicate services

- This family is not dangerous because of runtime traffic volume.
- It is dangerous because refactoring it blindly can create more ownership drift
  or make the team think a dead path is authoritative when it is not.
