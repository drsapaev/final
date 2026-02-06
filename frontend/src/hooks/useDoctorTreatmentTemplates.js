/**
 * useDoctorTreatmentTemplates - хук для персональной клинической памяти врача
 * 
 * Загружает шаблоны лечения врача по коду МКБ-10.
 * Источник: прошлые подписанные EMR врача.
 * 
 * @example
 * const { templates, loading, error, pinTemplate } = useDoctorTreatmentTemplates({
 *   icd10Code: 'I10',
 *   enabled: !!icd10Code,
 * });
 */

import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

/**
 * @typedef {Object} TreatmentTemplate
 * @property {string} id - Уникальный ID
 * @property {string} treatment_text - Текст назначения
 * @property {string} icd10_code - Код МКБ-10
 * @property {number} usage_count - Количество использований
 * @property {string} last_used_at - Дата последнего использования
 * @property {boolean} is_pinned - Закреплён ли (📌)
 * @property {string|null} frequency_label - "часто" / "редко" / null
 */

/**
 * Hook для получения шаблонов лечения по диагнозу
 * 
 * @param {Object} options
 * @param {string} options.icd10Code - Код МКБ-10
 * @param {boolean} options.enabled - Включен ли fetch
 * @param {number} options.limit - Максимум результатов
 * @returns {{ templates: TreatmentTemplate[], loading: boolean, error: string|null, refetch: Function, pinTemplate: Function, unpinTemplate: Function }}
 */
export function useDoctorTreatmentTemplates({
    icd10Code = '',
    enabled = true,
    limit = 5,
} = {}) {
    const [templates, setTemplates] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const fetchTemplates = useCallback(async () => {
        if (!enabled || !icd10Code) {
            setTemplates([]);
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const response = await api.get('/emr/doctor-templates/treatment', {
                params: { icd10: icd10Code, limit }
            });

            const data = response.data;
            setTemplates(data.templates || []);
        } catch (err) {
            console.error('[DoctorTemplates] Error fetching:', err);
            setError(err.message || 'Ошибка загрузки шаблонов');
            setTemplates([]);
        } finally {
            setLoading(false);
        }
    }, [icd10Code, enabled, limit]);

    // Fetch при изменении icd10Code
    useEffect(() => {
        fetchTemplates();
    }, [fetchTemplates]);

    // 📌 Pin template
    const pinTemplate = useCallback(async (templateId) => {
        try {
            await api.post(`/emr/doctor-templates/treatment/${templateId}/pin`);
            await fetchTemplates(); // Refresh
            return true;
        } catch (err) {
            console.error('[DoctorTemplates] Error pinning:', err);
            return false;
        }
    }, [fetchTemplates]);

    // Unpin template
    const unpinTemplate = useCallback(async (templateId) => {
        try {
            await api.delete(`/emr/doctor-templates/treatment/${templateId}/pin`);
            await fetchTemplates(); // Refresh
            return true;
        } catch (err) {
            console.error('[DoctorTemplates] Error unpinning:', err);
            return false;
        }
    }, [fetchTemplates]);

    // ✏️ Update template (inline edit)
    const updateTemplate = useCallback(async (templateId, newText, mode = 'replace') => {
        try {
            await api.put(`/emr/doctor-templates/treatment/${templateId}`, {
                treatment_text: newText,
                mode, // 'replace' | 'save_as_new'
            });
            await fetchTemplates(); // Refresh
            return true;
        } catch (err) {
            console.error('[DoctorTemplates] Error updating:', err);
            return false;
        }
    }, [fetchTemplates]);

    return {
        templates,
        loading,
        error,
        refetch: fetchTemplates,
        hasTemplates: templates.length > 0,
        pinTemplate,
        unpinTemplate,
        updateTemplate,
    };
}

/**
 * Удалить шаблон лечения (soft delete)
 * 
 * @param {string} templateId - ID шаблона
 * @returns {Promise<boolean>}
 */
export async function deleteTemplate(templateId) {
    try {
        await api.delete(`/emr/doctor-templates/treatment/${templateId}`);
        return true;
    } catch (err) {
        console.error('[DoctorTemplates] Error deleting:', err);
        return false;
    }
}

export default useDoctorTreatmentTemplates;

