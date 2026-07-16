import logger from '../utils/logger';
import { getApiOrigin } from '../api/runtime';
import { tokenManager } from '../utils/tokenManager';

// Единый сервис работы с очередью и приемом пациента

function getAuthToken() {
  // Использует централизованный tokenManager для единообразия
  return tokenManager.getAccessToken() || '';
}

interface QueueRequestOptions {
  absolute?: boolean;
  headers?: Record<string, string>;
  method?: string;
  body?: unknown;
}

async function apiRequest<T = unknown>(path: string, options: QueueRequestOptions = {}): Promise<T> {
  const base = options.absolute ? '' : getApiOrigin();
  const token = getAuthToken();

  if (!token) {
    logger.error('[queueService] No auth token found');
    throw new Error('Требуется авторизация. Пожалуйста, войдите в систему.');
  }

  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {})
  };

  logger.log(`[queueService] ${options.method || 'GET'} ${path}`, { hasToken: !!token, tokenLength: token.length });

  const res = await fetch(`${base}/api/v1${path}`, {
    method: options.method || 'GET',
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined
  });

  if (!res.ok) {
    let detail = 'Ошибка запроса';
    let errorData = null;
    try {
      errorData = await res.json();
      detail = errorData.detail || errorData.message || detail;
    } catch {
      detail = `HTTP ${res.status}: ${res.statusText}`;
    }

    logger.error(`[queueService] Request failed: ${path}`, {
      status: res.status,
      statusText: res.statusText,
      detail,
      errorData
    });

    throw new Error(detail);
  }
  try {
    return await res.json();
  } catch {
    return null;
  }
}

// Глобальное уведомление об обновлении очереди
function notifyQueueUpdate(specialty: string, action: string = 'update'): void {
  logger.log('[queueService] notifyQueueUpdate:', { specialty, action });
  // Отправляем CustomEvent для синхронизации всех компонентов
  const event = new CustomEvent('queueUpdated', {
    detail: { specialty, action, timestamp: Date.now() }
  });
  window.dispatchEvent(event);
}

function hasBackendQueueAction(entry: Record<string, unknown> | null, action: string, flagName: string): boolean {
  if (!entry) return false;
  if (Array.isArray(entry.available_actions)) {
    return entry.available_actions.includes(action);
  }
  if (flagName && Object.prototype.hasOwnProperty.call(entry, flagName)) {
    return Boolean(entry[flagName]);
  }
  return false;
}

function selectNextCallEntry(queue: Record<string, unknown> | null | undefined): Record<string, unknown> | null {
  const entries = Array.isArray(queue?.entries) ? queue.entries : [];
  const backendEntryId = queue?.next_call_entry_id;

  if (backendEntryId !== undefined && backendEntryId !== null) {
    return entries.find((entry) => entry.id === backendEntryId) || { id: backendEntryId };
  }

  return entries.find((entry) => hasBackendQueueAction(entry, 'call', 'can_call')) || null;
}

export const queueService = {
  // Очередь врача на сегодня по специальности
  getTodayQueue: async (specialty) => {
    return apiRequest(`/doctor/${encodeURIComponent(specialty)}/queue/today`);
  },

  // Вызвать пациента в кабинет (по id записи очереди)
  callPatient: async (entryId) => {
    const result = await apiRequest(`/doctor/queue/${entryId}/call`, { method: 'POST' });
    // Уведомляем об обновлении
    notifyQueueUpdate('all', 'patientCalled');
    return result;
  },

  // Начать прием пациента
  startVisit: async (entryId) => {
    const result = await apiRequest(`/doctor/queue/${entryId}/start-visit`, { method: 'POST' });
    // Уведомляем об обновлении
    notifyQueueUpdate('all', 'visitStarted');
    return result;
  },

  // Завершить прием пациента (можно передать med data)
  completeVisit: async (entryId, visitData) => {
    const result = await apiRequest(`/doctor/queue/${entryId}/complete`, {
      method: 'POST',
      body: visitData || {}
    });
    // Уведомляем об обновлении после завершения приема
    notifyQueueUpdate('all', 'visitCompleted');
    logger.log('[queueService] completeVisit: отправлено уведомление об обновлении очереди');
    return result;
  },

  // Вызвать следующего ожидающего пациента по специальности
  callNextWaiting: async (specialty) => {
    const queue = await apiRequest<{ entries?: Array<Record<string, unknown>>; next_call_entry_id?: unknown }>(`/doctor/${encodeURIComponent(specialty)}/queue/today`);
    if (!queue?.entries?.length) return { success: false, message: 'Очередь пуста' };
    const nextEntry = selectNextCallEntry(queue);
    if (!nextEntry?.id) return { success: false, message: 'Нет ожидающих пациентов' };
    await apiRequest(`/doctor/queue/${nextEntry.id}/call`, { method: 'POST' });
    // Уведомляем об обновлении
    notifyQueueUpdate(specialty, 'nextPatientCalled');
    return { success: true, entry: nextEntry };
  }
};
