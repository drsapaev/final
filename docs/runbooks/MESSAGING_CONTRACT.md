# Messaging Contract

This document is the operational SSOT for the messaging stack.

## Canonical Truths

- Message history is authoritative in persisted message rows plus the server event stream.
- Read state is authoritative in the backend and exposed via `is_read`, `read_at`, and unread counters.
- Presence and typing are best-effort websocket hints only.
- Attachments are authoritative only after backend upload/metadata creation.
- AI chat history is separate from user-to-user chat history.

## Canonical Identifiers

- `message_id`
- `client_message_id` for idempotent sends
- `conversation_id`
- `server_sequence` or equivalent per conversation ordering key
- `last_read_message_id` or `last_read_seq`

## State Lifecycles

- Message: `pending -> sent -> delivered -> read -> failed`
- Attachment: `uploading -> uploaded -> scanned -> available -> blocked`
- AI response: `draft -> streaming -> completed -> failed -> cancelled`

## Event Taxonomy

### Reliable events

- `new_message`
- `message_read`
- `messages_read`
- `reaction_update`
- `message_deleted`
- attachment lifecycle updates
- AI session/history updates

### Ephemeral events

- `typing`
- `online_status`
- `ping` / `pong`
- transient reconnect hints

## Delivery Semantics

- Reliable events use at-least-once delivery with dedupe on the client.
- Conversation ordering is guaranteed per conversation, not globally.
- Reconnect/resync must be idempotent and safe to replay.
- Unread counters must converge after refresh or reconnect.
- Every websocket payload includes `contract_version` so clients can detect rollout mismatches without breaking the session.
- `pong` is a heartbeat acknowledgement and must not surface as an error in normal operation.

## Rollout Rules

- Use feature flags for any delivery-semantic change.
- Define rollback criteria before changing websocket payloads or read semantics.
- Keep a backward-compatibility window for older clients.
- Validate a clean-session smoke before widening rollout.
- If a payload version mismatch is detected, log it once and continue on the compatible path when possible.
- Treat unknown top-level fields as backward-compatible; never remove required fields without a rollout window.
- Treat `pong` as a valid no-op inbound message on the websocket channel.

## Security Rules

- Authenticate websocket handshakes.
- Re-check conversation membership on send/read/reaction/delete paths.
- Validate attachments for MIME, size, extension spoofing, and safe paths.
- Keep Telegram webhook handling explicit and documented.
- Validate Telegram webhook secret tokens when configured, and keep bot management endpoints Admin-only.
- Keep AI chat prompts and outputs free of accidental PHI/PII leakage.

## Observability

- Message send success rate
- Duplicate delivery rate
- Reconnect recovery success rate
- Unread drift incidents
- WebSocket auth failures
- Attachment upload success/failure
- Telegram delivery success rate
- AI stream interruption rate
- p95 send-to-visible latency
- p95 conversation-switch latency

## Operational Guardrails

- Treat `output/playwright/messaging-rollout-proof/` as the canonical clean-session rollout proof set for this cycle.
- Re-run the chromium two-user smoke after any transport, composer, attachment, voice, or reconnect change.
- Treat recurring websocket auth failures, unread drift, duplicate delivery, or attachment scope leaks as release blockers.
- Treat Telegram delivery regressions and AI stream interruptions as rollout-review items before widening exposure.
- Use the p95 send-to-visible and conversation-switch latency metrics as the first performance regression checks for chat changes.
- When smoke fails, capture console and network logs plus the exact user IDs and routes before retrying.

## Done When

- Cross-conversation leaks are absent.
- Duplicates are suppressed or safely deduped.
- Reconnect preserves ordering and unread consistency.
- Attachments stay scoped.
- AI chat remains separate from user chat.
- Telegram and notifications stay aligned with the app state.
- Notification-status UI reflects the backend response shape without manual response unwrapping bugs.
