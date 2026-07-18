// src/types/features/emr.ts
// Phase 0.5 / 1.4 — EMR state machine types.
// Plan: JS-to-TS-Migration-Plan v3, section 1.4
//
// SSOT: frontend/src/reducers/emrReducer.js — EMR_ACTIONS
// (UI state machine, not in OpenAPI)
//
// Action payload shapes are derived from the actual reducer code,
// not from the plan's slightly-off spec ("точные action types из кода").

export type EmrStatus = 'idle' | 'loading' | 'saving' | 'error' | 'conflict';

/** Shape of `state.conflict` after CONFLICT_DETECTED runs. */
export interface EmrConflict {
  serverVersion: unknown;
  yourVersion: unknown;
  lastEditedBy: string;
  lastEditedAt: string;
}

/** Raw EMR record shape (subset we read). The full record is backend-defined. */
export interface EmrRecord {
  data?: Record<string, unknown>;
  version?: number;
  row_version?: number;
  updated_at?: string | null;
  [key: string]: unknown;
}

export interface EmrState {
  emr: EmrRecord | null;
  data: Record<string, unknown>;
  version: number;
  rowVersion: number;
  status: EmrStatus;
  isDirty: boolean;
  lastSaved: string | null;
  conflict: EmrConflict | null;
  history: Record<string, unknown>[];
  future: Record<string, unknown>[];
  error: unknown;
}

/**
 * Payload of CONFLICT_DETECTED — mirrors what the backend returns when
 * optimistic lock fails. Field names are snake_case (backend convention).
 */
export interface EmrConflictDetectedPayload {
  current_version: unknown;
  your_version: unknown;
  last_edited_by: string;
  last_edited_at: string;
}

/**
 * Discriminated union of EMR reducer actions.
 * Action types must match EMR_ACTIONS in reducers/emrReducer.js exactly —
 * do not invent new variants here without updating the reducer.
 */
export type EmrAction =
  | { type: 'LOAD'; payload: { emr: EmrRecord } }
  | { type: 'SET_FIELD'; payload: { field: string; value: unknown } }
  | { type: 'SET_NESTED_FIELD'; payload: { path: string; value: unknown } }
  | { type: 'SAVE_START' }
  | { type: 'SAVE_SUCCESS'; payload: { emr: EmrRecord } }
  | { type: 'SAVE_ERROR'; payload: { error: unknown } }
  | { type: 'CONFLICT_DETECTED'; payload: EmrConflictDetectedPayload }
  | { type: 'CONFLICT_RESOLVED'; payload: { data?: Record<string, unknown> | null; rowVersion?: number | null } }
  | { type: 'UNDO' }
  | { type: 'REDO' }
  | { type: 'RESET_DIRTY' };

/**
 * Vital signs sub-record — used inside EMR data.
 * TODO: tighten in Phase 5.8 (emr-v2/) once we inspect actual EMR payloads.
 */
export interface VitalSigns {
  blood_pressure_systolic?: number;
  blood_pressure_diastolic?: number;
  heart_rate?: number;
  temperature?: number;
  respiratory_rate?: number;
  oxygen_saturation?: number;
  weight?: number;
  height?: number;
  notes?: string;
  measured_at?: string;
}
