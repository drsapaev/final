# Wave 2C Registrar Batch Next Step

Date: 2026-03-07
Status: `human review needed`

## Recommended Next Step

Human review for registrar batch contract questions before any boundary
migration.

## Why

Characterization produced two material contract ambiguities:

1. `diagnostics` entry does not block new allocation, although canonical active
   contract says it is active
2. same-specialist multi-service batch collapses different `queue_tag` values
   into one queue row

Both behaviors may be intentional, but neither should be migrated into a new
boundary blindly.

## Human Review Questions

1. For registrar batch-only flow, should existing `diagnostics` / `in_service`
   rows be reused instead of creating a new row?
2. Should batch grouping remain specialist-only, or should it split by
   `queue_tag` / queue claim?
3. Should `source="morning_assignment"` remain accepted as passthrough input
   for this registrar endpoint?

## Why Other Options Were Not Chosen

### `registrar batch-only boundary migration`

Not yet safe because it would either:

- preserve ambiguous runtime behavior without explicit approval
- or silently normalize behavior and risk drift

### `additional registrar batch characterization/tests`

Current evidence is already sufficient to show the key contract conflicts.
More tests alone will not answer the policy questions.

### `defer to broader registrar family track`

Not necessary yet. The batch-only subfamily is isolated enough for a targeted
human decision before any broader registrar migration.
