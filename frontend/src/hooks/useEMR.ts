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
import type { EMRApiError } from '../types/domain/emr';

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

export function invalidateEMRCache(visitId: string | number) {
    syncCachePrincipal();
    const prefix = `${emrCachePrincipal ?? 'anonymous'}:${visitId}:`;
    for (const key of emrCache.keys()) {
        if (key.startsWith(prefix)) emrCache.delete(key);
    }
}

const PATIENT_CONTEXT_CHANGED = 'PATIENT_CONTEXT_CHANGED';

const isPatientContextMismatch = (error?: EMRApiError): boolean => {
    const detail = error?.response?.data?.detail;
    return error?.response?.status === 409 && typeof detail === 'object'
        && detail !== null && 'code' in detail && detail.code === PATIENT_CONTEXT_CHANGED;
};

const isAccessDenied = (error: EMRApiError): boolean => {
    const status = error.response?.status;
    return status === 401 || status === 403 || isPatientContextMismatch(error);
};

const getAccessDeniedMessage = (error?: EMRApiError): string => {
    if (isPatientContextMismatch(error)) return PATIENT_CONTEXT_CHANGED;
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

/** RETRO-3930-01 follow-up 2 (Codex review on round 22): a shared cache
 * promise may resolve with a NON-RECORD outcome marker — { stale: true } for
 * a request dropped by a visit switch, or { accessDenied, ... } for a denied
 * one. Those outcomes belong to the subscriber that started the request; a
 * subscriber that JOINS the cached promise must only ever dispatch a real
 * EMR record, never a marker (which would load an empty clinical document
 * and clear the current dirty flag and undo history). */
const isEmrRecord = (value: unknown): value is Record<string, unknown> =>
    Boolean(value && typeof value === 'object' && (value as Record<string, unknown>).data);

/**
 * useEMR Hook
 *
 * @param {number} visitId - Visit ID to load EMR for
 * @param {Object} options - Configuration options
 * @param {boolean} options.autoLoad - Auto-load on mount (default: true)
 * @param {string} options.specialty - Canonical specialty for this EMR flow
 * @returns {Object} EMR state and actions
 */
export function useEMR(
    visitId: number | string | null,
    { autoLoad = true, specialty = 'general', patientId }: {
        autoLoad?: boolean; specialty?: string; patientId?: string | number | null;
    } = {},
) {
    const selectedPatientId = Number(patientId);
    const expectedPatientId = Number.isSafeInteger(selectedPatientId) && selectedPatientId > 0 ? selectedPatientId : null;
    const [state, dispatch] = useReducer(emrReducer, initialState);
    const clientSessionId = useRef(generateSessionId());
    const isMountedRef = useRef(true);
    const writeAccessDeniedRef = useRef(false);
    const [writeAccessDenied, setWriteAccessDenied] = useState(false);
    const patientContextChangedRef = useRef(false);
    const [patientContextChanged, setPatientContextChanged] = useState(false);
    const clearPatientContextChanged = useCallback(() => {
        patientContextChangedRef.current = false;
        setPatientContextChanged(false);
    }, []);
    // RETRO-4007-01 (post-merge re-review of 4007): the server finalized the
    // record (a structured FINALIZED_STATE 409 or a legacy signed HTTP 400)
    // while the LOCAL editor still held the in_progress draft. The local
    // isSigned/isAmended flags stay false in this window, so the amendment
    // affordance (which only the signed/amended toolbar branch renders) was
    // unreachable exactly when the UI told the doctor to use it. The marker
    // mirrors the writeAccessDenied pattern (ref for the callbacks + state
    // for the consumer) and is cleared by a reload, an amendment, a visit
    // switch or a specialty change — never by further local edits (the
    // unsaved draft is retained, not auto-discarded).
    const serverFinalizedRef = useRef(false);
    const [serverFinalized, setServerFinalized] = useState(false);
    // Идентичность стабильна ([] — ref-гарды): флип state не пересоздаёт
    // коллбеки, иначе эффекты визита/specialty перезапускались бы на каждом
    // маркере и очищали его (бесконечный флип).
    const clearServerFinalized = useCallback(() => {
        if (serverFinalizedRef.current) {
            serverFinalizedRef.current = false;
            setServerFinalized(false);
        }
    }, []);
    const markServerFinalized = useCallback(() => {
        serverFinalizedRef.current = true;
        setServerFinalized(true);
    }, []);
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
    const patientIdentityRef = useRef(expectedPatientId);
    const draftSaveEpochRef = useRef<number | null>(null);
    // An edit can be queued in React before stateRef reflects it. A refresh
    // must yield to those edits and to writes started while its GET is pending.
    const documentGenerationRef = useRef(0);

    useEffect(() => {
        isMountedRef.current = true;
        return () => {
            isMountedRef.current = false;
        };
    }, []);

    useEffect(() => {
        if (visitIdentityRef.current !== visitId || patientIdentityRef.current !== expectedPatientId) {
            visitIdentityRef.current = visitId;
            patientIdentityRef.current = expectedPatientId;
            visitEpochRef.current += 1;
            writeAccessDeniedRef.current = false;
            setWriteAccessDenied(false);
            clearPatientContextChanged();
            clearServerFinalized();
            // Hard reset: no data, no dirty flag, no history, no conflict of
            // the previous visit may survive into the new visit's editor.
            dispatch(emrActions.contextReset());
        }
    }, [visitId, expectedPatientId, clearPatientContextChanged, clearServerFinalized]);

    useEffect(() => {
        if (!patientContextChangedRef.current) {
            writeAccessDeniedRef.current = false;
            setWriteAccessDenied(false);
        }
        clearServerFinalized();
    }, [specialty, clearServerFinalized]);

    // EMRCACHE-FE-001: principal-scoped cache key (cleared on principal swap)
    syncCachePrincipal();
    const cachePrincipal = emrCachePrincipal;
    const cacheKey = `${cachePrincipal ?? 'anonymous'}:${visitId || ''}:${expectedPatientId ?? ''}:${specialty}`;
    const canUseCache = cachePrincipal !== null;

    const handlePatientContextChanged = useCallback(() => {
        if (visitId !== null) invalidateEMRCache(visitId);
        visitEpochRef.current += 1;
        writeAccessDeniedRef.current = true;
        setWriteAccessDenied(true);
        patientContextChangedRef.current = true;
        setPatientContextChanged(true);
        clearServerFinalized();
        dispatch(emrActions.contextReset());
        return { accessDenied: true, status: 409, message: PATIENT_CONTEXT_CHANGED };
    }, [visitId, clearServerFinalized]);

    const handleAccessDenied = useCallback((operation: string, error: EMRApiError) => {
        if (isPatientContextMismatch(error)) return handlePatientContextChanged();
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
    }, [handlePatientContextChanged, specialty, visitId]);

    // =========================================================================
    // LOAD EMR
    // =========================================================================
    const loadEMR = useCallback(async (forceRefresh = false) => {
        if (!visitId) return;
        // EMRCTX-FE-001: every async resolution below must be attributed to
        // the visit generation it was started for — a late resolution of a
        // previous visit (cache promise or GET) is dropped.
        const epoch = visitEpochRef.current;
        const stillCurrentVisit = () => isMountedRef.current
            && visitEpochRef.current === epoch && getCachePrincipal() === cachePrincipal;
        if (forceRefresh && draftSaveEpochRef.current === epoch) {
            return { stale: true };
        }
        const generation = documentGenerationRef.current;
        const stillCurrentSnapshot = () => stillCurrentVisit() && documentGenerationRef.current === generation;
        const applySnapshot = <T,>(result: T) => {
            if (result && typeof result === 'object' && 'message' in result
                && result.message === PATIENT_CONTEXT_CHANGED && stillCurrentVisit()) {
                return handlePatientContextChanged();
            }
            if (!isEmrRecord(result)) return result;
            if (!stillCurrentSnapshot()) {
                return { stale: true };
            }
            if (patientContextChangedRef.current && (
                !(Number(result.id) > 0 && Number(result.row_version) > 0)
                || String(result.visit_id) !== String(visitId)
            )) {
                return { accessDenied: true, status: 409, message: PATIENT_CONTEXT_CHANGED };
            }
            if (expectedPatientId !== null && result.id && Number(result.patient_id) !== expectedPatientId) {
                return handlePatientContextChanged();
            }
            writeAccessDeniedRef.current = false;
            setWriteAccessDenied(false);
            clearPatientContextChanged();
            clearServerFinalized();
            dispatch(emrActions.load(result));
            return result;
        };
        // EMRCACHE-FE-001: without an authenticated principal the cache is
        // bypassed entirely (no reads, no writes) — anonymous state must
        // never serve or persist clinical records.
        const cachedEntry = canUseCache ? emrCache.get(cacheKey) : undefined;
        if (!forceRefresh && !writeAccessDeniedRef.current && cachedEntry?.data) {
            if (stillCurrentVisit()) {
                dispatch(emrActions.load(cachedEntry.data));
            }
            return cachedEntry.data;
        }
        if (cachedEntry?.promise) {
            return applySnapshot(await cachedEntry.promise);
        }

        const pendingEntry = { data: cachedEntry?.data || null, promise: null as Promise<unknown> | null };
        const loadPromise = (async () => {
            try {
                const response = await apiClient.get(`/v2/emr/${visitId}`, {
                    silent: true,
                    validateStatus: (status) => status === 404 || (status >= 200 && status < 300),
                });

                const currentEntry = emrCache.get(cacheKey);
                // Prefer a newer write that has already replaced this GET.
                if (canUseCache && currentEntry && currentEntry !== pendingEntry) {
                    return !currentEntry.promise && currentEntry.data ? currentEntry.data : { stale: true };
                }
                if (response.status === 404) {
                    logger.info('[FIX:EMR404] EMR not found, initializing empty draft', {
                        visitId,
                        specialty,
                    });
                    // EMRCACHE-FE-002 (audit 3886 round 18): a 404 placeholder
                    // is NOT a persisted canonical record — never cache it as
                    // authoritative data. Successful writes now refresh the
                    // cache (see saveEMR/signEMR/amendEMR), so a remount after
                    // a save must show the saved content, not this empty draft.
                    return {
                        data: buildInitialEMRData(specialty),
                        version: 1,
                        row_version: 0,
                        status: 'draft',
                    };
                }

                const normalizedEmr = {
                    ...response.data,
                    data: normalizeEMRData(response.data?.data, specialty),
                };
                if (canUseCache && currentEntry === pendingEntry && getCachePrincipal() === cachePrincipal) {
                    emrCache.set(cacheKey, { data: normalizedEmr, promise: null });
                }
                return normalizedEmr;
            } catch (error) {
                const apiError = toEMRApiError(error);
                if (emrCache.get(cacheKey) === pendingEntry) emrCache.delete(cacheKey);
                if (isAccessDenied(apiError)) {
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
                    emrCache.delete(cacheKey);
                    return handleAccessDenied('loadEMR', apiError);
                }

                logger.error('Failed to load EMR:', error);
                // Ignore recoverable failures after the editor has moved on
                // to another visit, later edits, or a newer write.
                if (!stillCurrentSnapshot()) {
                    return { stale: true };
                }
                if (isMountedRef.current) {
                    dispatch(emrActions.saveError(apiError.message || 'Failed to load EMR'));
                }
                throw error;
            }
        })();

        if (canUseCache) {
            pendingEntry.promise = loadPromise;
            emrCache.set(cacheKey, pendingEntry);
        }

        try {
            return applySnapshot(await loadPromise);
        } finally {
            const currentEntry = emrCache.get(cacheKey);
            if (currentEntry?.promise === loadPromise) {
                emrCache.set(cacheKey, {
                    data: currentEntry.data || null,
                    promise: null,
                });
            }
        }
    }, [cacheKey, cachePrincipal, canUseCache, clearPatientContextChanged, clearServerFinalized, expectedPatientId, handleAccessDenied, handlePatientContextChanged, specialty, visitId]);

    // =========================================================================
    // SAVE EMR
    // =========================================================================
    const saveEMR = useCallback(async (options: Record<string, unknown> = {}) => {
        const { isDraft = true, force = false } = options;
        const epoch = visitEpochRef.current;
        if (visitIdentityRef.current !== visitId || patientIdentityRef.current !== expectedPatientId
            || draftSaveEpochRef.current === epoch) return null;

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

        draftSaveEpochRef.current = epoch;
        documentGenerationRef.current += 1;
        dispatch(emrActions.saveStart());
        const stillCurrentVisit = () => isMountedRef.current && visitEpochRef.current === epoch
            && getCachePrincipal() === cachePrincipal;

        try {
            const payload = {
                // EMRSIGN-FE-001: serialize the LATEST document, not the
                // closure snapshot from the render this callback was created in.
                data: normalizeEMRData(stateRef.current.data, specialty),
                row_version: force ? 0 : stateRef.current.rowVersion, // 0 = skip lock check
                client_session_id: clientSessionId.current,
                is_draft: isDraft,
                ...(expectedPatientId !== null && { expected_patient_id: expectedPatientId }),
            };

            const response = await apiClient.post(`/v2/emr/${visitId}`, payload);
            // EMRCACHE-FE-002: refresh the cache with the authoritative
            // server record so a remount shows the saved content/version.
            if (canUseCache && stillCurrentVisit()) {
                emrCache.set(cacheKey, {
                    data: { ...response.data, data: normalizeEMRData(response.data?.data, specialty) },
                    promise: null,
                });
            }
            if (stillCurrentVisit()) {
                dispatch(emrActions.saveSuccess(response.data));
            }
            return stillCurrentVisit() ? response.data : null;
        } catch (error) {
            const apiError = toEMRApiError(error);
            if (isAccessDenied(apiError)) {
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
                    error?: string;
                    message?: string;
                    [key: string]: unknown;
                };
                // RETRO-3971-03 (post-merge review of the 3969–3996 window):
                // a structured FINALIZED_STATE 409 is amendment routing, not
                // a version conflict — the backend deliberately returns it
                // when the record was signed/amended on the server (it was
                // never “another user changed the document”). Dispatching
                // conflictDetected here rendered the false conflict dialog
                // with literal vundefined/vundefined versions (no version
                // fields on this payload) and gated the amendment affordance
                // behind the LOCAL isSigned flag, false in this scenario.
                // Route honestly: the same saveError surfacing the 400-branch
                // uses for signed documents, plus a `finalized: true` marker
                // the autosave hook classifies as deterministic (never
                // stamped as a successful save).
                if (conflictData?.error === 'FINALIZED_STATE') {
                    if (stillCurrentVisit()) {
                        // RETRO-4007-01: expose the marker so the amendment
                        // affordance opens for THIS stale-local window.
                        markServerFinalized();
                        dispatch(emrActions.saveError('EMR подписана. Используйте "Внести поправку".'));
                    }
                    return { finalized: true, ...conflictData };
                }
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
                        // RETRO-4007-01: the legacy signed-400 refusal marks
                        // the same server-finalized window (amend routing).
                        markServerFinalized();
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
        } finally {
            if (draftSaveEpochRef.current === epoch) draftSaveEpochRef.current = null;
        }
    }, [cacheKey, cachePrincipal, canUseCache, expectedPatientId, handleAccessDenied, specialty, visitId, markServerFinalized]);

    // =========================================================================
    // SIGN EMR
    // =========================================================================
    const signEMR = useCallback(async (options: { rowVersion?: number; data?: Record<string, unknown> } = {}) => {
        if (visitIdentityRef.current !== visitId || patientIdentityRef.current !== expectedPatientId
            || draftSaveEpochRef.current === visitEpochRef.current) return null;
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

        documentGenerationRef.current += 1;
        dispatch(emrActions.saveStart());
        const epoch = visitEpochRef.current;
        const stillCurrentVisit = () => isMountedRef.current && visitEpochRef.current === epoch
            && getCachePrincipal() === cachePrincipal;

        try {
            const payload = {
                data: normalizeEMRData(options.data ?? stateRef.current.data, specialty),
                row_version: options.rowVersion ?? stateRef.current.rowVersion,
                client_session_id: clientSessionId.current,
            };

            const response = await apiClient.post(`/v2/emr/${visitId}/sign`, payload);
            // EMRCACHE-FE-002: keep the cache in sync with the signed record.
            if (canUseCache && stillCurrentVisit()) {
                emrCache.set(cacheKey, {
                    data: { ...response.data, data: normalizeEMRData(response.data?.data, specialty) },
                    promise: null,
                });
            }
            if (stillCurrentVisit()) {
                dispatch(emrActions.saveSuccess(response.data));
            }
            return stillCurrentVisit() ? response.data : null;
        } catch (error) {
            const apiError = toEMRApiError(error);
            if (isAccessDenied(apiError)) {
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
                    error?: string;
                    message?: string;
                    [key: string]: unknown;
                };
                // RETRO-3971-03: same honest routing on the sign path — a
                // FINALIZED_STATE 409 is amendment routing, never a version
                // conflict (see the save-path branch above for the rationale).
                if (conflictData?.error === 'FINALIZED_STATE') {
                    if (stillCurrentVisit()) {
                        // RETRO-4007-01: the sign path marks the same
                        // server-finalized window.
                        markServerFinalized();
                        dispatch(emrActions.saveError('EMR подписана. Используйте "Внести поправку".'));
                    }
                    return { finalized: true, ...conflictData };
                }
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
    }, [cacheKey, cachePrincipal, canUseCache, expectedPatientId, handleAccessDenied, specialty, visitId, markServerFinalized]);

    // =========================================================================
    // AMEND EMR
    // =========================================================================
    const amendEMR = useCallback(async (reason: string, options: { data?: Record<string, unknown> } = {}) => {
        if (visitIdentityRef.current !== visitId || patientIdentityRef.current !== expectedPatientId
            || draftSaveEpochRef.current === visitEpochRef.current) return null;
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

        documentGenerationRef.current += 1;
        dispatch(emrActions.saveStart());
        const epoch = visitEpochRef.current;
        const stillCurrentVisit = () => isMountedRef.current && visitEpochRef.current === epoch
            && getCachePrincipal() === cachePrincipal;

        try {
            const payload = {
                // EMRSIGN-FE-001: amendments serialize the live document too.
                data: normalizeEMRData(options.data ?? stateRef.current.data, specialty),
                reason: reason.trim(),
                row_version: stateRef.current.rowVersion,
            };

            const response = await apiClient.post(`/v2/emr/${visitId}/amend`, payload);
            // EMRCACHE-FE-002: keep the cache in sync with the amended record.
            if (canUseCache && stillCurrentVisit()) {
                emrCache.set(cacheKey, {
                    data: { ...response.data, data: normalizeEMRData(response.data?.data, specialty) },
                    promise: null,
                });
            }
            if (stillCurrentVisit()) {
                // RETRO-4007-01: the reasoned amendment landed — the amended
                // server record supersedes the stale-local window.
                clearServerFinalized();
                dispatch(emrActions.load({ ...response.data, data: normalizeEMRData(response.data?.data, specialty) }));
            }
            return stillCurrentVisit() ? response.data : null;
        } catch (error) {
            const apiError = toEMRApiError(error);
            if (isAccessDenied(apiError)) {
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
    }, [cacheKey, cachePrincipal, canUseCache, expectedPatientId, handleAccessDenied, specialty, visitId, clearServerFinalized]);

    // =========================================================================
    // CONFLICT RESOLUTION
    // =========================================================================
    // The guarded LOAD resolves the conflict together with the discarded
    // text and history. A separate dispatch could clear newer edits.
    const reloadFromServer = useCallback(() => loadEMR(true), [loadEMR]);

    // =========================================================================
    // FIELD SETTERS
    // =========================================================================
    const setField = useCallback((field: string, value: unknown, source?: Record<string, unknown>) => {
        if (writeAccessDeniedRef.current) return;
        documentGenerationRef.current += 1;
        dispatch(emrActions.setField(field, value, source));
    }, []);

    const setNestedField = useCallback((path: string, value: unknown) => {
        if (writeAccessDeniedRef.current) return;
        documentGenerationRef.current += 1;
        dispatch(emrActions.setNestedField(path, value));
    }, []);

    // =========================================================================
    // UNDO/REDO
    // =========================================================================
    const undo = useCallback(() => {
        if (writeAccessDeniedRef.current) return;
        documentGenerationRef.current += 1;
        dispatch(emrActions.undo());
    }, []);

    const redo = useCallback(() => {
        if (writeAccessDeniedRef.current) return;
        documentGenerationRef.current += 1;
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
        patientContextChanged,
        // RETRO-4007-01: the record was finalized (signed/amended) on the
        // server while the local editor still held the stale in_progress
        // draft — the amendment affordance must open for this window
        // (cleared by a reload/amendment/visit switch/specialty change).
        serverFinalized,

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
