/**
 * EMR v2 Reducer - State management with undo/redo support
 * 
 * Actions:
 * - LOAD: Load EMR data from server
 * - SET_FIELD: Update a single field
 * - SAVE_START/SUCCESS/ERROR: Save lifecycle
 * - CONFLICT_DETECTED: Optimistic lock conflict
 * - UNDO/REDO: Navigate history
 */

// Action types
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
};

// Max history size for undo/redo (memory-conscious)
const MAX_HISTORY_SIZE = 50;

/**
 * Initial state shape
 */
export const initialState = {
    // EMR data
    emr: null,           // Full EMR record from server
    data: {},            // Current clinical data

    // Versioning
    version: 0,          // Current version number
    rowVersion: 0,       // Optimistic lock version

    // Status
    status: 'idle',      // idle | loading | saving | error
    isDirty: false,      // Has unsaved changes
    lastSaved: null,     // Last save timestamp

    // Conflict handling
    conflict: null,      // { serverData, serverVersion, lastEditedBy, lastEditedAt }

    // Undo/Redo (stores data snapshots only, not full state)
    history: [],         // Past states for undo
    future: [],          // Future states for redo

    // Error
    error: null,
};

/**
 * Add to history with size limit
 */
function pushHistory(history, data) {
    const newHistory = [...history, JSON.parse(JSON.stringify(data))];
    if (newHistory.length > MAX_HISTORY_SIZE) {
        return newHistory.slice(-MAX_HISTORY_SIZE);
    }
    return newHistory;
}

/**
 * Deep set a nested field value
 * e.g., setNestedValue(obj, 'diagnosis.main', 'headache')
 */
function setNestedValue(obj, path, value) {
    const keys = path.split('.');
    const result = { ...obj };
    let current = result;

    for (let i = 0; i < keys.length - 1; i++) {
        const key = keys[i];
        current[key] = current[key] ? { ...current[key] } : {};
        current = current[key];
    }

    current[keys[keys.length - 1]] = value;
    return result;
}

/**
 * EMR Reducer
 */
export function emrReducer(state, action) {
    switch (action.type) {
        // =========================================================================
        // LOAD - Initial load from server
        // =========================================================================
        case EMR_ACTIONS.LOAD:
            return {
                ...initialState,
                emr: action.payload.emr,
                data: action.payload.emr?.data || {},
                version: action.payload.emr?.version || 1,
                rowVersion: action.payload.emr?.row_version || 0,
                status: 'idle',
                lastSaved: action.payload.emr?.updated_at || null,
            };

        // =========================================================================
        // SET_FIELD - Update single field
        // =========================================================================
        case EMR_ACTIONS.SET_FIELD: {
            const { field, value } = action.payload;

            // Skip if value hasn't changed
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
                // Push current data to history for undo
                history: pushHistory(state.history, state.data),
                future: [], // Clear redo stack on new change
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
            const { emr } = action.payload;
            return {
                ...state,
                emr,
                version: emr.version,
                rowVersion: emr.row_version,
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
        case EMR_ACTIONS.CONFLICT_DETECTED:
            return {
                ...state,
                status: 'conflict',
                conflict: {
                    serverVersion: action.payload.current_version,
                    yourVersion: action.payload.your_version,
                    lastEditedBy: action.payload.last_edited_by,
                    lastEditedAt: action.payload.last_edited_at,
                },
            };

        // =========================================================================
        // CONFLICT_RESOLVED - User resolved conflict
        // =========================================================================
        case EMR_ACTIONS.CONFLICT_RESOLVED:
            return {
                ...state,
                status: 'idle',
                conflict: null,
                // If action includes new data, apply it
                ...(action.payload?.data && { data: action.payload.data }),
                ...(action.payload?.rowVersion && { rowVersion: action.payload.rowVersion }),
            };

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
    load: (emr) => ({
        type: EMR_ACTIONS.LOAD,
        payload: { emr },
    }),

    setField: (field, value) => ({
        type: EMR_ACTIONS.SET_FIELD,
        payload: { field, value },
    }),

    setNestedField: (path, value) => ({
        type: EMR_ACTIONS.SET_NESTED_FIELD,
        payload: { path, value },
    }),

    saveStart: () => ({
        type: EMR_ACTIONS.SAVE_START,
    }),

    saveSuccess: (emr) => ({
        type: EMR_ACTIONS.SAVE_SUCCESS,
        payload: { emr },
    }),

    saveError: (error) => ({
        type: EMR_ACTIONS.SAVE_ERROR,
        payload: { error },
    }),

    conflictDetected: (conflictData) => ({
        type: EMR_ACTIONS.CONFLICT_DETECTED,
        payload: conflictData,
    }),

    conflictResolved: (data = null, rowVersion = null) => ({
        type: EMR_ACTIONS.CONFLICT_RESOLVED,
        payload: { data, rowVersion },
    }),

    undo: () => ({ type: EMR_ACTIONS.UNDO }),

    redo: () => ({ type: EMR_ACTIONS.REDO }),

    resetDirty: () => ({ type: EMR_ACTIONS.RESET_DIRTY }),
};
