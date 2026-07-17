// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

/**
 * Hook for Doctor Queue Management
 * Provides queue data and actions for the doctor panel
 */
import { useState, useCallback, useEffect } from 'react';
import api from '../services/api';
import logger from '../utils/logger';

const ZERO_STATS = {
    waiting: 0,
    called: 0,
    served: 0,
    total: 0
};

const hasBackendQueueAction = (entry, action, flagName) => {
    if (!entry) return false;
    if (Array.isArray(entry.available_actions)) {
        return entry.available_actions.includes(action);
    }
    if (flagName && Object.prototype.hasOwnProperty.call(entry, flagName)) {
        return Boolean(entry[flagName]);
    }
    return false;
};

const selectNextCallEntryId = (queuePayload) => {
    const backendEntryId = queuePayload?.next_call_entry_id;
    if (backendEntryId !== undefined && backendEntryId !== null) {
        return backendEntryId;
    }

    const entries = Array.isArray(queuePayload?.entries) ? queuePayload.entries : [];
    const callableEntry = entries.find((entry) => hasBackendQueueAction(entry, 'call', 'can_call'));
    return callableEntry?.id ?? null;
};

/**
 * @param {string} specialty - Каноническая specialty/queue tag для панели врача
 */
const useDoctorQueue = (specialty = 'general') => {
    const [queue, setQueue] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [stats, setStats] = useState(ZERO_STATS);
    const [queueControls, setQueueControls] = useState({
        canCallNext: false,
        nextCallEntryId: null
    });
    const normalizedSpecialty = specialty || 'general';

    // Загрузка очереди
    const loadQueue = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await api.get(`/doctor/${encodeURIComponent(normalizedSpecialty)}/queue/today`);
            const entries = Array.isArray(response.data?.entries) ? response.data.entries : [];
            const apiStats = response.data?.stats || {};
            const nextCallEntryId = selectNextCallEntryId(response.data);

            setQueue(entries);
            setQueueControls({
                canCallNext: response.data?.can_call_next === true,
                nextCallEntryId
            });
            setStats({
                waiting: apiStats.waiting ?? entries.filter((entry) => entry.status === 'waiting').length,
                called: apiStats.called ?? entries.filter((entry) => entry.status === 'called').length,
                served: apiStats.served ?? entries.filter((entry) => entry.status === 'served').length,
                total: apiStats.total ?? entries.length
            });

            logger.info('[useDoctorQueue] Loaded specialty queue:', {
                specialty: normalizedSpecialty,
                entries: entries.length,
                queueIds: response.data?.queue_ids || []
            });
        } catch (err) {
            logger.error('[useDoctorQueue] Error loading queue:', err);
            setQueue([]);
            setStats(ZERO_STATS);
            setQueueControls({ canCallNext: false, nextCallEntryId: null });
            setError(err.response?.data?.detail || err.message || 'Ошибка загрузки очереди');
        } finally {
            setLoading(false);
        }
    }, [normalizedSpecialty]);

    // Вызвать следующего пациента
    const callNext = useCallback(async () => {
        try {
            const currentQueue = await api.get(`/doctor/${encodeURIComponent(normalizedSpecialty)}/queue/today`);
            const nextCallEntryId = selectNextCallEntryId(currentQueue.data);
            if (!nextCallEntryId) {
                return { success: false, message: 'Нет ожидающих пациентов' };
            }

            const response = await api.post(`/doctor/queue/${nextCallEntryId}/call`);
            await loadQueue(); // Обновляем очередь
            return response.data;
        } catch (err) {
            logger.error('[useDoctorQueue] Error calling next:', err);
            throw err;
        }
    }, [loadQueue, normalizedSpecialty]);

    // Отметить неявку
    const markNoShow = useCallback(async (entryId) => {
        try {
            const response = await api.post(`/queue/entry/${entryId}/no-show`);
            await loadQueue();
            return response.data;
        } catch (err) {
            logger.error('[useDoctorQueue] Error marking no-show:', err);
            throw err;
        }
    }, [loadQueue]);

    // Восстановить пациента следующим
    const restoreToNext = useCallback(async (entryId, reason = '') => {
        try {
            const response = await api.post(`/queue/entry/${entryId}/restore-next`, { reason });
            await loadQueue();
            return response.data;
        } catch (err) {
            logger.error('[useDoctorQueue] Error restoring to next:', err);
            throw err;
        }
    }, [loadQueue]);

    // Отправить на обследование
    const sendToDiagnostics = useCallback(async (entryId) => {
        try {
            const response = await api.post(`/queue/entry/${entryId}/diagnostics`);
            await loadQueue();
            return response.data;
        } catch (err) {
            logger.error('[useDoctorQueue] Error sending to diagnostics:', err);
            throw err;
        }
    }, [loadQueue]);

    // Отметить как incomplete
    const markIncomplete = useCallback(async (entryId, reason) => {
        try {
            const response = await api.post(`/queue/entry/${entryId}/incomplete`, { reason });
            await loadQueue();
            return response.data;
        } catch (err) {
            logger.error('[useDoctorQueue] Error marking incomplete:', err);
            throw err;
        }
    }, [loadQueue]);

    // Завершить приём (served)
    const completeVisit = useCallback(async (entryId) => {
        try {
            const response = await api.post(`/doctor/queue/${entryId}/complete`);
            await loadQueue();
            return response.data;
        } catch (err) {
            logger.error('[useDoctorQueue] Error completing visit:', err);
            throw err;
        }
    }, [loadQueue]);

    // Авто-обновление каждые 30 секунд
    useEffect(() => {
        loadQueue();
        const interval = setInterval(loadQueue, 30000);
        return () => clearInterval(interval);
    }, [loadQueue]);

    return {
        queue,
        loading,
        error,
        stats,
        canCallNext: queueControls.canCallNext,
        nextCallEntryId: queueControls.nextCallEntryId,
        loadQueue,
        callNext,
        markNoShow,
        restoreToNext,
        sendToDiagnostics,
        markIncomplete,
        completeVisit
    };
};

export default useDoctorQueue;
