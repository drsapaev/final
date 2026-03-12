# W2D Next Execution Unit After Board/Stats Prep

## Decision

`B) replacement-prep for queues.stats only`

## Why This Is Safest First

- It is a confirmed live mounted surface.
- It has a confirmed frontend consumer in `DisplayBoardUnified.jsx`.
- It is the narrowest pure counter surface in the OnlineDay board/stats group.
- It does not require solving board/display metadata ownership in the first step.
- It can later become the canonical source for any redirect or retirement of `appointments.stats`.

## Why Not The Other Options

### Not `A) board_state only`

`board.state()` is live, but it is not a clean counter-only contract. The current UI
expects board/display metadata that runtime does not actually provide consistently.
Replacing it first would force a broader adapter/read-model decision.

### Not `C) appointments.stats retire/redirect prep`

`appointments.stats()` looks like a duplicate wrapper with no confirmed product consumer.
It is a weaker first target than the live, user-facing `queues.stats()` surface.

### Not `D) combined board/stats read-model prep`

That would broaden the first slice too early by mixing:

- queue counters
- board metadata
- retire-vs-redirect decisions

The safer path is to start with the smallest live counter replacement.
