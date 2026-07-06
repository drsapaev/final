## Summary
Added `aria-label="Закрыть"` and `title="Закрыть"` to the icon-only "✕" button in the fullscreen variant of `Modal.jsx`.
Updated `weasyprint` from `>=68.1,<69.0` to `>=69.0,<70.0` to fix the `CVE-2026-49452` security vulnerability.

## Cyclic Execution Evidence
Not applicable because this is a simple a11y HTML attribute addition and dependency bump.

## Contract Impact
Not applicable because there are no backend changes affecting contracts.

## RBAC / Permissions
Not applicable because this is a pure UI change and dependency bump without permission checks.

## Notification / Realtime
Not applicable because this does not touch realtime functionality.

## Frontend Resilience
Not applicable because it doesn't affect data loading or frontend resilience logic.

## Scope Gate
Not applicable because it only adds aria labels to an existing UI component.

## Validation
Not applicable because tests cover the UI building.
