// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

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

const sectionTemplateCache = new Map();

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
    icd10Code = null as unknown,
    limit = 10,
}) {
    const [templates, setTemplates] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const isMountedRef = useRef(true);

    useEffect(() => {
        isMountedRef.current = true;
        return () => {
            isMountedRef.current = false;
        };
    }, []);

    const cacheKey = `${section || ''}:${icd10Code || ''}:${limit}`;

    /**
     * Fetch templates from API
     */
    const fetchTemplates = useCallback(async (forceRefresh: boolean = false) => {
        if (!section) return;

        const cachedEntry = sectionTemplateCache.get(cacheKey);
        if (!forceRefresh) {
            if (cachedEntry?.data) {
                if (isMountedRef.current) {
                    setTemplates(cachedEntry.data);
                    setError(null);
                    setLoading(false);
                }
                return cachedEntry.data;
            }

            if (cachedEntry?.promise) {
                return cachedEntry.promise;
            }
        } else if (cachedEntry?.promise) {
            return cachedEntry.promise;
        }

        if (isMountedRef.current) {
            setLoading(true);
            setError(null);
        }

        const loadPromise = (async () => {
            const params = new URLSearchParams();
            if (icd10Code) params.append('icd10_code', icd10Code);
            params.append('limit', limit.toString());

            try {
                const response = await apiClient.get(
                    `/section-templates/${section}?${params.toString()}`
                );

                const templatesData = response.data.templates || [];
                sectionTemplateCache.set(cacheKey, {
                    data: templatesData,
                    promise: null,
                });

                if (isMountedRef.current) {
                    setTemplates(templatesData);
                }

                return templatesData;
            } catch (err) {
                logger.error('[useDoctorSectionTemplates] Fetch error:', err);
                if (isMountedRef.current) {
                    setError(err.message || 'Failed to load templates');
                    setTemplates([]);
                }
                sectionTemplateCache.delete(cacheKey);
                return [];
            }
        })();

        sectionTemplateCache.set(cacheKey, {
            data: cachedEntry?.data || null,
            promise: loadPromise,
        });

        try {
            return await loadPromise;
        } finally {
            const currentEntry = sectionTemplateCache.get(cacheKey);
            if (currentEntry?.promise === loadPromise) {
                sectionTemplateCache.set(cacheKey, {
                    data: currentEntry.data || null,
                    promise: null,
                });
            }

            if (isMountedRef.current) {
                setLoading(false);
            }
        }
    }, [cacheKey, icd10Code, limit, section]);

    // Fetch on mount and when dependencies change
    useEffect(() => {
        fetchTemplates();
    }, [fetchTemplates]);

    /**
     * Pin a template
     * @param {string} templateId
     */
    const pinTemplate = useCallback(async (templateId) => {
        try {
            await apiClient.post(`/section-templates/${section}/${templateId}/pin`);
            await fetchTemplates(true); // Refresh list
            return { success: true };
        } catch (err) {
            logger.error('[useDoctorSectionTemplates] Pin error:', err);
            return { success: false, error: err.message };
        }
    }, [section, fetchTemplates]);

    /**
     * Unpin a template
     * @param {string} templateId
     */
    const unpinTemplate = useCallback(async (templateId) => {
        try {
            await apiClient.delete(`/section-templates/${section}/${templateId}/pin`);
            await fetchTemplates(true);
            return { success: true };
        } catch (err) {
            logger.error('[useDoctorSectionTemplates] Unpin error:', err);
            return { success: false, error: err.message };
        }
    }, [section, fetchTemplates]);

    /**
     * Update a template
     * @param {string} templateId
     * @param {string} newText
     * @param {'replace'|'save_as_new'} mode
     */
    const updateTemplate = useCallback(async (templateId, newText, mode = 'replace') => {
        try {
            const response = await apiClient.put(
                `/section-templates/${section}/${templateId}`,
                { new_text: newText, mode }
            );
            await fetchTemplates(true);
            return { success: true, template: response.data };
        } catch (err) {
            logger.error('[useDoctorSectionTemplates] Update error:', err);
            return { success: false, error: err.message };
        }
    }, [section, fetchTemplates]);

    /**
     * Delete a template
     * @param {string} templateId
     */
    const deleteTemplate = useCallback(async (templateId) => {
        try {
            await apiClient.delete(`/section-templates/${section}/${templateId}`);
            await fetchTemplates(true);
            return { success: true };
        } catch (err) {
            logger.error('[useDoctorSectionTemplates] Delete error:', err);
            return { success: false, error: err.message };
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
