/**
 * API утилиты для работы с очередями
 */

import { useState } from 'react';

import logger from '../utils/logger';
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

/**
 * Получить токен авторизации
 */
const getAuthToken = () => localStorage.getItem('access_token');

/**
 * Создать заголовки для API запросов
 */
const createHeaders = () => ({
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${getAuthToken()}`
});

/**
 * Получить состояние очереди по ID
 */
export const getQueueStatus = async (queueId) => {
  const response = await fetch(`${API_BASE}/queue/status/${queueId}`, {
    headers: createHeaders()
  });
  
  if (!response.ok) {
    throw new Error(`Failed to get queue status: ${response.statusText}`);
  }
  
  return response.json();
};

/**
 * Получить состояние очереди по специалисту и дню
 */
export const getQueueStatusBySpecialist = async (specialistId, day = null) => {
  const queryDay = day || new Date().toISOString().split('T')[0];
  const response = await fetch(
    `${API_BASE}/queue/status/by-specialist/?specialist_id=${specialistId}&day=${queryDay}`,
    {
      headers: createHeaders()
    }
  );
  
  if (!response.ok) {
    throw new Error(`Failed to get queue status by specialist: ${response.statusText}`);
  }
  
  return response.json();
};

/**
 * Переместить запись в очереди на новую позицию
 */
export const moveQueueEntry = async (entryId, newPosition) => {
  const response = await fetch(`${API_BASE}/queue/move-entry`, {
    method: 'PUT',
    headers: createHeaders(),
    body: JSON.stringify({
      entry_id: entryId,
      new_position: newPosition
    })
  });
  
  if (!response.ok) {
    throw new Error(`Failed to move queue entry: ${response.statusText}`);
  }
  
  return response.json();
};

/**
 * Изменить порядок нескольких записей в очереди
 */
export const reorderQueue = async (queueId, entryOrders) => {
  const response = await fetch(`${API_BASE}/queue/reorder`, {
    method: 'PUT',
    headers: createHeaders(),
    body: JSON.stringify({
      queue_id: queueId,
      entry_orders: entryOrders
    })
  });
  
  if (!response.ok) {
    throw new Error(`Failed to reorder queue: ${response.statusText}`);
  }
  
  return response.json();
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
      setError(err.message);
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
