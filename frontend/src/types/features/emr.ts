// src/types/features/emr.ts
// Phase 0.5 / 1.4 — EMR state machine types.
// Plan: JS-to-TS-Migration-Plan v3, section 1.4
//
// SSOT: frontend/src/reducers/emrReducer.js — EMR_ACTIONS
// (UI state machine, not in OpenAPI)

export type EmrStatus = 'idle' | 'loading' | 'saving' | 'error' | 'conflict';

export interface EmrState {
  emr: Record<string, unknown> | null;
  data: Record<string, unknown>;
  version: number;
  rowVersion: number;
  status: EmrStatus;
  isDirty: boolean;
  lastSaved: string | null;
  conflict: {
    serverVersion: unknown;
    yourVersion: unknown;
    lastEditedBy: string;
    lastEditedAt: string;
  } | null;
  history: Record<string, unknown>[];
  future: Record<string, unknown>[];
  error: unknown;
}

/**
 * Discriminated union of EMR reducer actions.
 * Action types must match EMR_ACTIONS in reducers/emrReducer.js exactly —
 * do not invent new variants here without updating the reducer.
 */
export type EmrAction =
  | { type: 'LOAD'; payload: { emr: Record<string, unknown> } }
  | { type: 'SET_FIELD'; payload: { field: string; value: unknown } }
  | { type: 'SET_NESTED_FIELD'; payload: { path: string; value: unknown } }
  | { type: 'SAVE_START' }
  | { type: 'SAVE_SUCCESS'; payload: { emr: Record<string, unknown> } }
  | { type: 'SAVE_ERROR'; payload: { error: unknown } }
  | { type: 'CONFLICT_DETECTED'; payload: Record<string, unknown> }
  | { type: 'CONFLICT_RESOLVED'; payload: { data?: Record<string, unknown>; rowVersion?: number } }
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
