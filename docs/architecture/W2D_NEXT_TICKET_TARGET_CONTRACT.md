# W2D next_ticket Target Contract

## Recommended target direction

`next_ticket` should not be treated as a future core queue-domain operation.

## Should the action survive?

Recommended answer:

- not as a first-class part of the target queue architecture

More precise form:

- if no real consumer remains, retire it
- if a real operational/manual consumer is confirmed, preserve only the business effect through a dedicated operational admin adapter

## If it survives, what should it do?

If survival is required, the action should mean only:

- issue the next operational display/desk ticket for a legacy-compatible department/day surface

It should not mean:

- call next patient
- advance a queue entry
- replace doctor-facing queue progression

## Which domain should own it?

If retained, ownership should sit in:

- an operational admin adapter domain

Not in:

- `QueueDomainService.allocate_ticket()`
- SSOT queue-entry lifecycle
- doctor queue call-next flows

## If it does not survive

Safest retirement path:

1. keep legacy route mounted for now
2. verify external/manual usage with product or operations
3. prepare explicit deprecation track
4. retire instead of rebuilding its semantics into SSOT

## Naming during transition

Legacy naming should not be extended into the target architecture.

If temporary compatibility is required:

- `next_ticket` may remain only as a legacy alias during transition

But the long-term target should use a more honest operational name if the action survives at all.

## Recommended target contract summary

- survive as core queue action: no
- survive as optional operational adapter: only if usage is confirmed
- default strategic direction: deprecate later rather than modernize blindly
