/**
 * API утилиты для работы с очередями
 *
 * UX Audit: миграция 4 raw fetch() → api/client.js (axios).
 * Удалены: getApiBaseUrl, tokenManager, getAuthToken, createHeaders —
 * всё это обрабатывается централизованно через axios-interceptor.
 */

import { useState } from 'react';
import { getErrorMessage } from '../utils/errorHandler';
import logger from '../utils/logger';
import { api } from '../api/client';

/**
 * Получить состояние очереди по ID
 */
export const getQueueStatus = async (queueId) => {
  try {
    const response = await api.get(`/queue/status/${queueId}`);
    return response.data;
  } catch (error) {
    throw new Error('Не удалось получить статус очереди. Проверьте соединение и попробуйте снова.');
  }
};

/**
 * Получить состояние очереди по специалисту и дню
 */
export const getQueueStatusBySpecialist = async (specialistId, day = null) => {
  const queryDay = day || new Date().toISOString().split('T')[0];
  try {
    const response = await api.get('/queue/status/by-specialist/', {
      params: { specialist_id: specialistId, day: queryDay },
    });
    return response.data;
  } catch (error) {
    throw new Error('Не удалось получить очередь специалиста. Проверьте соединение и попробуйте снова.');
  }
};

/**
 * Переместить запись в очереди на новую позицию
 */
export const moveQueueEntry = async (entryId, newPosition) => {
  try {
    const response = await api.put('/queue/move-entry', {
      entry_id: entryId,
      new_position: newPosition,
    });
    return response.data;
  } catch (error) {
    throw new Error('Не удалось переместить запись в очереди. Проверьте соединение и попробуйте снова.');
  }
};

/**
 * Изменить порядок нескольких записей в очереди
 */
export const reorderQueue = async (queueId, entryOrders) => {
  try {
    const response = await api.put('/queue/reorder', {
      queue_id: queueId,
      entry_orders: entryOrders,
    });
    return response.data;
  } catch (error) {
    throw new Error('Не удалось изменить порядок очереди. Проверьте соединение и попробуйте снова.');
  }
};

/**
 * Преобразовать данные очереди от сервера в формат для UI
 */
export const formatQueueData = (serverQueue) => {
  if (!serverQueue || !serverQueue.entries) {
    return [];
  }

  return serverQueue.entries.map(entry => ({
    id: entry.id,
    number: entry.number,
    patient_name: entry.patient_name,
    phone: entry.phone,
    type: entry.source === 'online' ? 'Онлайн' : 'Регистратура',
    source: entry.source,
    status: entry.status,
    created_at: entry.created_at,
    called_at: entry.called_at
  }));
};

/**
 * Хук для работы с очередью
 */
export const useQueueManager = (specialistId) => {
  const [queue, setQueue] = useState([]);
  const [queueId, setQueueId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadQueue = async () => {
    if (!specialistId) return;

    setLoading(true);
    setError(null);

    try {
      const queueData = await getQueueStatusBySpecialist(specialistId);
      setQueueId(queueData.queue_id);
      setQueue(formatQueueData(queueData));
    } catch (err) {
      logger.error('Error loading queue:', err);
      setError(getErrorMessage(err, 'Не удалось загрузить очередь. Проверьте соединение и попробуйте снова.'));
    } finally {
      setLoading(false);
    }
  };

  const moveEntry = async (entryId, newPosition) => {
    try {
      const result = await moveQueueEntry(entryId, newPosition);
      if (result.success && result.queue_info) {
        setQueue(formatQueueData(result.queue_info));
      }
      return result;
    } catch (err) {
      logger.error('Error moving queue entry:', err);
      throw err;
    }
  };

  const reorderEntries = async (entryOrders) => {
    if (!queueId) {
      throw new Error('Queue ID not available');
    }

    try {
      const result = await reorderQueue(queueId, entryOrders);
      if (result.success && result.queue_info) {
        setQueue(formatQueueData(result.queue_info));
      }
      return result;
    } catch (err) {
      logger.error('Error reordering queue:', err);
      throw err;
    }
  };

  return {
    queue,
    queueId,
    loading,
    error,
    loadQueue,
    moveEntry,
    reorderEntries,
    setQueue // Для оптимистичных обновлений
  };
};
