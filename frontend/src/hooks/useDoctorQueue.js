/**
 * Hook for Doctor Queue Management
 * Provides queue data and actions for the doctor panel
 */
import { useState, useCallback, useEffect } from 'react';
import api from '../services/api';
import logger from '../utils/logger';

/**
 * @param {number|null} doctorId - ID врача (если null, будет получен из текущего пользователя)
 * @param {object|null} currentUser - Текущий пользователь из контекста
 */
const useDoctorQueue = (doctorId = null, currentUser = null) => {
    const [queue, setQueue] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [resolvedDoctorId, setResolvedDoctorId] = useState(doctorId);
    const [stats, setStats] = useState({
        waiting: 0,
        called: 0,
        served: 0,
        total: 0
    });

    // Получаем doctor_id если не передан явно
    useEffect(() => {
        const resolveDoctorId = async () => {
            if (doctorId) {
                setResolvedDoctorId(doctorId);
                return;
            }

            if (currentUser?.doctor_id) {
                setResolvedDoctorId(currentUser.doctor_id);
                return;
            }

            // Пробуем получить doctor_id через API
            if (currentUser?.id) {
                try {
                    const response = await api.get(`/doctors/by-user/${currentUser.id}`);
                    if (response.data?.id) {
                        setResolvedDoctorId(response.data.id);
                        logger.info('[useDoctorQueue] Resolved doctor_id from API:', response.data.id);
                    }
                } catch (err) {
                    logger.warn('[useDoctorQueue] Could not resolve doctor_id:', err.message);
                }
            }
        };

        resolveDoctorId();
    }, [doctorId, currentUser]);

    // Загрузка очереди
    const loadQueue = useCallback(async () => {
        if (!resolvedDoctorId) {
            logger.warn('[useDoctorQueue] No doctorId resolved yet');
            setLoading(false);
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const today = new Date().toISOString().split('T')[0];
            const response = await api.get('/registrar/queues/today', {
                params: { target_date: today }
            });

            // Находим очередь для этого врача
            const queues = response.data?.queues || [];
            const doctorQueue = queues.find(q =>
                q.specialist_id === resolvedDoctorId ||
                q.doctor_id === resolvedDoctorId
            );

            if (doctorQueue) {
                // Сортируем по priority DESC, queue_time ASC
                const sortedEntries = [...(doctorQueue.entries || [])].sort((a, b) => {
                    // Сначала по priority (1 = следующий, идёт первым)
                    const priorityDiff = (b.priority || 0) - (a.priority || 0);
                    if (priorityDiff !== 0) return priorityDiff;
                    // Затем по queue_time
                    return new Date(a.queue_time || a.created_at) - new Date(b.queue_time || b.created_at);
                });

                setQueue(sortedEntries);
                setStats({
                    waiting: sortedEntries.filter(e => e.status === 'waiting').length,
                    called: sortedEntries.filter(e => e.status === 'called').length,
                    served: sortedEntries.filter(e => e.status === 'served').length,
                    total: sortedEntries.length
                });
            } else {
                setQueue([]);
                setStats({ waiting: 0, called: 0, served: 0, total: 0 });
            }

            logger.info('[useDoctorQueue] Loaded queue:', { doctorId: resolvedDoctorId, entries: queue.length });
        } catch (err) {
            logger.error('[useDoctorQueue] Error loading queue:', err);
            setError(err.message || 'Ошибка загрузки очереди');
        } finally {
            setLoading(false);
        }
    }, [resolvedDoctorId]);

    // Вызвать следующего пациента
    const callNext = useCallback(async () => {
        if (!resolvedDoctorId) return null;

        try {
            const response = await api.post(`/queue/${resolvedDoctorId}/call-next`);
            await loadQueue(); // Обновляем очередь
            return response.data;
        } catch (err) {
            logger.error('[useDoctorQueue] Error calling next:', err);
            throw err;
        }
    }, [resolvedDoctorId, loadQueue]);

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
            // Используем существующий endpoint для изменения статуса
            const response = await api.post(`/queue/entry/${entryId}/status`, null, {
                params: { status: 'served' }
            });
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
