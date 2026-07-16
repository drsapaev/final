// src/types/features/queue.ts
// Phase 0.5 — Queue domain UI types (placeholder).
// Plan: JS-to-TS-Migration-Plan v3, section 0.5.6
//
// Will be filled in during Phase 5 (queue components migration) and
// Phase 2 (useQueueWebSocket / useDoctorQueue hooks).
//
// SSOT for runtime shapes:
//   - frontend/src/hooks/useQueueWebSocket.js
//   - frontend/src/hooks/useDoctorQueue.js
//   - frontend/src/components/queue/
//
// DO NOT write types here speculatively — read the source files first when
// the corresponding phase starts, then derive types from observed runtime shape.

// TODO Phase 2/5: QueueState, QueueFilters, QueueWebSocketEvent
export type QueueState = Record<string, unknown>;

export type QueueWebSocketEvent =
  | { type: 'PATIENT_CALLED'; payload: Record<string, unknown> }
  | { type: 'PATIENT_JOINED'; payload: Record<string, unknown> }
  | { type: 'QUEUE_UPDATED'; payload: Record<string, unknown> }
  | { type: 'POSITION_UPDATED'; payload: Record<string, unknown> }
  | { type: 'ping'; payload?: never }
  | { type: 'pong'; payload?: never };
