# Messaging Audit Status

> Historical evidence log. Keep for audit trail and implementation history; do not treat this file as the live product contract.

Updated: 2026-03-30

## Current Tracking

- Current case: `awaiting user direction`
- Last completed case: `TASK 7 - Update docs, runbooks, and execution log`
- Next case: `awaiting user direction`
- Blockers: none

## Initial Findings

- `P0` - `broadcast_event` and `notify_messages_read` are referenced by the messaging service layer but are missing from the current chat WebSocket manager.
- `P1` - Active-conversation read behavior is not yet auto-synced from the frontend when a new message arrives while the chat is open.
- `P2` - Available-user search still prefers username/email and can miss `full_name` matches in the chat picker.

## Evidence

- Backend messaging router: `backend/app/api/v1/endpoints/messages.py`
- Backend WebSocket manager: `backend/app/ws/chat_ws.py`
- Backend messaging service: `backend/app/services/messages_api_service.py`
- Frontend chat state: `frontend/src/contexts/ChatContext.jsx`
- Frontend AI chat hook: `frontend/src/hooks/useAIChat.js`

## Notes

- Backend and frontend implementation lanes are running in parallel.
- Keep the log resumable after each completed task.
- Update the backlog classification if a finding turns out to be environment noise or a duplicate.
- The plan now has explicit SSOT, delivery-semantics, rollout, observability, and DoD gates.
- Backend event-contract hardening and frontend auto-read sync are already in motion; keep them aligned with the locked contract.
- The wire contract is now versioned in both directions and client mismatches are logged once without breaking the session.
- Chat websocket heartbeats now treat `pong` as a valid no-op and log client contract-version drift once per session.
- The operational contract is documented in `docs/runbooks/MESSAGING_CONTRACT.md`.
- TASK 3 is complete: backend transport now has versioned WS payloads, broadcast/read/delete semantics, attachment validation, and scoped file download protection.
- TASK 4 is complete: inbox now hydrates before websocket open, conversation unread/presence/typing state is deterministic, AI chat stale-session handling is guarded, and compact/mobile chat smoke passes.
- Browser smoke evidence now covers both desktop and narrow/mobile viewports.
- TASK 5 is complete: Telegram webhook secret validation and Admin gates are in place, notification-status renders from the backend response shape, and the messaging QA/docs runbook reflects the operational contract.
- TASK 6 is complete: the regression/rollout smoke now passes on a clean session with two-user chat, attachment, voice, and reconnect coverage.
- Recent browser proof:
  - `output/playwright/messaging-rollout-proof/messaging-rollout-proof-chat.png`
  - `output/playwright/messaging-rollout-proof/messaging-rollout-proof-console.log`
  - `output/playwright/messaging-rollout-proof/messaging-rollout-proof-network.json`
- TASK 7 is complete: docs, runbooks, and execution log are synced with the implemented contract and rollout proof.
