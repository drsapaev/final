/**
 * useEMR - Core EMR v2 hook
 * 
 * Features:
 * - Load EMR by visit_id
 * - Save with optimistic locking (row_version)
 * - Conflict detection and handling
 * - Undo/redo support
 */

import { useReducer, useCallback, useEffect, useRef, useState } from 'react';
import { emrReducer, initialState, emrActions } from '../reducers/emrReducer';
import { apiClient } from '../api/client';
import logger from '../utils/logger';
import { buildInitialEMRData, normalizeEMRData } from '../utils/emrSpecialty';
import type { EMRApiError, EMRStatus } from '../types/domain/emr';

let fallbackSessionCounter = 0;

// Generate client session ID for smart conflict resolution
const generateSessionId = () => {
    const browserCrypto = globalThis.crypto;

    if (browserCrypto?.randomUUID) {
        return browserCrypto.randomUUID();
    }

    if (browserCrypto?.getRandomValues) {
        const randomBytes = new Uint8Array(16);
        browserCrypto.getRandomValues(randomBytes);
        randomBytes[6] = randomBytes[6] & 0x0f | 0x40;
        randomBytes[8] = randomBytes[8] & 0x3f | 0x80;
        const hex = Array.from(randomBytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
        return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }

    fallbackSessionCounter += 1;
    return `${Date.now().toString(36)}-${fallbackSessionCounter.toString(36)}`;
};

const emrCache = new Map();
const isAccessDeniedStatus = (status: EMRStatus) => status === 401 || status === 403;

const getAccessDeniedMessage = (error: EMRApiError): string => (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    'Нет доступа к EMR для текущей учётной записи'
);

/**
 * useEMR Hook
 * 
 * @param {number} visitId - Visit ID to load EMR for
 * @param {Object} options - Configuration options
 * @param {boolean} options.autoLoad - Auto-load on mount (default: true)
 * @param {string} options.specialty - Canonical specialty for this EMR flow
 * @returns {Object} EMR state and actions
 */
export function useEMR(visitId, { autoLoad = true, specialty = 'general' } = {}) {
    const [state, dispatch] = useReducer(emrReducer, initialState);
    const clientSessionId = useRef(generateSessionId());
    const isMountedRef = useRef(true);
    const writeAccessDeniedRef = useRef(false);
    const [writeAccessDenied, setWriteAccessDenied] = useState(false);

    useEffect(() => {
        isMountedRef.current = true;
        return () => {
            isMountedRef.current = false;
        };
    }, []);

    useEffect(() => {
        writeAccessDeniedRef.current = false;
        setWriteAccessDenied(false);
    }, [visitId, specialty]);

    const cacheKey = `${visitId || ''}:${specialty}`;

    const handleAccessDenied = useCallback((operation: string, error: EMRApiError) => {
        const status = error?.response?.status;
        const message = getAccessDeniedMessage(error);
        logger.warn(`[FIX:EMR${status}] ${operation} blocked by access control`, {
            visitId,
            specialty,
            status,
            message
        });
        writeAccessDeniedRef.current = true;
        setWriteAccessDenied(true);
        dispatch(emrActions.saveError(message));
        return {
            accessDenied: true,
            status,
            message
        };
    }, [specialty, visitId]);

    // =========================================================================
    // LOAD EMR
    // =========================================================================
    const loadEMR = useCallback(async (forceRefresh = false) => {
        if (!visitId) return;

        const cachedEntry = emrCache.get(cacheKey);
        if (!forceRefresh) {
            if (cachedEntry?.data) {
                if (isMountedRef.current) {
                    dispatch(emrActions.load(cachedEntry.data));
                }
                return cachedEntry.data;
            }

            if (cachedEntry?.promise) {
                return cachedEntry.promise;
            }
        } else if (cachedEntry?.promise) {
            return cachedEntry.promise;
        }

        const loadPromise = (async () => {
            try {
                const response = await apiClient.get(`/v2/emr/${visitId}`, {
                    silent: true,
                    validateStatus: (status) => status === 404 || (status >= 200 && status < 300),
                });

                if (response.status === 404) {
                    logger.info('[FIX:EMR404] EMR not found, initializing empty draft', {
                        visitId,
                        specialty,
                    });
                    writeAccessDeniedRef.current = false;
                    setWriteAccessDenied(false);
                    const emptyEmr = {
                        data: buildInitialEMRData(specialty),
                        version: 1,
                        row_version: 0,
                        status: 'draft',
                    };
                    emrCache.set(cacheKey, { data: emptyEmr, promise: null });
                    if (isMountedRef.current) {
                        dispatch(emrActions.load(emptyEmr));
                    }
                    return emptyEmr;
                }

                const normalizedEmr = {
                    ...response.data,
                    data: normalizeEMRData(response.data?.data, specialty),
                };
                writeAccessDeniedRef.current = false;
                setWriteAccessDenied(false);
                emrCache.set(cacheKey, { data: normalizedEmr, promise: null });
                if (isMountedRef.current) {
                    dispatch(emrActions.load(normalizedEmr));
                }
                return normalizedEmr;
            } catch (error) {
                if (isAccessDeniedStatus(error?.response?.status)) {
                    emrCache.delete(cacheKey);
                    return handleAccessDenied('loadEMR', error);
                }

                logger.error('Failed to load EMR:', error);
                emrCache.delete(cacheKey);
                if (isMountedRef.current) {
                    dispatch(emrActions.saveError(error.message || 'Failed to load EMR'));
                }
                throw error;
            }
        })();

        emrCache.set(cacheKey, {
            data: cachedEntry?.data || null,
            promise: loadPromise,
        });

        try {
            return await loadPromise;
        } finally {
            const currentEntry = emrCache.get(cacheKey);
            if (currentEntry?.promise === loadPromise) {
                emrCache.set(cacheKey, {
                    data: currentEntry.data || null,
                    promise: null,
                });
            }
        }
    }, [cacheKey, handleAccessDenied, specialty, visitId]);

    // =========================================================================
    // SAVE EMR
    // =========================================================================
    const saveEMR = useCallback(async (options: Record<string, unknown> = {}) => {
        const { isDraft = true, force = false } = options;

        if (writeAccessDeniedRef.current) {
            logger.info('[FIX:EMR403] saveEMR skipped because access was already denied', {
                visitId,
                specialty,
            });
            return {
                accessDenied: true,
                status: 403,
                message: getAccessDeniedMessage(undefined)
            };
        }

        dispatch(emrActions.saveStart());

        try {
            const payload = {
                data: normalizeEMRData(state.data, specialty),
                row_version: force ? 0 : state.rowVersion, // 0 = skip lock check
                client_session_id: clientSessionId.current,
                is_draft: isDraft,
            };

            const response = await apiClient.post(`/v2/emr/${visitId}`, payload);
            dispatch(emrActions.saveSuccess(response.data));
            return response.data;
        } catch (error) {
            if (isAccessDeniedStatus(error?.response?.status)) {
                return handleAccessDenied('saveEMR', error);
            }

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
    }, [handleAccessDenied, specialty, visitId, state.data, state.rowVersion]);

    // =========================================================================
    // SIGN EMR
    // =========================================================================
    const signEMR = useCallback(async () => {
        if (writeAccessDeniedRef.current) {
            logger.info('[FIX:EMR403] signEMR skipped because access was already denied', {
                visitId,
                specialty,
            });
            return {
                accessDenied: true,
                status: 403,
                message: getAccessDeniedMessage(undefined)
            };
        }

        dispatch(emrActions.saveStart());

        try {
            const payload = {
                data: normalizeEMRData(state.data, specialty),
                row_version: state.rowVersion,
                client_session_id: clientSessionId.current,
            };

            const response = await apiClient.post(`/v2/emr/${visitId}/sign`, payload);
            dispatch(emrActions.saveSuccess(response.data));
            return response.data;
        } catch (error) {
            if (isAccessDeniedStatus(error?.response?.status)) {
                return handleAccessDenied('signEMR', error);
            }

            if (error.response?.status === 409) {
                const conflictData = error.response.data?.detail || error.response.data;
                dispatch(emrActions.conflictDetected(conflictData));
                return { conflict: true, ...conflictData };
            }

            dispatch(emrActions.saveError(error.message || 'Ошибка подписания'));
            throw error;
        }
    }, [handleAccessDenied, specialty, visitId, state.data, state.rowVersion]);

    // =========================================================================
    // AMEND EMR
    // =========================================================================
    const amendEMR = useCallback(async (reason: string) => {
        if (!reason || reason.trim().length < 10) {
            const error = 'Причина поправки должна быть не менее 10 символов';
            dispatch(emrActions.saveError(error));
            return { error };
        }

        if (writeAccessDeniedRef.current) {
            logger.info('[FIX:EMR403] amendEMR skipped because access was already denied', {
                visitId,
                specialty,
            });
            return {
                accessDenied: true,
                status: 403,
                message: getAccessDeniedMessage(undefined)
            };
        }

        dispatch(emrActions.saveStart());

        try {
            const payload = {
                data: normalizeEMRData(state.data, specialty),
                reason: reason.trim(),
                row_version: state.rowVersion,
            };

            const response = await apiClient.post(`/v2/emr/${visitId}/amend`, payload);
            dispatch(emrActions.saveSuccess(response.data));
            return response.data;
        } catch (error) {
            if (isAccessDeniedStatus(error?.response?.status)) {
                return handleAccessDenied('amendEMR', error);
            }

            dispatch(emrActions.saveError(error.message || 'Ошибка внесения поправки'));
            throw error;
        }
    }, [handleAccessDenied, specialty, visitId, state.data, state.rowVersion]);

    // =========================================================================
    // CONFLICT RESOLUTION
    // =========================================================================
    const reloadFromServer = useCallback(async () => {
        const result = await loadEMR(true);
        if (result?.accessDenied) {
            return result;
        }
        dispatch(emrActions.conflictResolved());
    }, [loadEMR]);

    const forceOverwrite = useCallback(async () => {
        return saveEMR({ force: true });
    }, [saveEMR]);

    // =========================================================================
    // FIELD SETTERS
    // =========================================================================
    const setField = useCallback((field: string, value: unknown) => {
        dispatch(emrActions.setField(field, value));
    }, []);

    const setNestedField = useCallback((path: string, value: unknown) => {
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
        accessDenied: writeAccessDenied,

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
