# W2D board pause/closed target decision

## Recommended ownership

Recommended target ownership for both `is_paused` and `is_closed`:

- display-domain operational ownership
- not queue-domain
- not OnlineDay / legacy counter ownership

## Move to new board endpoint

- `is_paused`: no, not yet
- `is_closed`: no, not yet

Reason:

- there is no confirmed backend owner today
- the current semantics are not proven by the mounted backend contract
- moving them now would require inventing semantics rather than migrating them

## Keep on legacy / compatibility path

- yes, temporarily

More precisely:

- keep them on compatibility fallback in `DisplayBoardUnified.jsx`
- do not treat current legacy `/board/state` as a real long-term owner

## Business / product sign-off needed

- yes

Questions that still need explicit confirmation:

- does `is_paused` represent manual board pause, service pause, or queue pause?
- does `is_closed` represent clinic closed, department closed, or board closed?
- are these persistent settings or transient operational flags?

## Practical implication

The new metadata-first board endpoint should remain focused on confirmed fields.
`is_paused` and `is_closed` should only move after ownership and semantics are
explicitly approved.
