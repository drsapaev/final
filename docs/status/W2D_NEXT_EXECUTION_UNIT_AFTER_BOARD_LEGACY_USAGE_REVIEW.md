# Next execution unit after board legacy usage review

## Decision

`D) human/business review needed`

## Why this is the safest next step

`DisplayBoardUnified.jsx` is already mostly off legacy `/board/state`.

The only remaining board-metadata dependency is:

- `is_paused`
- `is_closed`

These are not blocked by missing code wiring anymore. They are blocked by
missing ownership and meaning.

Trying a code slice before clarifying semantics would likely create a fake owner
or silently redefine product behavior.

## Why the other options were not chosen

- `A) narrow migration of is_paused/is_closed to new endpoint`
  - unsafe without approved ownership
- `B) backend prep for those fields first`
  - backend prep would still require an unproven owner
- `C) keep legacy fallback and move to another surface`
  - possible later, but the cleanest immediate action is to resolve the
    semantics first
