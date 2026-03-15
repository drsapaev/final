# W2D next_ticket Replacement Gaps

## Missing SSOT equivalent

Yes.

There is no confirmed SSOT operation today that means:

- issue next department/day ticket number
- increment waiting counter
- keep serving/done untouched
- broadcast legacy board/stats shape

## Numbering parity concerns

Yes.

Current numbering depends on:

- `OnlineDay.start_number`
- `Setting(queue::...::last_ticket)`
- `max(last_ticket, start_number - 1) + 1`

That is not the same as SSOT queue-entry numbering semantics.

## State-transition parity concerns

Yes.

Current runtime changes only:

- `last_ticket`
- `waiting`

It does not:

- select an existing waiting patient
- create a SSOT queue entry
- advance someone to `serving`

Any replacement that assumes “call next patient” would be wrong.

## Board / display parity concerns

Yes.

`next_ticket` feeds legacy board-visible state indirectly through:

- `/queues/stats`
- `/board/state`
- legacy `queue.update` websocket payload

If replacement changes counter timing or meaning, board behavior may drift even without a direct route consumer.

## Consumer migration concerns

Yes.

Current code audit found:

- no confirmed in-repo direct caller
- but the route remains mounted and public in OpenAPI

That leaves unresolved risk of:

- manual usage
- external client usage
- forgotten admin tooling outside this repo

## Business / product ambiguity

Yes.

The unresolved question is:

- should this action continue to exist at all
- and if yes, should it remain a department/day counter action or become a different operational action

## Replacement blockers summary

Primary blockers:

- missing target-domain meaning
- no clean SSOT equivalent
- unresolved consumer ownership

Secondary blockers:

- board/stats parity sensitivity
- numbering parity sensitivity
