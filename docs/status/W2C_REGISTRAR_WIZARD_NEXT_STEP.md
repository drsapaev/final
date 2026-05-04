# Wave 2C Registrar Wizard Next Step

Date: 2026-03-08
Status: `human review needed`

## Recommended Next Step

Run a contract-review pass for the mounted registrar wizard cart family before any
boundary migration or behavior correction.

## Why

- the mounted wizard flow is still mixed with invoice creation and payment-adjacent
  orchestration
- queue claim ownership is not specialist-level in the observed runtime; it is
  queue-tag driven
- duplicate reuse currently depends on resolved queue identity rather than the
  canonical active-entry contract

## What The Human Review Should Clarify

1. whether the wizard cart family should intentionally own queue claims per
   `queue_tag` rather than per specialist
2. whether reused rows should keep their old `visit_id` / source ownership
3. whether queue allocation is allowed to remain inside the invoice/cart request
   or must be extracted first

## Why Other Options Were Not Chosen

### `narrow wizard behavior-correction slice`

Not yet safe because the target claim model is still ambiguous.

### `narrow wizard boundary migration slice`

Not yet safe because the mounted runtime is still billing-coupled.

### `additional wizard characterization/tests`

Current characterization is sufficient to identify the blocking contract issues.

### `defer wizard family and move to another allocator family`

Possible later, but the current best next step is to resolve the wizard-family
contract while the evidence is fresh.
