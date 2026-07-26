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
export const getQueueStatus = async (queueId: string | number): Promise<Record<string, unknown>> => {
  try {
    const response = await api.get(`/queue/status/${queueId}`);
    return response.data as Record<string, unknown>;
  } catch (error) {
    throw new Error('Не удалось получить статус очереди. Проверьте соединение и попробуйте снова.');
  }
};

/**
 * Получить состояние очереди по специалисту и дню
 */
export const getQueueStatusBySpecialist = async (specialistId: string | number, day: string | null = null): Promise<Record<string, unknown>> => {
  const queryDay = day || new Date().toISOString().split('T')[0];
  try {
    const response = await api.get('/queue/status/by-specialist/', {
      params: { specialist_id: specialistId, day: queryDay },
    });
    return response.data as Record<string, unknown>;
  } catch (error) {
    throw new Error('Не удалось получить очередь специалиста. Проверьте соединение и попробуйте снова.');
  }
};

/**
 * Переместить запись в очереди на новую позицию
 */
export const moveQueueEntry = async (entryId: string | number, newPosition: number): Promise<Record<string, unknown>> => {
  try {
    const response = await api.put('/queue/move-entry', {
      entry_id: entryId,
      new_position: newPosition,
    });
    return response.data as Record<string, unknown>;
  } catch (error) {
    throw new Error('Не удалось переместить запись в очереди. Проверьте соединение и попробуйте снова.');
  }
};

/**
 * Изменить порядок нескольких записей в очереди
 */
export const reorderQueue = async (queueId: string | number, entryOrders: unknown[]): Promise<Record<string, unknown>> => {
  try {
    const response = await api.put('/queue/reorder', {
      queue_id: queueId,
      entry_orders: entryOrders,
    });
    return response.data as Record<string, unknown>;
  } catch (error) {
    throw new Error('Не удалось изменить порядок очереди. Проверьте соединение и попробуйте снова.');
  }
};

interface ServerQueueEntry {
  id: string | number;
  number: number;
  patient_name: string;
  phone: string;
  source: string;
  status: string;
  created_at: string;
  called_at: string;
  [key: string]: unknown;
}

interface ServerQueueData {
  queue_id?: string | number;
  entries?: ServerQueueEntry[];
  [key: string]: unknown;
}

/**
 * Преобразовать данные очереди от сервера в формат для UI
 */
export const formatQueueData = (serverQueue: ServerQueueData | null | undefined): Record<string, unknown>[] => {
  if (!serverQueue || !serverQueue.entries) {
    return [];
  }

  return serverQueue.entries.map((entry: ServerQueueEntry) => ({
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
export const useQueueManager = (specialistId: string | number | null | undefined) => {
  const [queue, setQueue] = useState<Record<string, unknown>[]>([]);
  const [queueId, setQueueId] = useState<string | number | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadQueue = async () => {
    if (!specialistId) return;

    setLoading(true);
    setError(null);

    try {
      const queueData = await getQueueStatusBySpecialist(specialistId);
      setQueueId((queueData.queue_id as string | number | undefined) ?? null);
      setQueue(formatQueueData(queueData as ServerQueueData));
    } catch (err) {
      logger.error('Error loading queue:', err);
      setError(getErrorMessage(err, 'Не удалось загрузить очередь. Проверьте соединение и попробуйте снова.'));
    } finally {
      setLoading(false);
    }
  };

  const moveEntry = async (entryId: string | number, newPosition: number): Promise<Record<string, unknown>> => {
    try {
      const result = await moveQueueEntry(entryId, newPosition);
      if (result.success && result.queue_info) {
        setQueue(formatQueueData(result.queue_info as ServerQueueData));
      }
      return result;
    } catch (err) {
      logger.error('Error moving queue entry:', err);
      throw err;
    }
  };

  const reorderEntries = async (entryOrders: unknown[]): Promise<Record<string, unknown>> => {
    if (!queueId) {
      throw new Error('Queue ID not available');
    }

    try {
      const result = await reorderQueue(queueId, entryOrders);
      if (result.success && result.queue_info) {
        setQueue(formatQueueData(result.queue_info as ServerQueueData));
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
