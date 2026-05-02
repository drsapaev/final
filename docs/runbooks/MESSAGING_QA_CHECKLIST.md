# Messaging QA Checklist

> Historical evidence note: this checklist is preserved for messaging rollout history.
> Do not treat it as the primary clinic-wide acceptance runbook; current operator truth is `docs/PANEL_QA_CHECKLIST.md` plus active role runbooks.

## Purpose

Use this runbook to verify the full messaging stack after backend, frontend, or integration changes.

## Canonical Surfaces

- User chat: `/messages/*` REST and `/ws/chat`
- AI chat: `/ai/chat/*` REST and `/api/v1/ai/chat/ws`
- Telegram: `/admin/telegram/*`, `/telegram/*`, `/telegram-bot/*`
- Notifications: `/notifications/*`, `/notifications/notification-status`, and `/ws/notifications/connect`

## Smoke Path

- Login as User A and User B.
- Open the chat surface and confirm the conversation list loads.
- Send a text message from A to B and confirm it appears in both tabs.
- Open the same conversation on B and confirm the unread badge clears.
- Send a voice message and confirm playback opens through the voice stream URL.
- Upload a file and confirm the attachment renders and opens safely.
- Toggle a reaction and confirm both tabs reflect the same reaction state.
- Delete a message and confirm the sender/recipient views stay consistent.
- Open AI chat and confirm a message can be sent and a response returns.
- Open Telegram settings and confirm settings load and save.
- Confirm Telegram webhook operations are Admin-only and reject requests without the configured secret token.
- Open notification preferences and confirm save + reload persistence.
- Open notification system status and confirm provider cards render from the notification-status API response.
- Use the chromium clean-session proof under `output/playwright/messaging-rollout-proof/` as the canonical release-grade evidence set for this run.

## Regression Path

- Re-open the same conversation after reload and confirm history is preserved.
- Reconnect the websocket and confirm presence / online status recovers.
- Confirm active conversation read state stays aligned after an incoming message.
- Confirm search / available-users filtering still finds the expected recipient.
- Confirm voice and file attachments remain accessible only to conversation participants.

## Destructive / Admin-Only

- Change Telegram settings on a staging/test account only.
- Rotate Telegram webhook secrets only in staging/test data.
- Toggle notification preferences for a dedicated QA user only.
- Revoke or rotate test tokens only in staging/test data.
- Do not use destructive messaging actions on production data during manual smoke.

## Evidence

- Attach screenshots for the conversation list, active chat, AI chat, Telegram settings, and notification preferences.
- Attach browser console and network logs for any failed websocket, upload, or receipt-sync path.
- Record the exact user, route, and message ID when a flow fails.
- For rollout proof, keep the latest chat, console, network, attachment, and voice artifacts in `output/playwright/messaging-rollout-proof/`.
