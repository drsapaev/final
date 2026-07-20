/**
 * EMR v2 Reducer - State management with undo/redo support.
 *
 * Phase 1 — migrated from .js. Types from '@/types/features/emr'.
 *
 * Actions:
 * - LOAD: Load EMR data from server
 * - SET_FIELD: Update a single field
 * - SAVE_START/SUCCESS/ERROR: Save lifecycle
 * - CONFLICT_DETECTED: Optimistic lock conflict
 * - UNDO/REDO: Navigate history
 */
import type { EmrAction, EmrRecord, EmrState } from '../types/features/emr';

// Action types — exported as a const object for runtime use.
// The EmrAction discriminated union (in types/features/emr.ts) is the
// compile-time mirror of these runtime strings.
export const EMR_ACTIONS = {
    LOAD: 'LOAD',
    SET_FIELD: 'SET_FIELD',
    SET_NESTED_FIELD: 'SET_NESTED_FIELD',
    SAVE_START: 'SAVE_START',
    SAVE_SUCCESS: 'SAVE_SUCCESS',
    SAVE_ERROR: 'SAVE_ERROR',
    CONFLICT_DETECTED: 'CONFLICT_DETECTED',
    CONFLICT_RESOLVED: 'CONFLICT_RESOLVED',
    UNDO: 'UNDO',
    REDO: 'REDO',
    RESET_DIRTY: 'RESET_DIRTY',
} as const;

// Max history size for undo/redo (memory-conscious)
const MAX_HISTORY_SIZE = 50;

/**
 * Initial state shape
 */
export const initialState: EmrState = {
    emr: null,
    data: {},
    version: 0,
    rowVersion: 0,
    status: 'idle',
    isDirty: false,
    lastSaved: null,
    conflict: null,
    history: [],
    future: [],
    error: null,
};

/**
 * Add to history with size limit
 */
function pushHistory(
  history: Record<string, unknown>[],
  data: Record<string, unknown>,
): Record<string, unknown>[] {
    const newHistory = [...history, JSON.parse(JSON.stringify(data)) as Record<string, unknown>];
    if (newHistory.length > MAX_HISTORY_SIZE) {
        return newHistory.slice(-MAX_HISTORY_SIZE);
    }
    return newHistory;
}

/**
 * Deep set a nested field value.
 * e.g., setNestedValue(obj, 'diagnosis.main', 'headache')
 */
function setNestedValue(
  obj: Record<string, unknown>,
  path: string,
  value: unknown,
): Record<string, unknown> {
    const keys = path.split('.');
    const result = { ...obj };
    let current: Record<string, unknown> = result;

    for (let i = 0; i < keys.length - 1; i++) {
        const key = keys[i];
        const next = current[key];
        current[key] = next && typeof next === 'object' ? { ...(next as Record<string, unknown>) } : {};
        current = current[key] as Record<string, unknown>;
    }

    current[keys[keys.length - 1]] = value;
    return result;
}

/**
 * EMR Reducer
 */
export function emrReducer(state: EmrState, action: EmrAction): EmrState {
    switch (action.type) {
        // =========================================================================
        // LOAD - Initial load from server
        // =========================================================================
        case EMR_ACTIONS.LOAD: {
            const emr = action.payload.emr;
            return {
                ...initialState,
                emr,
                data: emr?.data || {},
                version: emr?.version || 1,
                rowVersion: emr?.row_version || 0,
                status: 'idle',
                lastSaved: emr?.updated_at || null,
            };
        }

        // =========================================================================
        // SET_FIELD - Update single field
        // =========================================================================
        case EMR_ACTIONS.SET_FIELD: {
            const { field, value } = action.payload;

            if (state.data[field] === value) {
                return state;
            }

            return {
                ...state,
                data: {
                    ...state.data,
                    [field]: value,
                },
                isDirty: true,
                history: pushHistory(state.history, state.data),
                future: [],
                error: null,
            };
        }

        // =========================================================================
        // SET_NESTED_FIELD - Update nested field (e.g., 'diagnosis.main')
        // =========================================================================
        case EMR_ACTIONS.SET_NESTED_FIELD: {
            const { path, value } = action.payload;

            return {
                ...state,
                data: setNestedValue(state.data, path, value),
                isDirty: true,
                history: pushHistory(state.history, state.data),
                future: [],
                error: null,
            };
        }

        // =========================================================================
        // SAVE_START - Begin save
        // =========================================================================
        case EMR_ACTIONS.SAVE_START:
            return {
                ...state,
                status: 'saving',
                error: null,
            };

        // =========================================================================
        // SAVE_SUCCESS - Save completed
        // =========================================================================
        case EMR_ACTIONS.SAVE_SUCCESS: {
            const emr: EmrRecord = action.payload.emr;
            return {
                ...state,
                emr,
                version: emr.version ?? state.version,
                rowVersion: emr.row_version ?? state.rowVersion,
                status: 'idle',
                isDirty: false,
                lastSaved: new Date().toISOString(),
                error: null,
                conflict: null,
            };
        }

        // =========================================================================
        // SAVE_ERROR - Save failed
        // =========================================================================
        case EMR_ACTIONS.SAVE_ERROR:
            return {
                ...state,
                status: 'error',
                error: action.payload.error,
            };

        // =========================================================================
        // CONFLICT_DETECTED - Optimistic lock failed
        // =========================================================================
        case EMR_ACTIONS.CONFLICT_DETECTED: {
            const p = action.payload;
            return {
                ...state,
                status: 'conflict',
                conflict: {
                    serverVersion: p.current_version,
                    yourVersion: p.your_version,
                    lastEditedBy: p.last_edited_by,
                    lastEditedAt: p.last_edited_at,
                },
            };
        }

        // =========================================================================
        // CONFLICT_RESOLVED - User resolved conflict
        // =========================================================================
        case EMR_ACTIONS.CONFLICT_RESOLVED: {
            const payload = action.payload;
            return {
                ...state,
                status: 'idle',
                conflict: null,
                ...(payload?.data ? { data: payload.data } : {}),
                ...(payload?.rowVersion ? { rowVersion: payload.rowVersion } : {}),
            };
        }

        // =========================================================================
        // UNDO - Restore previous state
        // =========================================================================
        case EMR_ACTIONS.UNDO: {
            if (state.history.length === 0) {
                return state;
            }

            const previous = state.history[state.history.length - 1];
            const newHistory = state.history.slice(0, -1);

            return {
                ...state,
                data: previous,
                history: newHistory,
                future: [state.data, ...state.future].slice(0, MAX_HISTORY_SIZE),
                isDirty: true,
            };
        }

        // =========================================================================
        // REDO - Restore next state
        // =========================================================================
        case EMR_ACTIONS.REDO: {
            if (state.future.length === 0) {
                return state;
            }

            const next = state.future[0];
            const newFuture = state.future.slice(1);

            return {
                ...state,
                data: next,
                history: [...state.history, state.data].slice(-MAX_HISTORY_SIZE),
                future: newFuture,
                isDirty: true,
            };
        }

        // =========================================================================
        // RESET_DIRTY - Clear dirty flag (after successful autosave)
        // =========================================================================
        case EMR_ACTIONS.RESET_DIRTY:
            return {
                ...state,
                isDirty: false,
            };

        default:
            return state;
    }
}

/**
 * Action creators
 */
export const emrActions = {
    load: (emr: EmrRecord): EmrAction => ({
        type: EMR_ACTIONS.LOAD,
        payload: { emr },
    }),

    setField: (field: string, value: unknown): EmrAction => ({
        type: EMR_ACTIONS.SET_FIELD,
        payload: { field, value },
    }),

    setNestedField: (path: string, value: unknown): EmrAction => ({
        type: EMR_ACTIONS.SET_NESTED_FIELD,
        payload: { path, value },
    }),

    saveStart: (): EmrAction => ({
        type: EMR_ACTIONS.SAVE_START,
    }),

    saveSuccess: (emr: EmrRecord): EmrAction => ({
        type: EMR_ACTIONS.SAVE_SUCCESS,
        payload: { emr },
    }),

    saveError: (error: unknown): EmrAction => ({
        type: EMR_ACTIONS.SAVE_ERROR,
        payload: { error },
    }),

    conflictDetected: (conflictData: {
        current_version: unknown;
        your_version: unknown;
        last_edited_by: string;
        last_edited_at: string;
    }): EmrAction => ({
        type: EMR_ACTIONS.CONFLICT_DETECTED,
        payload: conflictData,
    }),

    conflictResolved: (
      data: Record<string, unknown> | null = null,
      rowVersion: number | null = null,
    ): EmrAction => ({
        type: EMR_ACTIONS.CONFLICT_RESOLVED,
        payload: { data, rowVersion },
    }),

    undo: (): EmrAction => ({ type: EMR_ACTIONS.UNDO }),
    redo: (): EmrAction => ({ type: EMR_ACTIONS.REDO }),
    resetDirty: (): EmrAction => ({ type: EMR_ACTIONS.RESET_DIRTY }),
};
