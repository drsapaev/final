/**
 * API клиент для Registrar Batch операций
 * 
 * Решает проблему UI Row ↔ API Entry mismatch:
 * - UI показывает пациента как одну строку  
 * - API оперирует множеством entries
 * 
 * Этот модуль обеспечивает атомарные операции над всеми записями пациента за день.
 */

import { apiRequest } from './client';

/**
 * Получить все записи пациента на указанную дату
 * 
 * @param {number} patientId - ID пациента
 * @param {string} date - Дата в формате YYYY-MM-DD
 * @returns {Promise<Object>} - { online_queue_entries, visits, aggregated }
 */
export async function getPatientEntriesForDate(patientId: string | number, date: string) {
    return apiRequest('GET', `/registrar/batch/patients/${patientId}/entries/${date}`);
}

/**
 * ⭐ Атомарное batch-обновление записей пациента за день
 * 
 * @param {number} patientId - ID пациента
 * @param {string} date - Дата в формате YYYY-MM-DD
 * @param {Object} updates - Объект с обновлениями
 * @param {Array} updates.entries - Массив действий над записями
 * @param {Object} [updates.common_updates] - Общие обновления для всех записей
 * @returns {Promise<Object>} - { success, updated_entries, aggregated_row }
 * 
 * @example
 * const result = await batchUpdatePatientEntries(42, '2024-12-17', {
 *   entries: [
 *     { id: 123, action: 'update', status: 'called' },
 *     { id: 124, action: 'cancel', reason: 'Patient request' },
 *     { id: null, action: 'create', specialty: 'cardiology' }
 *   ],
 *   common_updates: {
 *     payment_type: 'card',
 *     discount_mode: 'percent_10'
 *   }
 * });
 */
export async function batchUpdatePatientEntries(patientId: string | number, date: string, updates: Record<string, unknown>) {
    return apiRequest('PATCH', `/registrar/batch/patients/${patientId}/entries/${date}`, {
        data: updates
    });
}

/**
 * Отменить ВСЕ записи пациента на указанную дату
 * 
 * @param {number} patientId - ID пациента
 * @param {string} date - Дата в формате YYYY-MM-DD
 * @param {string} [reason='bulk_cancel'] - Причина отмены
 * @returns {Promise<Object>} - { success, cancelled_count, details }
 * 
 * @example
 * const result = await cancelAllPatientEntries(42, '2024-12-17', 'Patient no-show');
 */
export async function cancelAllPatientEntries(patientId: string | number, date: string, reason: string = 'bulk_cancel') {
    return apiRequest('DELETE', `/registrar/batch/patients/${patientId}/entries/${date}?reason=${encodeURIComponent(reason)}`);
}

/**
 * Helper: Форматирует дату в YYYY-MM-DD
 */
export function formatDateForAPI(date: string | Date | null | undefined): string | null {
    if (!date) return null;
    if (typeof date === 'string') return date;

    const d = date instanceof Date ? date : new Date(date);
    return d.toISOString().split('T')[0];
}

/**
 * Создаёт объект обновлений для batch операции
 * 
 * @param {Object} options
 * @param {Array} options.updates - Массив обновлений [{id, ...changes}]
 * @param {Array} options.cancels - Массив ID для отмены [id, id, ...]
 * @param {Array} options.creates - Массив новых записей [{specialty, service_id, ...}]
 * @param {Object} options.common - Общие обновления
 * @returns {Object} - BatchUpdateRequest
 */
interface BatchUpdateEntry {
    id: string | number | null;
    action: string;
    service_id?: string | number;
    service_code?: string;
    doctor_id?: string | number;
    status?: string;
    reason?: string;
    specialty?: string;
}

interface BatchUpdateItem {
    id?: string | number;
    service_id?: string | number;
    service_code?: string;
    doctor_id?: string | number;
    status?: string;
    reason?: string;
    specialty?: string;
}

interface BatchCancelItem {
    id?: string | number;
    reason?: string;
}

interface BatchCreateItem {
    specialty?: string;
    service_id?: string | number;
    service_code?: string;
    doctor_id?: string | number;
}

export function buildBatchRequest({
    updates = [],
    cancels = [],
    creates = [],
    common = null,
}: {
    updates?: BatchUpdateItem[];
    cancels?: Array<string | number | BatchCancelItem>;
    creates?: BatchCreateItem[];
    common?: Record<string, unknown> | null;
}): { entries: BatchUpdateEntry[]; common_updates?: Record<string, unknown> } {
    const entries: BatchUpdateEntry[] = [];

    // Обновления
    updates.forEach((update: BatchUpdateItem) => {
        entries.push({
            id: update.id!,
            action: 'update',
            service_id: update.service_id,
            service_code: update.service_code,
            doctor_id: update.doctor_id,
            status: update.status,
        });
    });

    // Отмены
    cancels.forEach((id: string | number | BatchCancelItem) => {
        const cancelItem = typeof id === 'object' && id !== null ? id as BatchCancelItem : { id: id as string | number };
        entries.push({
            id: cancelItem.id!,
            action: 'cancel',
            reason: cancelItem.reason || 'cancelled',
        });
    });

    // Создания
    creates.forEach((create: BatchCreateItem) => {
        entries.push({
            id: null,
            action: 'create',
            specialty: create.specialty,
            service_id: create.service_id,
            service_code: create.service_code,
            doctor_id: create.doctor_id,
        });
    });

    return {
        entries,
        common_updates: common || undefined,
    };
}

export default {
    getPatientEntriesForDate,
    batchUpdatePatientEntries,
    cancelAllPatientEntries,
    formatDateForAPI,
    buildBatchRequest,
};
