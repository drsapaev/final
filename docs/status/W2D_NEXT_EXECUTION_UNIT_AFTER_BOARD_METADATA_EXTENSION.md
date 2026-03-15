# Next execution unit after board metadata extension

## Decision

`A) reduce legacy /board/state usage review`

## Why this is the safest next step

The board page is now mostly off legacy metadata fallback.

What still remains on legacy `/board/state` in the staged page path:

- `is_paused`
- `is_closed`

Those are not straightforward "just wire one more field" candidates. Their
backend ownership and product semantics are still unclear, so another narrow
metadata extension slice would likely turn into guesswork.

The safest next move is therefore a bounded review of how much legacy
`/board/state` usage is still real, whether `is_paused` / `is_closed` should
survive as first-class board-display fields, and whether they need a dedicated
owner before any further frontend switch.

## Why not the other options

- `B) add queue_state later as separate prep track`
  - valid, but unrelated to the remaining legacy metadata dependency
- `C) one more narrow metadata extension slice`
  - unsafe until paused/closed ownership is clarified
- `D) human review needed`
  - not yet necessary; a bounded legacy-usage review can narrow the decision
    first
