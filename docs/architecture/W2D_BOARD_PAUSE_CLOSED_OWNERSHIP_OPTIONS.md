# W2D board pause/closed ownership options

## Option A: display-board settings ownership

Owner candidate:

- `Setting(category="display_board", key="is_paused")`
- `Setting(category="display_board", key="is_closed")`

Pros:

- simple additive extension to the new board-display endpoint
- keeps ownership local to the display/board domain
- easy staged frontend migration

Cons:

- risks turning operational state into unreviewed key/value config
- no evidence this is already a real product/admin workflow
- can blur transient operational state with persistent settings

Rollout risk:

- medium

Fits new board-display endpoint:

- yes, if product confirms these are display metadata / display control flags

## Option B: dedicated operational board-status owner

Owner candidate:

- dedicated board status model/service or operational admin adapter

Pros:

- clearer domain boundary
- supports explicit semantics for pause/closed state transitions
- avoids overloading generic settings storage

Cons:

- heavier than the current narrow migration scope
- requires new ownership and likely new admin/control surface

Rollout risk:

- medium-high

Fits new board-display endpoint:

- yes, but only after a new backend owner exists

## Option C: derive from queue/clinic state

Owner candidate:

- legacy `is_open`
- clinic working-hours state
- queue open/closed lifecycle

Pros:

- may avoid introducing extra display-only state
- could align display banners with actual operational state

Cons:

- current UI wording is broader than proven queue semantics
- derivation rules are not established
- risks mixing display concerns back into queue/open-close legacy logic

Rollout risk:

- high

Fits new board-display endpoint:

- only if explicit derivation rules are approved first

## Option D: keep compatibility-only for now

Owner candidate:

- none yet; keep on legacy compatibility fallback

Pros:

- zero runtime risk now
- honest about missing ownership
- preserves rollback simplicity

Cons:

- legacy dependency remains
- no path to removing `/board/state` usage for these fields yet

Rollout risk:

- low immediately, but blocks full cleanup

Fits new board-display endpoint:

- not yet
