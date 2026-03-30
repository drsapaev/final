# Notifications 2026-grade v2

## Goals
- Backend-owned persistent inbox with server-authoritative read state.
- Canonical notification event/delivery model with WS compatibility for `notification` and `queue_update`.
- Frontend role inbox and notification center aligned to backend contract.
- No direct panel-level `alert()` / toast usage outside the shared adapter layer.

## Tasks
- [x] Backend notification event/delivery model + Alembic migration
- [x] Backend notification platform service + API/WS contract
- [x] Frontend notification center/inbox + API alignment
- [x] Role panel integration + notification prompt polish
- [x] Regression tests for inbox, WS normalization, and panel-level notification guardrails
