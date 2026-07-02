# Wave 2C Duplicate Policy Contract

Date: 2026-03-07
Mode: analysis-first, docs-only

## Purpose

This document defines the target duplicate-policy contract for queue allocation.

It does not change current runtime checks. It defines which rule should become
canonical before allocator migration begins.

## Current Duplicate Rules

| Path | Identity key used | Active statuses used | Special cases |
|---|---|---|---|
| `queue_service.check_uniqueness()` | `phone` or `telegram_id` | `waiting`, `called` | `desk` and `morning_assignment` bypass checks |
| `join_queue_with_token()` | delegates to `check_uniqueness()` | `waiting`, `called` | Source-dependent bypass remains |
| `registrar_integration.create_queue_entries_batch()` | `patient_id` in queue/day | `waiting`, `called` | No phone/telegram-only key in that path |
| `QueueBatchRepository.find_existing_active_entry()` | `patient_id` + specialist/day | `waiting`, `called` | Read-side helper for batch path |
| `queue_session.get_or_create_session_id()` | `patient_id + queue_id + day` | `waiting`, `called`, `in_service` | Session reuse active set is broader |
| Legacy `online_queue.py` | normalized `phone` or `telegram_id` stored via settings keys | legacy queue states | Separate legacy semantics |

## Main Conflicts

### 1. Identity is not resolved the same way everywhere

Current runtime uses a mix of:

- `patient_id`
- `phone`
- `telegram_id`

That means "same patient" is not one uniformly defined thing.

### 2. Trusted-source bypass is too implicit

Today, `desk` and `morning_assignment` can bypass duplicate prevention entirely
in the main service helper.

That may be convenient for some flows, but it is too broad to remain the
canonical contract.

### 3. Active-status definition is inconsistent

Duplicate checks use a narrower status set than:

- session reuse
- queue position visibility
- the proposed active-entry contract

## Canonical Duplicate Rule

### Rule statement

There must be at most **one active queue entry per identity per queue/day**,
unless an explicit override contract is invoked.

### Canonical key

`identity_key + queue_id + queue_day`

Where `queue_day` is derived from `DailyQueue.day`.

## Canonical Identity Resolution

Identity should be resolved in this order:

1. `patient_id` if available
2. normalized `phone` if `patient_id` is not available
3. normalized `telegram_id` if neither `patient_id` nor phone is available
4. explicit external identity key only if a future join flow supports it

## Why `patient_id + queue_id + day` Is The Right Core Rule

It best matches the intended domain model:

- one patient may have multiple queue rows across different services/specialists
- a single queue row should represent one active claim in one concrete queue
- `DailyQueue` is already day-scoped, so queue ownership is local, not global

It also aligns better with:

- session reuse semantics
- registrar batch behavior
- visit-linked queue ownership

than the current phone-only or telegram-only rule.

## Source-Specific Exceptions

### Allowed by contract

- different queues on the same day may each receive an active entry for the
  same patient
- a multi-service QR or registrar flow may create multiple entries if they land
  in different `queue_id` values
- an explicit domain override may allow a duplicate in the same queue/day, but
  only with audit reason and explicit flag

### Not allowed by default

- source-based blanket bypass such as "desk always bypasses duplicates"
- implicit duplicate creation because a path lacks `patient_id`
- duplicate creation because one flow checks `phone` while another checks
  `patient_id`

## Proposed Duplicate Policy Owner

`QueueDomainService`

The domain service should own duplicate policy because:

- the rule depends on canonical active-entry semantics
- the rule depends on identity resolution
- the rule must run before ticket allocation
- the rule must share the same transaction boundary as allocation

Repositories may expose lookup helpers, but they should not own the final
duplicate decision.

## Compatibility Strategy

During migration, existing runtime paths can continue to behave as they do now,
but the contract target is:

- canonical duplicate identity: patient-first, contact fallback
- canonical active set: `waiting`, `called`, `in_service`, `diagnostics`
- explicit override instead of trusted-source blanket bypass

## Verdict

The duplicate-policy contract can be defined clearly enough for later migration.

Decision:

- canonical owner: `QueueDomainService`
- canonical key: `identity_key + queue_id + queue_day`
- preferred identity: `patient_id`
- fallback identity: normalized phone or telegram id
