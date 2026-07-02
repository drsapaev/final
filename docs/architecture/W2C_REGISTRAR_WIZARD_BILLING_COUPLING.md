# Wave 2C Registrar Wizard Billing Coupling

Date: 2026-03-08
Mode: readiness recheck, docs-only

## Mounted Runtime Under Review

Endpoint:

- `POST /api/v1/registrar/cart`

Primary runtime owner:

- `backend/app/api/v1/endpoints/registrar_wizard.py`

## What The Mounted Owner Does Today

Inside one mounted request flow, `/registrar/cart` currently performs:

- cart validation
- visit creation
- invoice creation
- invoice-visit linking
- billing total calculation
- same-day queue assignment for confirmed visits
- response shaping for visits, invoice and queue numbers

## Queue Allocation Position In The Flow

Queue allocation happens after invoice/visit construction, but before the final
request commit.

That means queue assignment is not isolated as its own mounted use-case owner.

## Coupling Severity

Severity: `HIGH`

## Why The Coupling Is High

### 1. Shared request transaction

Billing-side records and queue-side records are created within the same mounted
request/session lifecycle.

### 2. Shared response contract

The endpoint returns invoice data, visit data and queue-number data together.

### 3. Shared failure handling

Queue-assignment errors are handled as warnings inside the same cart flow,
instead of a clean queue-domain boundary with its own dedicated owner.

### 4. Shared orchestration owner

The mounted endpoint still owns both:

- business orchestration for billing/cart creation
- queue-assignment triggering

## What This Coupling Does Not Mean

This does not mean numbering itself depends on billing math.

The queue allocator still lives in the legacy queue service path, not in the
billing service.

## Readiness Implication

The mounted wizard family is not a clean queue-only caller today.

Even though duplicate semantics are corrected, direct boundary migration from
the current owner would still ride through a billing-heavy mounted flow.

## Practical Conclusion

Wizard-family is closer to migration than before, but the mounted owner still
benefits from decomposition before a clean queue-boundary migration can be
considered complete and local.
