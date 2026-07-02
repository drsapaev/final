# Wave 2C High-Risk Migration Order

Date: 2026-03-07
Mode: analysis-first, docs-only

## Recommended Order

### 1. Confirmation split-flow characterization pass

- Why first:
  - closest family to boundary migration
  - no direct SQL allocator
  - no `OnlineDay` dependency
  - uses shared `queue_service` helpers already
- Prerequisites:
  - add replay and multi-queue characterization tests
  - lock down `doctor.id` / `user.id` fallback behavior
- Tests required:
  - new confirmation allocator characterization tests
  - existing `test_visit_confirmation_api.py`
  - existing `test_visit_confirmation_service.py`
- Boundary migration possible before logic migration:
  - yes, if characterization first proves no replay drift

### 2. Registrar batch-only preparation pass

- Why second:
  - modern batch path already delegates final creation to `queue_service`
  - operator-visible behavior is already partially tested
- Prerequisites:
  - explicitly split batch path from wizard and same-day legacy desk path
  - add concurrency and identity-normalization characterization
- Tests required:
  - extend `test_queue_batch_api.py`
  - add batch concurrency characterization
- Boundary migration possible before logic migration:
  - yes, for the batch-only subfamily

### 3. Registrar wizard family review and family split

- Why third:
  - shares domain area with registrar batch, but still owns split allocation and
    legacy-style assumptions
- Prerequisites:
  - isolate `_create_queue_entries()` from `_assign_queue_numbers_on_confirmation()`
  - characterize wizard cart and confirmation flows separately
- Tests required:
  - wizard-specific characterization for queue creation branches
- Boundary migration possible before logic migration:
  - only after the family is split into smaller units

### 4. Unmounted and duplicate service ownership decision

- Why fourth:
  - runtime ownership should be clarified before touching more live allocators
- Prerequisites:
  - confirm which helpers are mounted, shadowed, or stale
- Tests required:
  - route-reachability or import ownership checks
- Boundary migration possible before logic migration:
  - cleanup may be possible without allocator migration, but only after owner is clear

### 5. Force majeure characterization expansion

- Why fifth:
  - still uses a separate allocator, but current behavior can be locked down more
    tightly before any redesign
- Prerequisites:
  - characterize duplicate-tomorrow behavior
  - characterize concurrent transfers
- Tests required:
  - force-majeure concurrency and duplicate tests
- Boundary migration possible before logic migration:
  - not safely; transfer transaction semantics need to be explicit first

### 6. `qr_queue.py` direct SQL family preparation

- Why sixth:
  - highest-risk SSOT family outside legacy track
- Prerequisites:
  - map mutation phases inside `full_update_online_entry()`
  - separate patient, visit, and queue-entry subflows
  - add direct-SQL concurrency characterization
- Tests required:
  - dedicated characterization around `full_update_online_entry()`
- Boundary migration possible before logic migration:
  - no

### 7. `OnlineDay` legacy track

- Why last:
  - separate counter world
  - separate duplicate memory
  - separate day-open semantics
- Prerequisites:
  - human decision whether to retire or preserve
- Tests required:
  - legacy-specific compatibility suite
- Boundary migration possible before logic migration:
  - no

## Order Summary

Do not migrate in this order:

- direct SQL first
- force majeure first
- `OnlineDay` first

Do migrate in this order:

- characterization-first families that already call `queue_service`
- then narrowed registrar subfamilies
- only then transaction-heavy or legacy families
