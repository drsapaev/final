## Active Blockers Before the First Frontend Switch

## 1. Missing Metadata Fields on the New Endpoint v1

The new endpoint does not yet expose:

- `logo`
- `is_paused`
- `is_closed`
- `contrast_default`
- `kiosk_default`

This does not block a narrow staged migration completely, but it prevents a full one-shot cutover.

## 2. No Dedicated Frontend Adapter Layer Yet

`DisplayBoardUnified.jsx` currently:

- fetches `/board/state` directly
- normalizes payload fields inline
- mixes fallback/default behavior into the page component

Without a dedicated adapter/service, the first frontend switch would be harder to review and harder to roll back.

## 3. Legacy Contract and Live UI Shape Still Differ

The live UI expects metadata-first board state, while legacy `/board/state` is an OnlineDay-style counter payload.

This mismatch is currently masked by:

- inline normalization in `DisplayBoardUnified.jsx`
- local storage fallback
- hardcoded page defaults

That means frontend migration still needs an explicit compatibility strategy, not just a URL swap.

## 4. No Central Frontend API Constant/Wrapper for the New Endpoint

There is no dedicated board-display endpoint wrapper yet in:

- `frontend/src/api/endpoints.js`
- `frontend/src/api/services.js`

This is a small blocker, but it is also the cleanest next prep step.

## Non-Blockers

These were checked and should not block the first migration slice:

### Board key sourcing

Not a blocker. `DisplayBoardUnified.jsx` already has `currentBoardId` from:

- `?board=...` query param
- fallback prop default `main_board`

### Queue counters

Not a blocker for the metadata-first migration. They already come from `/queues/stats`, not `/board/state`.

### Realtime display state

Not a blocker for the metadata-first migration. The websocket path is already separate.

## Blocker Summary

The first frontend switch is blocked only in a narrow way:

- missing metadata fields require fallback
- a small frontend adapter layer should exist before switching the page

This does not require backend route changes or legacy route removal.
