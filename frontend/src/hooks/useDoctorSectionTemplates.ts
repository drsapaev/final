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
const sectionTemplateCache = new Map();
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

    /**
     * Subscribe THIS hook instance to a shared in-flight promise so a second
     * mounted hook receives the fetched result too (EMRTMPL-FE-002).
     */
    const joinInFlightRequest = useCallback((epoch: number, promise: Promise<unknown>) => {
        if (isMountedRef.current) {
            setLoading(true);
        }
        promise.then((result: unknown) => {
            // EMRTMPL-FE-003: only commit while this request context is still current.
            if (!isMountedRef.current || epoch !== requestEpochRef.current) return;
            setTemplates(Array.isArray(result) ? result : []);
            setError(null);
            setLoading(false);
        }).catch(() => {
            if (isMountedRef.current && epoch === requestEpochRef.current) {
                setLoading(false);
            }
        });
        return promise;
    }, []);

    /**
     * Fetch templates from API
     */
    const fetchTemplates = useCallback(async (forceRefresh: boolean = false) => {
        if (!section) return;

        const epoch = ++requestEpochRef.current;
        // RETRO-3953-01: the owner whose authorization produced this request.
        // A response that completes after another principal took over must not
        // park its data in the (already cleared) module cache.
        const ownerAtRequest = sectionTemplateCacheOwner;
        const cachedEntry = canUseCache ? sectionTemplateCache.get(cacheKey) : undefined;
        if (!forceRefresh) {
            if (cachedEntry?.data) {
                if (isMountedRef.current && epoch === requestEpochRef.current) {
                    setTemplates(cachedEntry.data);
                    setError(null);
                    setLoading(false);
                }
                return cachedEntry.data;
            }

            if (cachedEntry?.promise) {
                // EMRTMPL-FE-002: joining an in-flight request must also
                // deliver the result to THIS instance, not only to the one
                // that started it.
                return joinInFlightRequest(epoch, cachedEntry.promise as Promise<unknown>);
            }
        } else if (cachedEntry?.promise) {
            return joinInFlightRequest(epoch, cachedEntry.promise as Promise<unknown>);
        }

        if (isMountedRef.current) {
            setLoading(true);
            setError(null);
        }

        const loadPromise = (async () => {
            const params = new URLSearchParams();
            if (icd10Code) params.append('icd10_code', String(icd10Code));
            params.append('limit', limit.toString());

            try {
                const response = await apiClient.get(
                    `/section-templates/${section}?${params.toString()}`
                );

                const templatesData = (response.data as Record<string, unknown>).templates || [];
                // RETRO-3953-01: an owner-swapped request may not repopulate
                // the cache with the previous principal's data.
                if (canUseCache && sectionTemplateCacheOwner === ownerAtRequest) {
                    sectionTemplateCache.set(cacheKey, {
                        data: templatesData,
                        promise: null,
                    });
                }

                // EMRTMPL-FE-003: commit only if this request context is
                // still the current one (the cache write above stays valid —
                // it is keyed to its own section/ICD context).
                if (isMountedRef.current && epoch === requestEpochRef.current) {
                    setTemplates(templatesData as unknown[]);
                }

                return templatesData;
            } catch (err: unknown) {
                logger.error('[useDoctorSectionTemplates] Fetch error:', err);
                if (isMountedRef.current && epoch === requestEpochRef.current) {
                    setError((err as Error).message || 'Failed to load templates');
                    setTemplates([]);
                }
                if (canUseCache) {
                    sectionTemplateCache.delete(cacheKey);
                }
                return [];
            }
        })();

        if (canUseCache) {
            sectionTemplateCache.set(cacheKey, {
                data: cachedEntry?.data || null,
                promise: loadPromise,
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
                    });
                }
            }

            if (isMountedRef.current && epoch === requestEpochRef.current) {
                setLoading(false);
            }
        }
    }, [cacheKey, canUseCache, icd10Code, joinInFlightRequest, limit, section]);

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
            await fetchTemplates(true); // Refresh list
            return { success: true };
        } catch (err: unknown) {
            logger.error('[useDoctorSectionTemplates] Pin error:', err);
            return { success: false, error: (err as Error).message };
        }
    }, [section, fetchTemplates]);

    /**
     * Unpin a template
     * @param {string} templateId
     */
    const unpinTemplate = useCallback(async (templateId: string) => {
        try {
            await apiClient.delete(`/section-templates/${section}/${templateId}/pin`);
            await fetchTemplates(true);
            return { success: true };
        } catch (err: unknown) {
            logger.error('[useDoctorSectionTemplates] Unpin error:', err);
            return { success: false, error: (err as Error).message };
        }
    }, [section, fetchTemplates]);

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
            await fetchTemplates(true);
            return { success: true, template: response.data };
        } catch (err: unknown) {
            logger.error('[useDoctorSectionTemplates] Update error:', err);
            return { success: false, error: (err as Error).message };
        }
    }, [section, fetchTemplates]);

    /**
     * Delete a template
     * @param {string} templateId
     */
    const deleteTemplate = useCallback(async (templateId: string) => {
        try {
            await apiClient.delete(`/section-templates/${section}/${templateId}`);
            await fetchTemplates(true);
            return { success: true };
        } catch (err: unknown) {
            logger.error('[useDoctorSectionTemplates] Delete error:', err);
            return { success: false, error: (err as Error).message };
        }
    }, [section, fetchTemplates]);

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
