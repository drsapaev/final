# Wave 2C QR Payload Compatibility Fix Plan

Date: 2026-03-09
Mode: behaviour-preserving compatibility fix

## Old Compatibility Gap

Current QR create seam preserves QR-local row fields that the current
`QueueDomainService.allocate_ticket(allocation_mode="create_entry")`
compatibility path does not fully carry through:

- `birth_year`
- `address`

The QR seam also shapes the additional-service row payload in a QR-local form,
which should be made directly consumable by the create-entry boundary.

## Chosen Narrow Fix Strategy

1. keep mounted QR runtime on the current QR-local seam
2. make QR handoff payload directly compatible with future `create_entry`
   boundary kwargs
3. minimally widen `queue_service.create_queue_entry(...)` to preserve:
   - `birth_year`
   - `address`
4. prove compatibility through targeted unit tests and characterization checks

## Why This Is Behaviour-Preserving

- no caller migration happens in this slice
- raw SQL numbering in the mounted QR seam remains unchanged
- `queue_time` assignment remains unchanged
- source inheritance remains unchanged
- response shape remains unchanged

## Out Of Scope

- switching mounted QR create branch to `QueueDomainService.allocate_ticket()`
- raw SQL numbering replacement
- duplicate-policy redesign
- `queue_session` semantics changes
- public QR join flow refactor
