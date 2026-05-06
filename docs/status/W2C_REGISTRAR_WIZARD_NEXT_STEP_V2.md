# Wave 2C Registrar Wizard Next Step V2

Date: 2026-03-08
Status: `narrow wizard behavior-correction slice`

## Recommended Next Step

Run one narrow behavior-correction slice for the mounted wizard cart duplicate
gate.

## Exact Scope

- mounted `/registrar/cart` same-day reuse path only
- no boundary migration
- no billing/invoice redesign
- no QR / legacy / force-majeure work

## Target Of The Correction

Keep the wizard-family queue-tag-level claim model, but correct reuse so it
checks canonical active statuses:

- `waiting`
- `called`
- `in_service`
- `diagnostics`

inside the resolved queue claim/day.

## Why This Is The Next Step

- claim ownership is now clarified
- batch-family divergence is justified, so that is no longer the blocker
- the real remaining behavior drift is the duplicate gate
- correcting that drift is smaller and safer than boundary migration

## Why Boundary Migration Was Not Chosen

- `/registrar/cart` is still billing-coupled
- migrating it now would mix contract correction with architectural extraction

## Why Deferral Was Not Chosen

- the next correction target is narrow enough to isolate
- more characterization is not needed before that correction
