/**
 * useEMR - Core EMR v2 hook
 * 
 * Features:
 * - Load EMR by visit_id
 * - Save with optimistic locking (row_version)
 * - Conflict detection and handling
 * - Undo/redo support
 */

import { useReducer, useCallback, useEffect, useRef } from 'react';
import { emrReducer, initialState, emrActions } from '../reducers/emrReducer';
import { apiClient } from '../api/client';

// Generate client session ID for smart conflict resolution
const generateSessionId = () => {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

/**
 * useEMR Hook
 * 
 * @param {number} visitId - Visit ID to load EMR for
 * @param {Object} options - Configuration options
 * @param {boolean} options.autoLoad - Auto-load on mount (default: true)
 * @returns {Object} EMR state and actions
 */
export function useEMR(visitId, { autoLoad = true } = {}) {
    const [state, dispatch] = useReducer(emrReducer, initialState);
    const clientSessionId = useRef(generateSessionId());
    const abortControllerRef = useRef(null);

    // =========================================================================
    // LOAD EMR
    // =========================================================================
    const loadEMR = useCallback(async () => {
        if (!visitId) return;

        // Cancel any pending request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        try {
            const response = await apiClient.get(`/v2/emr/${visitId}`, {
                signal: abortControllerRef.current.signal,
            });
            dispatch(emrActions.load(response.data));
            return response.data;
        } catch (error) {
            if (error.name === 'AbortError' || error.code === 'ERR_CANCELED') {
                return; // Aborted, ignore
            }

            if (error.response?.status === 404) {
                // No EMR exists yet - start with empty
                dispatch(emrActions.load(null));
                return null;
            }

            console.error('Failed to load EMR:', error);
            dispatch(emrActions.saveError(error.message || 'Failed to load EMR'));
            throw error;
        }
    }, [visitId]);

    // =========================================================================
    // SAVE EMR
    // =========================================================================
    const saveEMR = useCallback(async (options = {}) => {
        const { isDraft = true, force = false } = options;

        dispatch(emrActions.saveStart());

        try {
            const payload = {
                data: state.data,
                row_version: force ? 0 : state.rowVersion, // 0 = skip lock check
                client_session_id: clientSessionId.current,
                is_draft: isDraft,
            };

            const response = await apiClient.post(`/v2/emr/${visitId}`, payload);
            dispatch(emrActions.saveSuccess(response.data));
            return response.data;
        } catch (error) {
            // Check for conflict (409)
            if (error.response?.status === 409) {
                const conflictData = error.response.data?.detail || error.response.data;
                dispatch(emrActions.conflictDetected(conflictData));
                return { conflict: true, ...conflictData };
            }

            // Check for signed EMR error (400)
            if (error.response?.status === 400 &&
                error.response.data?.detail?.includes('signed')) {
                dispatch(emrActions.saveError('EMR подписана. Используйте "Внести поправку".'));
                return { signed: true };
            }

            dispatch(emrActions.saveError(error.message || 'Ошибка сохранения'));
            throw error;
        }
    }, [visitId, state.data, state.rowVersion]);

    // =========================================================================
    // SIGN EMR
    // =========================================================================
    const signEMR = useCallback(async () => {
        dispatch(emrActions.saveStart());

        try {
            const payload = {
                data: state.data,
                row_version: state.rowVersion,
                client_session_id: clientSessionId.current,
            };

            const response = await apiClient.post(`/v2/emr/${visitId}/sign`, payload);
            dispatch(emrActions.saveSuccess(response.data));
            return response.data;
        } catch (error) {
            if (error.response?.status === 409) {
                const conflictData = error.response.data?.detail || error.response.data;
                dispatch(emrActions.conflictDetected(conflictData));
                return { conflict: true, ...conflictData };
            }

            dispatch(emrActions.saveError(error.message || 'Ошибка подписания'));
            throw error;
        }
    }, [visitId, state.data, state.rowVersion]);

    // =========================================================================
    // AMEND EMR
    // =========================================================================
    const amendEMR = useCallback(async (reason) => {
        if (!reason || reason.trim().length < 10) {
            const error = 'Причина поправки должна быть не менее 10 символов';
            dispatch(emrActions.saveError(error));
            return { error };
        }

        dispatch(emrActions.saveStart());

        try {
            const payload = {
                data: state.data,
                reason: reason.trim(),
                row_version: state.rowVersion,
            };

            const response = await apiClient.post(`/v2/emr/${visitId}/amend`, payload);
            dispatch(emrActions.saveSuccess(response.data));
            return response.data;
        } catch (error) {
            dispatch(emrActions.saveError(error.message || 'Ошибка внесения поправки'));
            throw error;
        }
    }, [visitId, state.data, state.rowVersion]);

    // =========================================================================
    // CONFLICT RESOLUTION
    // =========================================================================
    const reloadFromServer = useCallback(async () => {
        await loadEMR();
        dispatch(emrActions.conflictResolved());
    }, [loadEMR]);

    const forceOverwrite = useCallback(async () => {
        return saveEMR({ force: true });
    }, [saveEMR]);

    // =========================================================================
    // FIELD SETTERS
    // =========================================================================
    const setField = useCallback((field, value) => {
        dispatch(emrActions.setField(field, value));
    }, []);

    const setNestedField = useCallback((path, value) => {
        dispatch(emrActions.setNestedField(path, value));
    }, []);

    // =========================================================================
    // UNDO/REDO
    // =========================================================================
    const undo = useCallback(() => {
        dispatch(emrActions.undo());
    }, []);

    const redo = useCallback(() => {
        dispatch(emrActions.redo());
    }, []);

    const canUndo = state.history.length > 0;
    const canRedo = state.future.length > 0;

    // =========================================================================
    // AUTO-LOAD
    // =========================================================================
    useEffect(() => {
        if (autoLoad && visitId) {
            loadEMR();
        }

        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, [autoLoad, visitId, loadEMR]);

    // =========================================================================
    // RETURN
    // =========================================================================
    return {
        // State
        emr: state.emr,
        data: state.data,
        version: state.version,
        rowVersion: state.rowVersion,
        status: state.status,
        isDirty: state.isDirty,
        lastSaved: state.lastSaved,
        conflict: state.conflict,
        error: state.error,

        // Computed
        isLoading: state.status === 'loading',
        isSaving: state.status === 'saving',
        hasConflict: state.status === 'conflict',
        isSigned: state.emr?.status === 'signed',
        isAmended: state.emr?.status === 'amended',
        canUndo,
        canRedo,

        // Actions
        loadEMR,
        saveEMR,
        signEMR,
        amendEMR,
        setField,
        setNestedField,
        undo,
        redo,

        // Conflict resolution
        reloadFromServer,
        forceOverwrite,

        // Session
        clientSessionId: clientSessionId.current,
    };
}

export default useEMR;
