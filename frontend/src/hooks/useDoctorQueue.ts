/**
 * Hook for Doctor Queue Management.
 * Provides queue data and actions for the doctor panel.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import logger from '../utils/logger';
import type {
  QueueEntry,
  QueueStats,
} from '../types/domain/queue';
// ADR-0016: canonical error types from types/errors.ts.
import type { HttpApiError } from '../types/errors';

// Doctor-queue-specific payload envelope. The backend returns this shape from
// /queue/{id} with queue entries + stats + can_call_next metadata. The
// generic QueuePayload in domain/queue.ts has `queues: QueueData[]`, but
// the doctor-panel endpoint returns a single queue object with entries
// inline — different shape, so we keep a local interface.
interface DoctorQueuePayload {
  entries?: QueueEntry[];
  stats?: QueueStats;
  can_call_next?: boolean;
  next_call_entry_id?: string | number | null;
  queue_ids?: Array<string | number>;
  [key: string]: unknown;
}

interface QueueControls {
  canCallNext: boolean;
  nextCallEntryId: string | number | null;
}

// ADR-0016: CatchError replaced by canonical HttpApiError.

const ZERO_STATS: QueueStats = {
  waiting: 0,
  called: 0,
  served: 0,
  total: 0,
};

const hasBackendQueueAction = (
  entry: QueueEntry | null | undefined,
  action: string,
  flagName: string,
): boolean => {
  if (!entry) return false;
  const availableActions = entry.available_actions as string[] | undefined;
  if (Array.isArray(availableActions)) {
    return availableActions.includes(action);
  }
  if (flagName && Object.prototype.hasOwnProperty.call(entry, flagName)) {
    return Boolean((entry as unknown as Record<string, unknown>)[flagName]);
  }
  return false;
};

const selectNextCallEntryId = (
  queuePayload: DoctorQueuePayload | null | undefined,
): string | number | null => {
  const backendEntryId = queuePayload?.next_call_entry_id;
  if (backendEntryId !== undefined && backendEntryId !== null) {
    return backendEntryId;
  }

  const entries = Array.isArray(queuePayload?.entries) ? queuePayload?.entries ?? [] : [];
  const callableEntry = entries.find((entry) => hasBackendQueueAction(entry, 'call', 'can_call'));
  return callableEntry?.id ?? null;
};

export interface UseDoctorQueueReturn {
  queue: QueueEntry[];
  loading: boolean;
  error: string | null;
  stats: QueueStats;
  canCallNext: boolean;
  nextCallEntryId: string | number | null;
  loadQueue: () => Promise<void>;
  callNext: () => Promise<unknown>;
  markNoShow: (entryId: string | number) => Promise<unknown>;
  restoreToNext: (entryId: string | number, reason?: string) => Promise<unknown>;
  sendToDiagnostics: (entryId: string | number) => Promise<unknown>;
  markIncomplete: (entryId: string | number, reason: string) => Promise<unknown>;
  completeVisit: (entryId: string | number) => Promise<unknown>;
}

const useDoctorQueue = (specialty: string = 'general'): UseDoctorQueueReturn => {
  const [queue, setQueue] = useState<QueueEntry[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<QueueStats>(ZERO_STATS);
  const [queueControls, setQueueControls] = useState<QueueControls>({
    canCallNext: false,
    nextCallEntryId: null,
  });
  const normalizedSpecialty = specialty || 'general';

  // audit/phase-8, BS-22: request-ID guard against overlapping loads.
  // Previously, the 30s polling interval could overlap with mutation-induced
  // loadQueue() calls — the later-started request could resolve first, then
  // the earlier request overwrote with stale data. The ref tracks the latest
  // request; stale responses are silently discarded.
  const loadQueueRequestIdRef = useRef(0);

  const loadQueue = useCallback(async (): Promise<void> => {
    const requestId = ++loadQueueRequestIdRef.current;
    setLoading(true);
    setError(null);

    try {
      const response = await api.get(`/doctor/${encodeURIComponent(normalizedSpecialty)}/queue/today`);
      // Discard stale responses — a newer loadQueue() has been triggered since.
      if (requestId !== loadQueueRequestIdRef.current) return;

      const data = response.data as DoctorQueuePayload;
      const entries = Array.isArray(data?.entries) ? data.entries : [];
      const apiStats: QueueStats = (data?.stats as QueueStats) || {};
      const nextCallEntryId = selectNextCallEntryId(data);

      setQueue(entries);
      setQueueControls({
        canCallNext: data?.can_call_next === true,
        nextCallEntryId,
      });
      setStats({
        waiting: apiStats.waiting ?? entries.filter((e) => e.status === 'waiting').length,
        called: apiStats.called ?? entries.filter((e) => e.status === 'called').length,
        served: apiStats.served ?? entries.filter((e) => e.status === 'served').length,
        total: apiStats.total ?? entries.length,
      });

      logger.info('[useDoctorQueue] Loaded specialty queue:', {
        specialty: normalizedSpecialty,
        entries: entries.length,
        queueIds: data?.queue_ids || [],
      });
    } catch (err) {
      if (requestId !== loadQueueRequestIdRef.current) return;
      const e = err as HttpApiError;
      logger.error('[useDoctorQueue] Error loading queue:', err);
      setQueue([]);
      setStats(ZERO_STATS);
      setQueueControls({ canCallNext: false, nextCallEntryId: null });
      const detail = e?.response?.data?.detail;
      setError((typeof detail === 'string' && detail) || e?.message || 'Ошибка загрузки очереди');
    } finally {
      if (requestId === loadQueueRequestIdRef.current) {
        setLoading(false);
      }
    }
  }, [normalizedSpecialty]);

  const callNext = useCallback(async (): Promise<unknown> => {
    try {
      const currentQueue = await api.get(`/doctor/${encodeURIComponent(normalizedSpecialty)}/queue/today`);
      const nextCallEntryId = selectNextCallEntryId(currentQueue.data as DoctorQueuePayload);
      if (!nextCallEntryId) {
        return { success: false, message: 'Нет ожидающих пациентов' };
      }

      const response = await api.post(`/doctor/queue/${nextCallEntryId}/call`, {});
      await loadQueue();
      return response.data;
    } catch (err) {
      logger.error('[useDoctorQueue] Error calling next:', err);
      throw err;
    }
  }, [loadQueue, normalizedSpecialty]);

  const markNoShow = useCallback(
    async (entryId: string | number): Promise<unknown> => {
      try {
        const response = await api.post(`/queue/entry/${entryId}/no-show`, {});
        await loadQueue();
        return response.data;
      } catch (err) {
        logger.error('[useDoctorQueue] Error marking no-show:', err);
        throw err;
      }
    },
    [loadQueue],
  );

  const restoreToNext = useCallback(
    async (entryId: string | number, reason: string = ''): Promise<unknown> => {
      try {
        const response = await api.post(`/queue/entry/${entryId}/restore-next`, { reason });
        await loadQueue();
        return response.data;
      } catch (err) {
        logger.error('[useDoctorQueue] Error restoring to next:', err);
        throw err;
      }
    },
    [loadQueue],
  );

  const sendToDiagnostics = useCallback(
    async (entryId: string | number): Promise<unknown> => {
      try {
        const response = await api.post(`/queue/entry/${entryId}/diagnostics`, {});
        await loadQueue();
        return response.data;
      } catch (err) {
        logger.error('[useDoctorQueue] Error sending to diagnostics:', err);
        throw err;
      }
    },
    [loadQueue],
  );

  const markIncomplete = useCallback(
    async (entryId: string | number, reason: string): Promise<unknown> => {
      try {
        const response = await api.post(`/queue/entry/${entryId}/incomplete`, { reason });
        await loadQueue();
        return response.data;
      } catch (err) {
        logger.error('[useDoctorQueue] Error marking incomplete:', err);
        throw err;
      }
    },
    [loadQueue],
  );

  const completeVisit = useCallback(
    async (entryId: string | number): Promise<unknown> => {
      try {
        const response = await api.post(`/doctor/queue/${entryId}/complete`, {});
        await loadQueue();
        return response.data;
      } catch (err) {
        logger.error('[useDoctorQueue] Error completing visit:', err);
        throw err;
      }
    },
    [loadQueue],
  );

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
    completeVisit,
  };
};

export default useDoctorQueue;
