// src/types/features/telegram.ts
// Phase 0.5 — Telegram domain UI types (placeholder).
// Will be filled in during Phase 5.16 (telegram components migration).
//
// SSOT:
//   - frontend/src/components/telegram/
//   - frontend/src/hooks/useTelegramAuth.jsx
//   - backend OpenAPI schemas: TelegramWebhookRequest, TelegramBotStatsResponse, etc.

// TODO Phase 5.16: TelegramBotConfig, TelegramWebhookEvent, TelegramMiniAppManifest
export type TelegramBotConfig = Record<string, unknown>;
export type TelegramWebhookEvent = Record<string, unknown>;
