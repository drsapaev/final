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
}) {
    const [templates, setTemplates] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const abortControllerRef = useRef(null);

    /**
     * Fetch templates from API
     */
    const fetchTemplates = useCallback(async () => {
        if (!section) return;

        // Cancel previous request
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        abortControllerRef.current = new AbortController();

        setLoading(true);
        setError(null);

        try {
            const params = new URLSearchParams();
            if (icd10Code) params.append('icd10_code', icd10Code);
            params.append('limit', limit.toString());

            const response = await apiClient.get(
                `/section-templates/${section}?${params.toString()}`,
                { signal: abortControllerRef.current.signal }
            );

            setTemplates(response.data.templates || []);
        } catch (err) {
            if (err.name !== 'CanceledError' && err.code !== 'ERR_CANCELED') {
                console.error('[useDoctorSectionTemplates] Fetch error:', err);
                setError(err.message || 'Failed to load templates');
                setTemplates([]);
            }
        } finally {
            setLoading(false);
        }
    }, [section, icd10Code, limit]);

    // Fetch on mount and when dependencies change
    useEffect(() => {
        fetchTemplates();

        return () => {
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }
        };
    }, [fetchTemplates]);

    /**
     * Pin a template
     * @param {string} templateId
     */
    const pinTemplate = useCallback(async (templateId) => {
        try {
            await apiClient.post(`/section-templates/${section}/${templateId}/pin`);
            await fetchTemplates(); // Refresh list
            return { success: true };
        } catch (err) {
            console.error('[useDoctorSectionTemplates] Pin error:', err);
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
            await fetchTemplates();
            return { success: true };
        } catch (err) {
            console.error('[useDoctorSectionTemplates] Unpin error:', err);
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
            await fetchTemplates();
            return { success: true, template: response.data };
        } catch (err) {
            console.error('[useDoctorSectionTemplates] Update error:', err);
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
            await fetchTemplates();
            return { success: true };
        } catch (err) {
            console.error('[useDoctorSectionTemplates] Delete error:', err);
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
