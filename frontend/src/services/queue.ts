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

async function apiRequest<T = unknown>(path: string, options: QueueRequestOptions = {}): Promise<T | null> {
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
    let errorData: unknown = null;
    try {
      errorData = await res.json();
      detail = (errorData as { detail?: string; message?: string })?.detail || (errorData as { message?: string })?.message || detail;
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
    return await res.json() as T;
  } catch {
    return null as T;
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

// DOCFLOW-FE-001 / DOCFLOW-FE-003 (audit 3886): a doctor-queue write is
// CONFIRMED only by an explicit `success: true` DTO in a parseable 2xx
// body. `apiRequest` returns `null` for a 2xx body that fails to parse —
// that outcome is AMBIGUOUS (the server may have committed; no blind
// retry), while `success: false` is an explicit rejection. Neither may be
// reported as success, reset clinical UI state, or fire the optimistic
// `queueUpdated` refresh event.
export type QueueWriteResult = {
  success: boolean;
  unknown?: boolean;
  message?: string;
  entry?: Record<string, unknown>;
  [key: string]: unknown;
};

const AMBIGUOUS_QUEUE_WRITE_MESSAGE =
  'Ответ сервера не удалось прочитать — завершение не подтверждено. Состояние очереди уточняется у сервера; не повторяйте операцию автоматически. / Unreadable server response — the operation is NOT confirmed. The queue state is being reconciled with the server; do not blindly retry.';

const REJECTED_QUEUE_WRITE_MESSAGE =
  'Сервер отклонил операцию. / The server rejected the operation.';

function queueWriteAck(result: Record<string, unknown> | null | undefined): QueueWriteResult {
  if (result && typeof result === 'object' && result.success === true) {
    return { success: true, ...result };
  }
  if (result === null || result === undefined || typeof result !== 'object') {
    return { success: false, unknown: true, message: AMBIGUOUS_QUEUE_WRITE_MESSAGE };
  }
  const detail = (result as { detail?: unknown; message?: unknown }).detail
    ?? (result as { message?: unknown }).message;
  return {
    success: false,
    message: typeof detail === 'string' && detail.trim() ? detail : REJECTED_QUEUE_WRITE_MESSAGE,
  };
}

function selectNextCallEntry(
  queue: Record<string, unknown> | null | undefined,
): { entry: Record<string, unknown> | null; contractError: string | null } {
  const entries = Array.isArray(queue?.entries) ? queue.entries : [];

  // QAPI-FE-001 (audit 3886): the backend `_queue_ops` SSOT computes and
  // ALWAYS returns `next_call_entry_id` (including an explicit null when
  // nothing is callable). A response WITHOUT the field is a contract
  // failure — fail closed instead of silently guessing a caller.
  if (!queue || !Object.prototype.hasOwnProperty.call(queue, 'next_call_entry_id')) {
    return {
      entry: null,
      contractError:
        'Контракт очереди нарушен: ответ сервера не содержит next_call_entry_id — вызов не выполнен (SSOT сервера не подтверждает кандидата). / Queue contract failure: next_call_entry_id missing in the server response — refusing to guess a caller.',
    };
  }

  const backendEntryId = queue.next_call_entry_id;

  // QAPI-FE-001: an EXPLICIT server null means «no callable entry» — the
  // old local `entries.find(can_call)` fallback second-guessed the server's
  // own choice on stale/inconsistent payloads and could call an entry the
  // canonical response had just declined to select.
  if (backendEntryId === null || backendEntryId === undefined) {
    return { entry: null, contractError: null };
  }

  return { entry: entries.find((entry) => entry.id === backendEntryId) || { id: backendEntryId }, contractError: null };
}

export const queueService = {
  // Очередь врача на сегодня по специальности
  getTodayQueue: async (specialty: string) => {
    return apiRequest(`/doctor/${encodeURIComponent(specialty)}/queue/today`);
  },

  // Вызвать пациента в кабинет (по id записи очереди)
  callPatient: async (entryId: string | number) => {
    const result = await apiRequest(`/doctor/queue/${entryId}/call`, { method: 'POST' });
    // Уведомляем об обновлении
    notifyQueueUpdate('all', 'patientCalled');
    return result;
  },

  // Начать прием пациента
  startVisit: async (entryId: string | number) => {
    const result = await apiRequest(`/doctor/queue/${entryId}/start-visit`, { method: 'POST' });
    // Уведомляем об обновлении
    notifyQueueUpdate('all', 'visitStarted');
    return result;
  },

  // Завершить прием пациента (можно передать med data)
  completeVisit: async (entryId: string | number, visitData: Record<string, unknown>): Promise<QueueWriteResult> => {
    const result = await apiRequest<Record<string, unknown> | null>(`/doctor/queue/${entryId}/complete`, {
      method: 'POST',
      body: visitData || {}
    });
    // DOCFLOW-FE-001 (audit 3886): only an explicit `success: true` DTO
    // confirms the completion. An ambiguous (unparseable 2xx body) or
    // explicitly rejected outcome must NOT fire the optimistic
    // `queueUpdated` event and must NOT be presented as a success — the
    // server may have committed, so the caller reconciles with the
    // canonical queue snapshot instead of blindly retrying.
    const ack = queueWriteAck(result);
    if (ack.success !== true) {
      logger.error('[queueService] completeVisit NOT confirmed:', ack.unknown ? 'ambiguous-2xx' : 'rejected', ack.message);
      return ack;
    }
    // Уведомляем об обновлении после завершения приема (только подтвержденное завершение)
    notifyQueueUpdate('all', 'visitCompleted');
    logger.log('[queueService] completeVisit: отправлено уведомление об обновлении очереди');
    return ack;
  },

  // Вызвать следующего ожидающего пациента по специальности
  callNextWaiting: async (specialty: string) => {
    const queue = await apiRequest<{ entries?: Array<Record<string, unknown>>; next_call_entry_id?: unknown }>(`/doctor/${encodeURIComponent(specialty)}/queue/today`);
    if (!queue?.entries?.length) return { success: false, message: 'Очередь пуста' };
    // QAPI-FE-001 (audit 3886): the backend's canonical next_call_entry_id
    // is the ONLY source for the call target — an explicit null stops the
    // call, and a missing field fails closed as a contract error. The old
    // local can_call fallback could invent a candidate the server had
    // explicitly declined to select.
    const { entry: nextEntry, contractError } = selectNextCallEntry(queue);
    if (contractError) {
      logger.error('[queueService] callNextWaiting refused:', contractError);
      return { success: false, message: contractError };
    }
    if (!nextEntry?.id) return { success: false, message: 'Нет ожидающих пациентов' };
    // DOCFLOW-FE-003 (audit 3886): the call POST result is authoritative.
    // The old code ignored the response and always fabricated
    // `{success: true, entry: <pre-call GET snapshot>}`. Only a confirmed
    // `success: true` may notify and report the call, and the
    // backend-returned entry (when present) is the canonical one — the
    // pre-call GET snapshot may already be stale.
    const callResult = await apiRequest<Record<string, unknown> | null>(`/doctor/queue/${nextEntry.id}/call`, { method: 'POST' });
    const callAck = queueWriteAck(callResult);
    if (callAck.success !== true) {
      logger.error('[queueService] callNextWaiting NOT confirmed:', callAck.unknown ? 'ambiguous-2xx' : 'rejected', callAck.message);
      return callAck;
    }
    // Уведомляем об обновлении (только подтвержденный вызов)
    notifyQueueUpdate(specialty, 'nextPatientCalled');
    const canonicalEntry: Record<string, unknown> =
      callResult && typeof callResult === 'object' && 'entry' in callResult && (callResult as { entry?: unknown }).entry
        ? (callResult as { entry: Record<string, unknown> }).entry
        : nextEntry;
    return { success: true, entry: canonicalEntry };
  }
};
