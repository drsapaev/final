# W2D next_ticket Replacement Readiness

## Verdict

`READY_FOR_CONTRACT_CLARIFICATION`

## Why

What the route does today is already clear enough from code:

- it issues the next legacy department/day ticket number
- increments `waiting`
- broadcasts updated legacy stats

What is not clear enough yet is the target product meaning:

- should this action survive at all
- if it survives, should it remain an operational admin action
- if it changes, what should replace the legacy department/day semantics

## Why not narrow replacement prep yet

Not safe yet because:

- there is no clean SSOT equivalent
- there is no confirmed in-repo direct caller to anchor replacement around
- a wrong replacement could silently change numbering and board-facing state meaning

## Why not “keep legacy forever” yet

Also premature, because:

- the route is still mounted
- external/manual usage is unresolved
- cleanup vs retention is still a product/operations decision
