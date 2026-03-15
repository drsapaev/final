# W2D Open / Close Target Contract

## Recommended Direction

The safest target direction is:

- `open_day`: survive **for now**
- `close_day`: survive **for now**

But only as **operational admin lifecycle actions**, not as queue-domain operations.

## Recommended Owner

If these routes survive, their future owner should be:

- a dedicated operational admin adapter / compatibility owner

They should **not** be treated as:

- `QueueDomainService.allocate_ticket()` style queue operations
- patient-level queue progression actions
- SSOT queue allocation APIs

## Recommended Meaning

### `open_day`

Target meaning:

- open or re-enable a legacy department/day intake window for ticket issuance

### `close_day`

Target meaning:

- close or disable that same legacy intake window

## Should Current Naming Remain?

During transition, yes.

Reason:

- the routes are still mounted
- external/manual usage is unresolved
- abrupt renaming would add compatibility risk without yet solving ownership

Longer term, clearer naming may be better, but that is not the first follow-up step.

## Long-Term Position

These actions should not define the future queue architecture.

They may either:

1. survive as a narrow operational compatibility/admin layer, or
2. be deprecated later if real usage is not confirmed

At this stage, the first safe move is **not replacement**, but characterization of the legacy runtime behavior and consumer risk.
