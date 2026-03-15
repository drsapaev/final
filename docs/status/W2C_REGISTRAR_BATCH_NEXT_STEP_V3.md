# Wave 2C Registrar Batch Next Step V3

Date: 2026-03-08
Status: `registrar batch-only boundary migration`

## Recommended Next Step

Migrate the mounted registrar batch-only create path to the
`QueueDomainService.allocate_ticket()` compatibility boundary.

## Why This Is Now Safe

- contract clarification is complete
- active-entry drift is corrected
- characterization tests are green
- full backend suite is green
- numbering and fairness semantics were preserved

## Scope For The Next Slice

Allowed:

- mounted registrar batch-only flow
- narrow caller-path migration only
- reuse existing specialist-level claim behavior

Not allowed:

- broader registrar wizard refactor
- QR allocator migration
- `OnlineDay`
- force-majeure
- numbering redesign

## Why Other Options Were Not Chosen

### `more registrar batch characterization needed`

Current evidence is already enough for the next narrow step.

### `human review needed`

No additional human policy decision is required for this local family.

### `defer to broader registrar family track`

Not necessary. The batch-only subfamily is now clean enough to move forward on
its own.
