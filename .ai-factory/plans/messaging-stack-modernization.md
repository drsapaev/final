# Messaging Stack Modernization Plan

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes
- Execution mode: resumable, with AI Factory status tracking

## Scope
- User-to-user chat
- AI chat
- Voice messages and attachments
- Read receipts, reactions, presence, unread counts
- Telegram and notification surfaces

## SSOT Contract
- Message history truth: persisted message rows plus their server-side event stream.
- Read/unread truth: `is_read`, `read_at`, and the current unread counters derived from the backend.
- Presence truth: best-effort websocket presence state only, not a persisted domain fact.
- Attachment truth: upload record + file metadata + message reference, never local client state alone.
- AI chat truth: separate session/message history, versioned prompts/outputs, and no mixing with user-to-user chat.
- Canonical identifiers:
  - `message_id`
  - `client_message_id` for idempotent sends and reconnect dedupe
  - `conversation_id`
  - `server_sequence` or equivalent per conversation ordering key
  - `last_read_message_id` or `last_read_seq`
- State lifecycles:
  - message: `pending -> sent -> delivered -> read -> failed`
  - attachment: `uploading -> uploaded -> scanned -> available -> blocked`

## Delivery Semantics
- Reliable events:
  - messages
  - reactions
  - read receipts
  - attachment state
  - AI responses and AI history updates
- Ephemeral events:
  - typing
  - presence
  - online/offline hints
- Delivery guarantees:
  - at-least-once delivery plus dedupe for reliable events
  - ordered per conversation, not globally ordered across all chats
  - unread counts must converge after refresh/reconnect
  - reconnect/resync must be idempotent and safe to replay

## Rollout Strategy
- Feature flags for any behavior that could change delivery semantics.
- Backward compatibility window for old clients and old WS payload shapes.
- Rollback criteria defined before changing core transport behavior.
- Migration/backfill steps called out for any schema or state-model change.
- Canary/live smoke required before wider rollout.

## Security Gates
- WebSocket auth checked at handshake and revalidated for sensitive actions.
- Conversation membership checked on every send/read/reaction/delete action.
- Attachment uploads validated for MIME, size, extension spoofing, and safe file paths.
- Telegram webhook/signature handling kept explicit and documented.
- AI chat prompts/outputs reviewed for PHI/PII leakage and retention semantics.
- Rate limiting / spam control considered for send and upload paths.

## Observability
- Message send success rate.
- Duplicate delivery rate.
- Reconnect recovery success rate.
- Unread drift incidents.
- WebSocket auth failures.
- Attachment upload success/failure.
- Telegram delivery success rate.
- AI stream interruption rate.
- p95 send-to-visible latency.
- p95 conversation-switch latency.

## Definition of Done
- No cross-conversation data leaks.
- One client send does not create duplicate persisted messages.
- Reconnect does not break ordering or unread consistency.
- Attachments cannot be downloaded outside the allowed scope.
- AI chat history stays separate from user chat history.
- Telegram/notifications stay aligned with in-app state.
- Narrow/mobile viewport does not break composer, history, or read state.
- Smoke, regression, and rollout proof all pass on a clean session.

## Tasks

- [x] TASK 1: Audit and truth-map the messaging stack
  - Build a lifecycle map for message, read/unread, attachment, presence, Telegram, and AI chat flows.
  - Capture the event taxonomy and current data-model inventory.
  - Build a ranked P0/P1/P2 backlog with repro steps, evidence, and source-of-truth.
  - Record the baseline in `.ai-factory/logs/MESSAGING_AUDIT_STATUS.md`.

- [x] TASK 2: Lock contracts and rollout gates
  - Formalize API and WS payload contracts.
  - Define idempotency keys, sequencing, and read/unread semantics.
  - Mark reliable vs ephemeral events explicitly.
  - Define feature-flag, backward-compatibility, and rollback rules.
  - Freeze the contract before expanding backend/frontend work.
  - Version every websocket payload with `contract_version` and log one mismatch warning on the client side when the wire contract drifts.

- [x] TASK 3: Harden the backend messaging transport
  - Fix REST/WS authz gaps and conversation membership checks.
  - Restore read-receipt, reaction, and delete broadcast semantics.
  - Tighten content/file validation and upload safety.
  - Align user lookup/search behavior and AI chat separation rules.
  - Keep backend changes compatible with the locked contract.

- [x] TASK 4: Harden the frontend messaging UX/state
  - Make active conversation, unread, presence, typing, and reconnect behavior deterministic.
  - Improve optimistic updates, loading/error states, and stale-state cleanup.
  - Validate AI chat history/streaming behavior separately from user chat.
  - Verify narrow/mobile viewport behavior for the composer and history pane.

- [x] TASK 5: Harden integrations and operational surfaces
  - Validate Telegram delivery/signature handling.
  - Keep notification/push/state mapping aligned with the app contract.
  - Check any external integration that can mutate or reflect messaging state.
  - Document any rollout constraints or operational dependencies.

- [x] TASK 6: Add regression coverage and rollout proof
  - Add backend unit/integration tests for messaging events, auth, and reconnect semantics.
  - Add frontend tests for chat context, unread sync, and AI chat flows.
  - Add browser smoke for two-user chat, voice/attachment, reconnect/resync, and AI chat.
  - Run clean-session rollout proof before considering the cycle stable.

- [x] TASK 7: Update docs, runbooks, and execution log
  - Sync messaging-related docs/runbooks with the implemented contract and rollout path.
  - Keep `.ai-factory/logs/MESSAGING_AUDIT_STATUS.md` resumable with completed steps, blockers, and evidence.
  - Add any SLI/SLO notes or operational guardrails that the team should keep using.

## Acceptance Criteria
- No cross-conversation data leaks or auth bypasses.
- Duplicate delivery is suppressed or safely deduped.
- Reconnect/resync keeps ordering and unread counts consistent.
- AI chat remains isolated from user chat history and retention semantics.
- Telegram/notification surfaces keep working as documented.
- Targeted tests and browser smoke pass on a clean local session.
