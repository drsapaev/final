/**
 * useDoctorSectionTemplates - Universal hook for doctor's section templates
 * 
 * Персональная клиническая память врача по секциям EMR:
 * - complaints (жалобы)
 * - anamnesis (анамнез)
 * - examination (осмотр)
 * - treatment (лечение)
 * - recommendations (рекомендации)
 * 
 * Usage:
 * const { templates, loading, pin, unpin, update, deleteTemplate } = 
 *   useDoctorSectionTemplates({ section: 'treatment', icd10Code: 'I10' });
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import apiClient from '../api/client';
import logger from '../utils/logger';
import { getState as getAuthState } from '../stores/auth';

// EMRTMPL-FE-001 (audit 3886 round 23): this module-global cache holds
// DOCTOR-SPECIFIC clinical phrases, so it is scoped to the authenticated
// principal and fully cleared on any principal change (logout / account
// switch inside the same JS runtime). The server stays the canonical
// authorization boundary; the cache may never hand another principal's
// templates to a hook. Mirrors the EMRCACHE-FE-001 pattern in useEMR.
// RETRO-3953-04 (dossier PR 3958): the shared in-flight outcome is TYPED — a
// failed GET is carried to every subscriber as { ok: false, error }, never
// laundered into a resolved empty list that reads as an honest success.
export type TemplateFetchOutcome =
    | { ok: true; data: unknown[] }
    | { ok: false; error: string };

interface SectionTemplateCacheEntry {
    data: unknown[] | null;
    promise: Promise<TemplateFetchOutcome> | null;
    // RETRO-3995-02 (ledger PR 4000): install generation of the request that
    // last replaced this entry — the SHARED write/delete identity.
    token: number;
}

const sectionTemplateCache = new Map<string, SectionTemplateCacheEntry>();
// RETRO-3995-02: monotonic per-key install generation. The request epoch is
// per hook INSTANCE and cannot see another instance's newer write into the
// SHARED map, so a last responder can pass its own epoch check and replace a
// newer successful entry with its stale payload (and a stale failure can
// delete it). Every cache write and every cache delete must still hold the
// newest token; a stale-generation response adopts the newer shared truth
// (or chains onto its pending read) instead of painting its own payload.
const sectionTemplateCacheTokens = new Map<string, number>();
// RETRO-4014-01 (ledger PR 4000, comment 19): per-key failure tombstone —
// the generation of the LATEST failed fresh read. A newer failure deletes
// the shared entry, so a stale completion later sees NO newer entry and
// used to fall through to its own payload as { ok: true } — the doctor saw
// old clinical phrase text as a successful current response after a
// successful mutation and a failed fresh read. The tombstone is the shared
// 'latest outcome is failure' record: a stale completion refuses to adopt
// its own payload while a newer generation's failure is the last known
// event. Pending-read chaining and newer-data adoption keep precedence.
const sectionTemplateCacheFailures = new Map<string, { token: number; error: string }>();
// RETRO-4014-01 sibling convergence (ledger PR 4000, comment 19): per-key
// listener registry for ALREADY-PAINTED mounted instances. A successful
// shared-map install fans out to every same-key subscriber so a quiet
// sibling converges on the newer truth without its own request; FAILURE
// outcomes fan out NOTHING (the tombstone governs reads; a painted sibling
// keeps its last known good list). Cleared on principal swap like every
// other module map.
const sectionTemplateCacheListeners = new Map<string, Set<() => void>>();
const notifySectionTemplateKey = (cacheKey: string): void => {
    const listeners = sectionTemplateCacheListeners.get(cacheKey);
    if (!listeners || listeners.size === 0) return;
    for (const listener of [...listeners]) listener();
};

const acquireCacheToken = (cacheKey: string): number => {
    const next = (sectionTemplateCacheTokens.get(cacheKey) ?? 0) + 1;
    sectionTemplateCacheTokens.set(cacheKey, next);
    return next;
};

const currentCacheToken = (cacheKey: string): number =>
    sectionTemplateCacheTokens.get(cacheKey) ?? 0;
let sectionTemplateCacheOwner: string | null = null;
const getCacheOwner = (): string | null => {
    try {
        const profile = getAuthState()?.profile;
        const id = profile?.id;
        return id === null || id === undefined ? null : String(id);
    } catch {
        return null;
    }
};

const syncSectionTemplateCacheOwner = (): void => {
    const owner = getCacheOwner();
    if (owner !== sectionTemplateCacheOwner) {
        sectionTemplateCache.clear();
        sectionTemplateCacheTokens.clear();
        sectionTemplateCacheFailures.clear();
        sectionTemplateCacheListeners.clear();
        sectionTemplateCacheOwner = owner;
    }
};

/**
 * @typedef {Object} SectionTemplate
 * @property {string} id - Template ID
 * @property {string} section_type - Section type
 * @property {string|null} icd10_code - ICD-10 code (null for general)
 * @property {string} template_text - Template text
 * @property {number} usage_count - Usage count
 * @property {boolean} is_pinned - Is pinned
 * @property {string|null} frequency_label - "часто" | "редко" | null
 * @property {boolean} is_stale - Not used > 12 months
 * @property {string|null} last_used_at - Last used timestamp
 */

/**
 * Valid section types
 */
export const SECTION_TYPES = {
    COMPLAINTS: 'complaints',
    ANAMNESIS: 'anamnesis',
    EXAMINATION: 'examination',
    TREATMENT: 'treatment',
    RECOMMENDATIONS: 'recommendations',
};

/**
 * Section labels (Russian)
 */
export const SECTION_LABELS = {
    complaints: 'Жалобы',
    anamnesis: 'Анамнез',
    examination: 'Осмотр',
    treatment: 'Лечение',
    recommendations: 'Рекомендации',
};

/**
 * Universal hook for doctor's section templates
 * 
 * @param {Object} options
 * @param {string} options.section - Section type (from SECTION_TYPES)
 * @param {string} [options.icd10Code] - ICD-10 code for filtering (optional)
 * @param {number} [options.limit=10] - Max templates to fetch
 * @returns {Object}
 */
export function useDoctorSectionTemplates({
    section,
    icd10Code = null,
    limit = 10,
}: {
    section?: string;
    icd10Code?: string | null;
    limit?: number;
} = {}) {
    const [templates, setTemplates] = useState<unknown[]>([]);
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<unknown>(null);
    const isMountedRef = useRef(true);
    // EMRTMPL-FE-003 (audit 3886 round 23): request-generation guard. Every
    // state commit must belong to the CURRENT section/ICD/limit context — a
    // slow response for the previous diagnosis must never overwrite the
    // results of the current one.
    const requestEpochRef = useRef(0);
    // RETRO-4014-01 sibling convergence: the window in which THIS instance's
    // own request owns the paint (a fan-out repaint must never interleave
    // with an in-flight own request) and the shared install generation this
    // instance last painted (a repaint fires only for a NEWER truth).
    const ownFetchPendingRef = useRef(0);
    const lastPaintedSharedTokenRef = useRef(0);

    useEffect(() => {
        isMountedRef.current = true;
        return () => {
            isMountedRef.current = false;
        };
    }, []);

    // EMRTMPL-FE-001: principal scoping — the key carries the owner and any
    // principal swap clears the map (dropping pending promises too).
    syncSectionTemplateCacheOwner();
    const cacheOwner = sectionTemplateCacheOwner;
    const canUseCache = cacheOwner !== null;
    const cacheKey = `${cacheOwner ?? 'anonymous'}:${section || ''}:${icd10Code || ''}:${limit}`;

    // RETRO-3995-01 (post-merge review of the #3969–#3996 wave): the LIVE
    // context key of this hook instance, updated on every render. The epoch
    // guard alone cannot stop a STALE-CLOSURE request from painting the
    // panel: a mutation (updateTemplate/pinTemplate/unpinTemplate/
    // deleteTemplate) that completes after the doctor switched the
    // section/ICD context called its captured fetchTemplates(true), which
    // took the NEWEST epoch for the OLD context and committed the previous
    // diagnosis's phrases under the current one (while the live context's
    // own in-flight response was discarded and never cached). Every state
    // commit below therefore additionally requires the request's context to
    // still be the live one.
    const liveCacheKeyRef = useRef(cacheKey);
    liveCacheKeyRef.current = cacheKey;

    // RETRO-3953-01 (dossier PR 3958): the rendered list belongs to the
    // PREVIOUS principal once the authenticated owner changes inside a
    // still-mounted hook. The module cache is already owner-scoped, but the
    // per-hook `templates` state was initialized once and survived an owner
    // swap, so doctor B could see doctor A's personal phrases until B's GET
    // resolved (or failed). The render-time reset drops the stale list
    // SYNCHRONOUSLY, before the new principal's fetch can paint anything;
    // async completions stay gated by the request epoch and an owner check
    // captured at request start.
    const [renderedOwner, setRenderedOwner] = useState(cacheOwner);
    if (renderedOwner !== cacheOwner) {
        setRenderedOwner(cacheOwner);
        setTemplates([]);
        setError(null);
    }

    // RETRO-3953-02 (dossier PR 3958): the same honesty rule applies to the
    // section/ICD/limit context itself — an in-place change must invalidate
    // the displayed phrases SYNCHRONOUSLY (they must not stay rendered or
    // actionable while the new context's request is pending). The new
    // context's cached list, if any, is seeded immediately; otherwise the
    // panel shows the honest empty state until its own fetch commits.
    const contextKey = `${section || ''}:${icd10Code || ''}:${limit}`;
    const [renderedContext, setRenderedContext] = useState(contextKey);
    if (renderedContext !== contextKey) {
        setRenderedContext(contextKey);
        const seed = canUseCache ? sectionTemplateCache.get(cacheKey) : undefined;
        setTemplates(seed?.data ?? []);
        lastPaintedSharedTokenRef.current = seed?.token ?? 0;
        setError(null);
    }

    /**
     * Subscribe THIS hook instance to a shared in-flight promise so a second
     * mounted hook receives the fetched result too (EMRTMPL-FE-002).
     */
    const joinInFlightRequest = useCallback((epoch: number, promise: Promise<TemplateFetchOutcome>, contextKey: string) => {
        if (isMountedRef.current) {
            setLoading(true);
        }
        promise.then((outcome) => {
            // EMRTMPL-FE-003: only commit while this request context is still current.
            if (!isMountedRef.current || epoch !== requestEpochRef.current) return;
            // RETRO-3995-01: and only while the joined request's context is
            // still the LIVE context of this hook instance.
            if (liveCacheKeyRef.current !== contextKey) return;
            // RETRO-3953-04: the shared outcome carries the typed failure — a
            // joining subscriber shows the same error as the originator
            // instead of a laundered empty success.
            if (outcome.ok) {
                setTemplates(outcome.data);
                setError(null);
            } else {
                setError(outcome.error);
                setTemplates([]);
            }
            setLoading(false);
            // The joiner painted the shared truth — record its generation so
            // a later repaint only fires for something NEWER.
            if (outcome.ok) {
                lastPaintedSharedTokenRef.current =
                    sectionTemplateCache.get(contextKey)?.token ?? lastPaintedSharedTokenRef.current;
            }
        });
        return promise;
    }, []);

    // RETRO-4014-01 sibling convergence: the fan-out repaint. Another
    // instance's successful install moved the shared truth past what THIS
    // instance last painted — converge without a new request. Gates: the
    // instance is mounted, its live context is still this key, it owns NO
    // in-flight request, and the shared token is strictly newer.
    const repaintFromSharedCache = useCallback(() => {
        if (!isMountedRef.current) return;
        if (ownFetchPendingRef.current > 0) return;
        if (liveCacheKeyRef.current !== cacheKey) return;
        const entry = canUseCache ? sectionTemplateCache.get(cacheKey) : undefined;
        if (!entry?.data) return;
        if (entry.token <= lastPaintedSharedTokenRef.current) return;
        lastPaintedSharedTokenRef.current = entry.token;
        setTemplates(entry.data);
        setError(null);
        setLoading(false);
    }, [cacheKey, canUseCache]);

    useEffect(() => {
        if (!canUseCache) return undefined;
        const set = sectionTemplateCacheListeners.get(cacheKey) ?? new Set<() => void>();
        sectionTemplateCacheListeners.set(cacheKey, set);
        set.add(repaintFromSharedCache);
        return () => {
            set.delete(repaintFromSharedCache);
        };
    }, [cacheKey, canUseCache, repaintFromSharedCache]);

    /**
     * Fetch templates from API
     */
    const fetchTemplatesInner = useCallback(async (forceRefresh: boolean = false): Promise<TemplateFetchOutcome> => {
        if (!section) {
            // RETRO-3953-02: no section → no query, and the previous
            // context's request epoch is invalidated so its late response can
            // never repopulate the (already synchronously cleared) list.
            requestEpochRef.current += 1;
            if (isMountedRef.current) {
                setTemplates([]);
                setError(null);
                setLoading(false);
            }
            return { ok: true, data: [] };
        }

        const epoch = ++requestEpochRef.current;
        // RETRO-3953-01: the owner whose authorization produced this request.
        // A response that completes after another principal took over must not
        // park its data in the (already cleared) module cache.
        const ownerAtRequest = sectionTemplateCacheOwner;
        const cachedEntry = canUseCache ? sectionTemplateCache.get(cacheKey) : undefined;
        if (!forceRefresh) {
            if (cachedEntry?.data) {
                if (isMountedRef.current && epoch === requestEpochRef.current && liveCacheKeyRef.current === cacheKey) {
                    setTemplates(cachedEntry.data);
                    lastPaintedSharedTokenRef.current = cachedEntry.token;
                    setError(null);
                    setLoading(false);
                }
                return { ok: true, data: cachedEntry.data };
            }

            if (cachedEntry?.promise) {
                // EMRTMPL-FE-002: joining an in-flight request must also
                // deliver the result to THIS instance, not only to the one
                // that started it.
                return joinInFlightRequest(epoch, cachedEntry.promise, cacheKey);
            }
        }
        // RETRO-3953-03: a forced refresh NEVER joins a pre-mutation in-flight
        // promise — after a successful PUT the stale GET's payload must not
        // overwrite the post-edit view while the mutation reports success.
        // Force always issues a fresh read whose loadPromise replaces the
        // cached one, so subsequent ordinary readers join the fresh request.

        if (isMountedRef.current) {
            setLoading(true);
            setError(null);
        }

        // RETRO-3995-02: the per-key install token of THIS read. Every cache
        // write/delete below must still hold the newest token: a newer
        // same-key install (another instance's forced post-mutation refresh)
        // invalidates this request's cache claims, and its stale response
        // adopts the newer shared truth instead of overwriting it.
        const myCacheToken = canUseCache ? acquireCacheToken(cacheKey) : 0;

        // Annotated: keeps the outcome literals narrow (ok: true / ok: false)
        // so the shared promise matches the cached-entry type.
        const loadPromise = (async (): Promise<TemplateFetchOutcome> => {
            const params = new URLSearchParams();
            if (icd10Code) params.append('icd10_code', String(icd10Code));
            params.append('limit', limit.toString());

            try {
                const response = await apiClient.get(
                    `/section-templates/${section}?${params.toString()}`
                );

                const templatesData = ((response.data as Record<string, unknown>).templates || []) as unknown[];
                // RETRO-3953-01: an owner-swapped request may not repopulate
                // the cache with the previous principal's data.
                // RETRO-3953-03: a superseded request's late response must not
                // poison the cache either — only the CURRENT request context
                // may claim the cache entry.
                // RETRO-3995-02: and only the holder of the newest per-key
                // install token may write it — a stale cross-instance
                // responder adopts the newer shared truth (pending read or
                // committed data) instead of replacing it with its payload.
                let committedData = templatesData;
                if (
                    canUseCache &&
                    sectionTemplateCacheOwner === ownerAtRequest &&
                    epoch === requestEpochRef.current &&
                    myCacheToken === currentCacheToken(cacheKey)
                ) {
                    sectionTemplateCache.set(cacheKey, {
                        data: templatesData,
                        promise: null,
                        token: myCacheToken,
                    });
                    // RETRO-4014-01: a newer SUCCESS supersedes any older
                    // failure tombstone for this key.
                    sectionTemplateCacheFailures.delete(cacheKey);
                    lastPaintedSharedTokenRef.current = myCacheToken;
                    // RETRO-4014-01 sibling convergence: THE fan-out point —
                    // every mounted same-key sibling repaints the newer
                    // truth; failure installs never notify.
                    notifySectionTemplateKey(cacheKey);
                } else if (canUseCache) {
                    const newerEntry = sectionTemplateCache.get(cacheKey);
                    if (newerEntry?.promise && newerEntry.token !== myCacheToken) {
                        // A newer same-key read is still in flight: its
                        // outcome is the freshest shared truth — chain onto it
                        // so this instance AND every joiner of this stale
                        // request converge on the newer result. The token
                        // comparison never chains onto THIS request's own
                        // install: the same key can be stale by EPOCH (this
                        // instance switched context) while the install token
                        // is still ours — a self reference would create a
                        // promise cycle.
                        // RETRO-4014-01: routed through the joiner contract —
                        // the bare return resolved this request's promise but
                        // never repainted THE STALE INSTANCE'S own state, so
                        // it stayed on an empty list while the cache moved on.
                        return joinInFlightRequest(epoch, newerEntry.promise, cacheKey);
                    }
                    if (newerEntry?.data && newerEntry.token !== myCacheToken) {
                        // A newer same-key read already committed successful
                        // data: prefer it over this stale payload.
                        committedData = newerEntry.data;
                        lastPaintedSharedTokenRef.current = newerEntry.token;
                    }
                    // RETRO-4014-01: no newer entry at all, but a NEWER
                    // generation's failure is the last shared event (its
                    // catch deleted the entry and left the tombstone). The
                    // stale payload must not fall through as a successful
                    // current response — surface the newer failure to this
                    // instance and every joiner honestly.
                    if (!newerEntry) {
                        const newerFailure = sectionTemplateCacheFailures.get(cacheKey);
                        if (newerFailure && newerFailure.token > myCacheToken) {
                            if (
                                isMountedRef.current &&
                                epoch === requestEpochRef.current &&
                                liveCacheKeyRef.current === cacheKey
                            ) {
                                setError(newerFailure.error);
                                setTemplates([]);
                            }
                            return { ok: false, error: newerFailure.error };
                        }
                    }
                }

                // EMRTMPL-FE-003: commit only if this request context is
                // still the current one — and RETRO-3995-01: only if it is
                // still the LIVE context (a stale-closure forced refresh may
                // own the newest epoch yet paint a context the doctor left).
                if (isMountedRef.current && epoch === requestEpochRef.current && liveCacheKeyRef.current === cacheKey) {
                    setTemplates(committedData);
                }

                return { ok: true, data: committedData };
            } catch (err: unknown) {
                logger.error('[useDoctorSectionTemplates] Fetch error:', err);
                const message = (err as Error).message || 'Failed to load templates';
                // RETRO-3995-02: only the newest generation may own its
                // failure. A stale-generation failure must never delete a
                // newer successful entry or pending promise, nor paint a
                // false failure over fresher known data — it adopts the
                // newer shared truth instead.
                if (myCacheToken === currentCacheToken(cacheKey)) {
                    if (isMountedRef.current && epoch === requestEpochRef.current && liveCacheKeyRef.current === cacheKey) {
                        setError(message);
                        setTemplates([]);
                    }
                    if (canUseCache && sectionTemplateCacheOwner === ownerAtRequest) {
                        sectionTemplateCache.delete(cacheKey);
                        // RETRO-4014-01: the delete removed the shared truth;
                        // record this generation's failure so a stale
                        // completion can never present its own payload as a
                        // successful current response afterwards.
                        sectionTemplateCacheFailures.set(cacheKey, {
                            token: myCacheToken,
                            error: message,
                        });
                    }
                    return { ok: false, error: message };
                }
                const newerEntry = canUseCache ? sectionTemplateCache.get(cacheKey) : undefined;
                if (newerEntry?.promise && newerEntry.token !== myCacheToken) {
                    // RETRO-4014-01: same joiner-contract convergence as the
                    // success path — the stale failure's instance must follow
                    // the newer pending read instead of staying frozen.
                    return joinInFlightRequest(epoch, newerEntry.promise, cacheKey);
                }
                if (newerEntry?.data && newerEntry.token !== myCacheToken) {
                    if (isMountedRef.current && epoch === requestEpochRef.current && liveCacheKeyRef.current === cacheKey) {
                        setTemplates(newerEntry.data);
                        setError(null);
                    }
                    return { ok: true, data: newerEntry.data };
                }
                return { ok: false, error: message };
            }
        })();

        if (canUseCache) {
            sectionTemplateCache.set(cacheKey, {
                data: cachedEntry?.data || null,
                promise: loadPromise,
                token: myCacheToken,
            });
        }

        try {
            return await loadPromise;
        } finally {
            if (canUseCache) {
                const currentEntry = sectionTemplateCache.get(cacheKey);
                if (currentEntry?.promise === loadPromise) {
                    sectionTemplateCache.set(cacheKey, {
                        data: currentEntry.data || null,
                        promise: null,
                        token: currentEntry.token,
                    });
                }
            }

            if (isMountedRef.current && epoch === requestEpochRef.current) {
                setLoading(false);
            }
        }
    }, [cacheKey, canUseCache, icd10Code, joinInFlightRequest, limit, section]);

    // RETRO-4014-01 sibling convergence: every fetchTemplates invocation —
    // cache hits, joins and fresh reads alike — opens the window in which
    // this instance's own request owns the paint.
    const fetchTemplates = useCallback(
        async (forceRefresh: boolean = false): Promise<TemplateFetchOutcome> => {
            ownFetchPendingRef.current += 1;
            try {
                return await fetchTemplatesInner(forceRefresh);
            } finally {
                ownFetchPendingRef.current -= 1;
            }
        },
        [fetchTemplatesInner],
    );


    // RETRO-3995-01: mutations must refresh the LIVE context. The mutation
    // callbacks below used to call their captured fetchTemplates(true); when
    // the mutation completed after a section/ICD switch, that captured
    // (stale) fetch became the newest epoch and repainted the previous
    // diagnosis's phrases under the current one. The latest-ref indirection
    // guarantees the post-mutation refresh always targets what the doctor is
    // looking at NOW; the live-context commit guards above are the defense
    // in depth for any other stale-closure caller (e.g. a captured refetch).
    const liveFetchRef = useRef<((forceRefresh?: boolean) => Promise<TemplateFetchOutcome>) | null>(null);
    liveFetchRef.current = fetchTemplates;

    // Fetch on mount and when dependencies change
    useEffect(() => {
        fetchTemplates();
    }, [fetchTemplates]);

    /**
     * Pin a template
     * @param {string} templateId
     */
    const pinTemplate = useCallback(async (templateId: string) => {
        try {
            await apiClient.post(`/section-templates/${section}/${templateId}/pin`);
            // RETRO-3995-01: refresh the LIVE context, never the captured one.
            await liveFetchRef.current?.(true); // Refresh list
            return { success: true };
        } catch (err: unknown) {
            logger.error('[useDoctorSectionTemplates] Pin error:', err);
            return { success: false, error: (err as Error).message };
        }
    }, [section]);

    /**
     * Unpin a template
     * @param {string} templateId
     */
    const unpinTemplate = useCallback(async (templateId: string) => {
        try {
            await apiClient.delete(`/section-templates/${section}/${templateId}/pin`);
            // RETRO-3995-01: refresh the LIVE context, never the captured one.
            await liveFetchRef.current?.(true);
            return { success: true };
        } catch (err: unknown) {
            logger.error('[useDoctorSectionTemplates] Unpin error:', err);
            return { success: false, error: (err as Error).message };
        }
    }, [section]);

    /**
     * Update a template
     * @param {string} templateId
     * @param {string} newText
     * @param {'replace'|'save_as_new'} mode
     */
    const updateTemplate = useCallback(async (templateId: string, newText: string, mode: 'replace' | 'save_as_new' = 'replace') => {
        try {
            const response = await apiClient.put(
                `/section-templates/${section}/${templateId}`,
                { new_text: newText, mode }
            );
            // RETRO-3995-01: refresh the LIVE context, never the captured one.
            await liveFetchRef.current?.(true);
            return { success: true, template: response.data };
        } catch (err: unknown) {
            logger.error('[useDoctorSectionTemplates] Update error:', err);
            return { success: false, error: (err as Error).message };
        }
    }, [section]);

    /**
     * Delete a template
     * @param {string} templateId
     */
    const deleteTemplate = useCallback(async (templateId: string) => {
        try {
            await apiClient.delete(`/section-templates/${section}/${templateId}`);
            // RETRO-3995-01: refresh the LIVE context, never the captured one.
            await liveFetchRef.current?.(true);
            return { success: true };
        } catch (err: unknown) {
            logger.error('[useDoctorSectionTemplates] Delete error:', err);
            return { success: false, error: (err as Error).message };
        }
    }, [section]);

    return {
        // Data
        templates,
        loading,
        error,
        hasTemplates: templates.length > 0,

        // Actions
        refetch: fetchTemplates,
        pinTemplate,
        unpinTemplate,
        updateTemplate,
        deleteTemplate,

        // Metadata
        section,
        icd10Code,
    };
}

export default useDoctorSectionTemplates;
