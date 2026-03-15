# W2D next execution unit after board_state harness

## Decision

`D) human review needed`

## Why this is the safest next step

The harness answered the technical question we needed:

- queue-state parity is not the blocker
- compatibility fields are not the blocker

The blocker is now contract intent:

- should mounted `/board/state` remain a legacy counter surface
- or should it become a real board/display metadata endpoint for the current UI

That is no longer just a narrow implementation question. It is a bounded
contract/ownership decision.

## Why not the larger code steps

### Why not `A) narrow mounted board_state replacement slice`

Because replacement direction is still ambiguous. A narrow code slice would be
guessing whether to preserve a legacy counter contract or move toward the live
metadata consumer contract.

### Why not `B) one more narrow board_state compatibility wiring/fix`

The remaining blocker is not another small compatibility field. It is the fact
that the mounted route and live UI are solving different problems.

### Why not `C) keep legacy route and defer replacement`

Deferring may ultimately be correct, but that choice should follow an explicit
human decision about whether `/board/state` should be retired, replaced, or
split.
