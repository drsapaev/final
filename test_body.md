## Summary
**What:** Added `aria-hidden="true"` and `focusable="false"` to decorative SVGs (loading spinners, progress rings) within `Button.tsx` and `Progress.tsx`. Also added a journal entry to `.Jules/palette.md`.
**Why:** Screen readers were potentially announcing redundant or confusing "unlabeled graphic" information for purely visual elements, despite the parent containers already correctly conveying the loading or progress state via ARIA attributes (`aria-busy`, `aria-valuenow`).
**Before/After:** No visual changes. Purely accessibility improvements.
**Accessibility:** Prevents screen readers from redundantly announcing purely decorative SVGs when the parent element already handles communicating the state via ARIA attributes.

## Cyclic Execution Evidence
not applicable - simple accessibility attribute addition.

## Contract Impact
not applicable - UI components accessibility only, no API, websocket, event, or frontend consumer contract changed.

## RBAC / Permissions
not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime
not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience
not applicable - accessibility improvement only, no user-facing panel or frontend data flow changed.

## Scope Gate
not applicable - simple accessibility attribute addition.

## DevBrain Memory Impact
- [x] no durable memory update needed

## Validation
not applicable - simple accessibility attribute addition.
