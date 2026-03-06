# Wave 2A Refactor Options

Date: 2026-03-06  
Purpose: propose reviewable options before touching queue/payment/lifecycle slices.

## `W2A-SR-011` `services.py` queue-adjacent metadata

### Option A: Partial Service Extraction

- Move only `get_queue_groups`, `resolve_service_endpoint`, and `get_service_code_mappings` to the existing `ServicesApiService`.
- Keep route paths and response models unchanged.
- Good when the goal is only router-boundary cleanup for read-only metadata.

### Option B: Dedicated Queue Metadata Service

- Extract queue-group and service-code mapping concerns into a dedicated read-model service.
- Keep catalog CRUD in `ServicesApiService`.
- Better if queue taxonomy will evolve independently from service catalog CRUD.

### Option C: Defer to Wave 2C

- Treat queue metadata as part of queue lifecycle architecture because it defines registrar tabs and routing semantics.
- Best when product owners expect queue taxonomy changes together with queue lifecycle work.

## `W2A-SR-040` `visits.py` queue-coupled write handlers

### Option A: Partial Service Delegation to Existing `VisitsApiService`

- Reuse the already-written `set_status` / `reschedule_*` service methods.
- Add targeted lifecycle regression tests before switching the router.
- Good only if human review accepts the current queue status semantics as canonical.

### Option B: Dedicated `VisitLifecycleService`

- Split visit lifecycle (`status`, `started_at`, `finished_at`, reschedule rules) from generic visit CRUD.
- Move queue-entry updates behind a dedicated orchestration boundary.
- Better when visit lifecycle needs explicit invariants and auditability.

### Option C: Defer to Wave 2C

- Treat visit status + queue-entry status as queue lifecycle work, not Wave 2A cleanup.
- Best when queue semantics are still under review or likely to change.

## `W2A-SR-020` / `W2A-SR-030` / `W2A-SR-050` / `W2A-SR-070` queue-heavy orchestration

### Option A: Extract Read Models First

- Move read-only dashboard/query handlers first.
- Leave mutating queue transitions in routers until queue invariants are documented.

### Option B: Introduce Dedicated Queue Domain Services

- `DepartmentProvisioningService`
- `DoctorQueueLifecycleService`
- `RegistrarQueueService`
- `QueueLifecycleService`

This gives cleaner transaction boundaries, but it is architectural work, not a safe cleanup slice.

### Option C: Defer to Wave 2C

- Use Wave 2C to redesign queue lifecycle boundaries explicitly.
- Recommended if queue status, display notifications, and registrar workflow must stay coherent.

## `W2A-SR-060` / `W2A-SR-080` / `W2A-SR-090` / `W2A-SR-100` payment-heavy or mixed reporting

### Option A: Read-Only Reporting Extraction

- Extract read-only analytics/listing handlers (`list_appointments`, `admin_stats` analytics) into reporting services.
- Keep payment mutations untouched.

### Option B: Dedicated Payment Domain Services

- `RegistrarCheckoutService`
- `CashierPaymentService`
- `PaymentReadModelService`
- `PaymentAnalyticsService`

This is the correct long-term shape, but it should be handled as a payment track, not as generic router cleanup.

### Option C: Defer to Wave 2D

- Recommended for anything that changes invoice/provider/payment status or visit payment reconciliation.

## Decision Tree

1. If the handler mutates queue status or queue settings: default to Wave 2C.
2. If the handler calls payment providers, mutates invoice/payment state, or derives visit payment status: default to Wave 2D.
3. If the handler is read-only but shapes shared queue/payment read models: allow only narrow micro-slices with explicit human acknowledgement.
