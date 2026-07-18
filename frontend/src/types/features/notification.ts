// src/types/features/notification.ts
// Phase 0.5 — Notification domain UI types (placeholder).
// Will be filled in during Phase 3 (NotificationWebSocketContext, NotificationCenterContext)
// and Phase 5.5 (notifications components migration).
//
// SSOT:
//   - frontend/src/contexts/NotificationWebSocketContext.jsx
//   - frontend/src/contexts/NotificationCenterContext.jsx
//   - frontend/src/components/notifications/
//   - backend OpenAPI schemas: NotificationInboxItem, NotificationResponse, etc.

// TODO Phase 3/5.5: NotificationState, NotificationCenterFilters
export type NotificationState = Record<string, unknown>;
