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
import { getState as getAuthState } from '../stores/auth';
import type { EMRApiError, EMRHttpStatus } from '../types/domain/emr';

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

// EMRCACHE-FE-001 (audit 3886 round 18): the module-global EMR cache holds
// clinical PHI, so it must be scoped to the authenticated principal. The key
// carries the principal id; when the principal changes (logout / account
// switch without a full page reload) every stale entry is dropped so a
// second principal can never receive the first principal's cached records.
const emrCache = new Map();
let emrCachePrincipal: string | null = null;

const getCachePrincipal = (): string | null => {
    try {
        const profile = getAuthState()?.profile;
        const id = profile?.id;
        return id === null || id === undefined ? null : String(id);
    } catch {
        return null;
    }
};

/** Scope the cache to the current principal, clearing it on a principal swap. */
const syncCachePrincipal = (): void => {
    const principal = getCachePrincipal();
    if (principal !== emrCachePrincipal) {
        emrCache.clear();
        emrCachePrincipal = principal;
    }
};

const isAccessDeniedStatus = (status: EMRHttpStatus | undefined) => status === 401 || status === 403;

const getAccessDeniedMessage = (error?: EMRApiError): string => {
    const detail = error?.response?.data?.detail;
    if (typeof detail === 'string' && detail) return detail;
    if (typeof detail === 'object' && detail?.message) return detail.message;
    return error?.response?.data?.message ||
        error?.message ||
        'Нет доступа к EMR для текущей учётной записи';
};

/** Coerce a caught value (typed `unknown` in strict mode) to EMRApiError. */
const toEMRApiError = (err: unknown): EMRApiError => {
    if (err && typeof err === 'object' && ('response' in err || 'message' in err)) {
        return err as EMRApiError;
    }
    return { message: String(err) };
};

/**
 * useEMR Hook
 *
 * @param {number} visitId - Visit ID to load EMR for
 * @param {Object} options - Configuration options
 * @param {boolean} options.autoLoad - Auto-load on mount (default: true)
 * @param {string} options.specialty - Canonical specialty for this EMR flow
 * @returns {Object} EMR state and actions
 */
export function useEMR(visitId: number | string | null, { autoLoad = true, specialty = 'general' }: { autoLoad?: boolean; specialty?: string } = {}) {
    const [state, dispatch] = useReducer(emrReducer, initialState);
    const clientSessionId = useRef(generateSessionId());
    const isMountedRef = useRef(true);
    const writeAccessDeniedRef = useRef(false);
    const [writeAccessDenied, setWriteAccessDenied] = useState(false);
    // EMRSIGN-FE-001 (audit 3886 round 17): save/sign/amend callbacks below
    // used to serialize the `state.data` captured in their closure at the
    // render they were created in. When a save-and-sign started at snapshot A
    // and the doctor (or any programmatic edit) changed the document to B
    // while the save request was in flight, the follow-up SIGN request still
    // serialized the stale A and finalized it as the signed clinical record.
    // This ref always holds the latest reducer state so every write request
    // carries the document that is on screen at the moment the request is
    // built, never a stale render snapshot.
    const stateRef = useRef(state);
    stateRef.current = state;

    // EMRCTX-FE-001 (audit 3886 round 18): visit-generation guard. When the
    // canonical visitId changes on a still-mounted hook, the epoch bumps and
    // the reducer is hard-reset; every async resolution (cache hit promises,
    // GET responses, save ACKs, conflict payloads) captured under an older
    // epoch is dropped, so a late response of the previous visit can never
    // overwrite the new visit's clinical state.
    const visitEpochRef = useRef(0);
    const visitIdentityRef = useRef<number | string | null>(visitId);

    useEffect(() => {
        isMountedRef.current = true;
        return () => {
            isMountedRef.current = false;
        };
    }, []);

    useEffect(() => {
        if (visitIdentityRef.current !== visitId) {
            visitIdentityRef.current = visitId;
            visitEpochRef.current += 1;
            writeAccessDeniedRef.current = false;
            setWriteAccessDenied(false);
            // Hard reset: no data, no dirty flag, no history, no conflict of
            // the previous visit may survive into the new visit's editor.
            dispatch(emrActions.contextReset());
        }
    }, [visitId]);

    useEffect(() => {
        writeAccessDeniedRef.current = false;
        setWriteAccessDenied(false);
    }, [specialty]);

    // EMRCACHE-FE-001: principal-scoped cache key (cleared on principal swap)
    syncCachePrincipal();
    const cacheKey = `${emrCachePrincipal ?? 'anonymous'}:${visitId || ''}:${specialty}`;
    const canUseCache = emrCachePrincipal !== null;

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
        // EMRCTX-FE-001: every async resolution below must be attributed to
        // the visit generation it was started for — a late resolution of a
        // previous visit (cache promise or GET) is dropped.
        const epoch = visitEpochRef.current;
        const stillCurrentVisit = () => isMountedRef.current && visitEpochRef.current === epoch;
        // EMRCACHE-FE-001: without an authenticated principal the cache is
        // bypassed entirely (no reads, no writes) — anonymous state must
        // never serve or persist clinical records.
        const cachedEntry = canUseCache ? emrCache.get(cacheKey) : undefined;
        if (!forceRefresh) {
            if (cachedEntry?.data) {
                if (stillCurrentVisit()) {
                    dispatch(emrActions.load(cachedEntry.data));
                }
                return cachedEntry.data;
            }

            if (cachedEntry?.promise) {
                // audit/phase-final, BS-18: dispatch to this instance when promise resolves.
                cachedEntry.promise.then((result: unknown) => {
                    if (result && !forceRefresh && stillCurrentVisit()) {
                        dispatch(emrActions.load(result as Record<string, unknown>));
                    }
                }).catch(() => {});
                return cachedEntry.promise;
            }
        } else if (cachedEntry?.promise) {
            cachedEntry.promise.then((result: unknown) => {
                if (result && stillCurrentVisit()) {
                    dispatch(emrActions.load(result as Record<string, unknown>));
                }
            }).catch(() => {});
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
                    // EMRCACHE-FE-002 (audit 3886 round 18): a 404 placeholder
                    // is NOT a persisted canonical record — never cache it as
                    // authoritative data. Successful writes now refresh the
                    // cache (see saveEMR/signEMR/amendEMR), so a remount after
                    // a save must show the saved content, not this empty draft.
                    if (stillCurrentVisit()) {
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
                if (canUseCache) {
                    emrCache.set(cacheKey, { data: normalizedEmr, promise: null });
                }
                if (stillCurrentVisit()) {
                    dispatch(emrActions.load(normalizedEmr));
                }
                return normalizedEmr;
            } catch (error) {
                const apiError = toEMRApiError(error);
                if (isAccessDeniedStatus(apiError?.response?.status)) {
                    emrCache.delete(cacheKey);
                    // RETRO-3930-01 (post-merge review of PR 3930): a 403 that
                    // belongs to a PREVIOUS visit must not lock or error the
                    // current visit's editor — guard the denial with the
                    // request identity, like the success path.
                    if (!stillCurrentVisit()) {
                        logger.warn('[FIX:EMR403] stale load denial dropped: visit switched before the rejection arrived', {
                            visitId,
                            specialty,
                            status: apiError?.response?.status,
                        });
                        return {
                            accessDenied: true,
                            status: apiError?.response?.status,
                            message: getAccessDeniedMessage(apiError),
                            stale: true,
                        };
                    }
                    return handleAccessDenied('loadEMR', apiError);
                }

                logger.error('Failed to load EMR:', error);
                emrCache.delete(cacheKey);
                // RETRO-3930-01: same guard for late failures of the previous
                // visit — no stale error state, no stale toast, no rejection
                // into callers that already moved on to the new visit. The
                // outcome is an EXPLICIT stale marker (not a fake success) so
                // continuations like reloadFromServer can distinguish a
                // dropped load from a completed one.
                if (!stillCurrentVisit()) {
                    return { stale: true };
                }
                if (isMountedRef.current) {
                    dispatch(emrActions.saveError(apiError.message || 'Failed to load EMR'));
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
        const epoch = visitEpochRef.current;
        const stillCurrentVisit = () => isMountedRef.current && visitEpochRef.current === epoch;

        try {
            const payload = {
                // EMRSIGN-FE-001: serialize the LATEST document, not the
                // closure snapshot from the render this callback was created in.
                data: normalizeEMRData(stateRef.current.data, specialty),
                row_version: force ? 0 : stateRef.current.rowVersion, // 0 = skip lock check
                client_session_id: clientSessionId.current,
                is_draft: isDraft,
            };

            const response = await apiClient.post(`/v2/emr/${visitId}`, payload);
            // EMRCACHE-FE-002: refresh the cache with the authoritative
            // server record so a remount shows the saved content/version.
            if (canUseCache) {
                emrCache.set(cacheKey, {
                    data: { ...response.data, data: normalizeEMRData(response.data?.data, specialty) },
                    promise: null,
                });
            }
            if (stillCurrentVisit()) {
                dispatch(emrActions.saveSuccess(response.data));
            }
            return response.data;
        } catch (error) {
            const apiError = toEMRApiError(error);
            if (isAccessDeniedStatus(apiError?.response?.status)) {
                // RETRO-3930-01: a late denial of a previous visit must not
                // lock the current visit's editor.
                if (!stillCurrentVisit()) {
                    logger.warn('[FIX:EMR403] stale save denial dropped: visit switched before the rejection arrived', {
                        visitId,
                        specialty,
                        status: apiError?.response?.status,
                    });
                    return {
                        accessDenied: true,
                        status: apiError?.response?.status,
                        message: getAccessDeniedMessage(apiError),
                        stale: true,
                    };
                }
                return handleAccessDenied('saveEMR', apiError);
            }

            // Check for conflict (409)
            if (apiError.response?.status === 409) {
                const conflictData = (apiError.response.data?.detail || apiError.response.data) as {
                    current_version: unknown;
                    your_version: unknown;
                    last_edited_by: string;
                    last_edited_at: string;
                    [key: string]: unknown;
                };
                if (stillCurrentVisit()) {
                    dispatch(emrActions.conflictDetected(conflictData));
                }
                return { conflict: true, ...conflictData };
            }

            // Check for signed EMR error (400)
            if (apiError.response?.status === 400) {
                const detail = apiError.response.data?.detail;
                if (typeof detail === 'string' && detail.includes('signed')) {
                    if (stillCurrentVisit()) {
                        dispatch(emrActions.saveError('EMR подписана. Используйте "Внести поправку".'));
                    }
                    return { signed: true };
                }
            }

            if (!stillCurrentVisit()) {
                // RETRO-3930-01: late failure of a previous visit — no stale
                // error state for the current one.
                return null;
            }
            dispatch(emrActions.saveError(apiError.message || 'Ошибка сохранения'));
            throw error;
        }
    }, [handleAccessDenied, specialty, visitId]);

    // =========================================================================
    // SIGN EMR
    // =========================================================================
    const signEMR = useCallback(async (options: { rowVersion?: number } = {}) => {
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
        const epoch = visitEpochRef.current;
        const stillCurrentVisit = () => isMountedRef.current && visitEpochRef.current === epoch;

        try {
            const payload = {
                // EMRSIGN-FE-001: the signed revision must equal the latest
                // explicitly approved clinical snapshot — serialize the live
                // document, never a stale render closure.
                data: normalizeEMRData(stateRef.current.data, specialty),
                row_version: options.rowVersion ?? stateRef.current.rowVersion,
                client_session_id: clientSessionId.current,
            };

            const response = await apiClient.post(`/v2/emr/${visitId}/sign`, payload);
            // EMRCACHE-FE-002: keep the cache in sync with the signed record.
            if (canUseCache) {
                emrCache.set(cacheKey, {
                    data: { ...response.data, data: normalizeEMRData(response.data?.data, specialty) },
                    promise: null,
                });
            }
            if (stillCurrentVisit()) {
                dispatch(emrActions.saveSuccess(response.data));
            }
            return response.data;
        } catch (error) {
            const apiError = toEMRApiError(error);
            if (isAccessDeniedStatus(apiError?.response?.status)) {
                // RETRO-3930-01: guard the sign denial with the request
                // identity — a previous visit's late 403 must not lock the
                // current editor.
                if (!stillCurrentVisit()) {
                    logger.warn('[FIX:EMR403] stale sign denial dropped: visit switched before the rejection arrived', {
                        visitId,
                        specialty,
                        status: apiError?.response?.status,
                    });
                    return {
                        accessDenied: true,
                        status: apiError?.response?.status,
                        message: getAccessDeniedMessage(apiError),
                        stale: true,
                    };
                }
                return handleAccessDenied('signEMR', apiError);
            }

            if (apiError.response?.status === 409) {
                const conflictData = (apiError.response.data?.detail || apiError.response.data) as {
                    current_version: unknown;
                    your_version: unknown;
                    last_edited_by: string;
                    last_edited_at: string;
                    [key: string]: unknown;
                };
                if (stillCurrentVisit()) {
                    dispatch(emrActions.conflictDetected(conflictData));
                }
                return { conflict: true, ...conflictData };
            }

            if (!stillCurrentVisit()) {
                // RETRO-3930-01: late failure of a previous visit — no stale
                // error state for the current one.
                return null;
            }
            dispatch(emrActions.saveError(apiError.message || 'Ошибка подписания'));
            throw error;
        }
    }, [handleAccessDenied, specialty, visitId]);

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
        const epoch = visitEpochRef.current;
        const stillCurrentVisit = () => isMountedRef.current && visitEpochRef.current === epoch;

        try {
            const payload = {
                // EMRSIGN-FE-001: amendments serialize the live document too.
                data: normalizeEMRData(stateRef.current.data, specialty),
                reason: reason.trim(),
                row_version: stateRef.current.rowVersion,
            };

            const response = await apiClient.post(`/v2/emr/${visitId}/amend`, payload);
            // EMRCACHE-FE-002: keep the cache in sync with the amended record.
            if (canUseCache) {
                emrCache.set(cacheKey, {
                    data: { ...response.data, data: normalizeEMRData(response.data?.data, specialty) },
                    promise: null,
                });
            }
            if (stillCurrentVisit()) {
                dispatch(emrActions.saveSuccess(response.data));
            }
            return response.data;
        } catch (error) {
            const apiError = toEMRApiError(error);
            if (isAccessDeniedStatus(apiError?.response?.status)) {
                // RETRO-3930-01: guard the amend denial with the request
                // identity as well.
                if (!stillCurrentVisit()) {
                    logger.warn('[FIX:EMR403] stale amend denial dropped: visit switched before the rejection arrived', {
                        visitId,
                        specialty,
                        status: apiError?.response?.status,
                    });
                    return {
                        accessDenied: true,
                        status: apiError?.response?.status,
                        message: getAccessDeniedMessage(apiError),
                        stale: true,
                    };
                }
                return handleAccessDenied('amendEMR', apiError);
            }

            if (!stillCurrentVisit()) {
                // RETRO-3930-01: late failure of a previous visit — no stale
                // error state for the current one.
                return null;
            }
            dispatch(emrActions.saveError(apiError.message || 'Ошибка внесения поправки'));
            throw error;
        }
    }, [handleAccessDenied, specialty, visitId]);

    // =========================================================================
    // CONFLICT RESOLUTION
    // =========================================================================
    const reloadFromServer = useCallback(async () => {
        const result = await loadEMR(true);
        if (result?.accessDenied) {
            return result;
        }
        // RETRO-3930-01 follow-up (Codex review on round 22): a load that was
        // DROPPED because the visit switched mid-reload must not resolve the
        // CURRENT visit's conflict — the «discard» continuation belongs to
        // the visit that started it, and dispatching here would clear the
        // new visit's dirty flag and undo history for edits it never saw.
        if (!result || (result as { stale?: boolean }).stale) {
            return result;
        }
        // EMRCONFLICT-FE-001 (audit 3886 round 17): this is the explicit
        // «discard my edits» path. The LOAD above already replaced the whole
        // reducer state with the canonical server snapshot (fresh history,
        // clean dirty flag). Resolving as 'discard' keeps that clean state —
        // the old code unconditionally marked the state dirty, so the
        // autosave immediately wrote the just-loaded server content back as
        // a brand-new revision the doctor never asked for.
        dispatch(emrActions.conflictResolved(null, null, 'discard'));
    }, [loadEMR]);

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

        // Session
        clientSessionId: clientSessionId.current,
    };
}

export default useEMR;
