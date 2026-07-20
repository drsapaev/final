/**
 * Hook for Doctor Queue Management.
 * Provides queue data and actions for the doctor panel.
 */
import { useCallback, useEffect, useState } from 'react';
import api from '../services/api';
import logger from '../utils/logger';

interface QueueStats {
  waiting: number;
  called: number;
  served: number;
  total: number;
}

interface QueueControls {
  canCallNext: boolean;
  nextCallEntryId: string | number | null;
}

interface QueueEntry {
  id: string | number;
  status: string;
  available_actions?: string[];
  [key: string]: unknown;
}

interface QueuePayload {
  entries?: QueueEntry[];
  stats?: Partial<QueueStats>;
  can_call_next?: boolean;
  next_call_entry_id?: string | number | null;
  queue_ids?: Array<string | number>;
}

interface CatchError {
  response?: { data?: { detail?: string }; status?: number };
  message?: string;
}

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
  if (Array.isArray(entry.available_actions)) {
    return entry.available_actions.includes(action);
  }
  if (flagName && Object.prototype.hasOwnProperty.call(entry, flagName)) {
    return Boolean(entry[flagName]);
  }
  return false;
};

const selectNextCallEntryId = (
  queuePayload: QueuePayload | null | undefined,
): string | number | null => {
  const backendEntryId = queuePayload?.next_call_entry_id;
  if (backendEntryId !== undefined && backendEntryId !== null) {
    return backendEntryId;
  }

  const entries = Array.isArray(queuePayload?.entries) ? queuePayload!.entries! : [];
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

  const loadQueue = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError(null);

    try {
      const response = await api.get(`/doctor/${encodeURIComponent(normalizedSpecialty)}/queue/today`);
      const data = response.data as QueuePayload;
      const entries = Array.isArray(data?.entries) ? data.entries : [];
      const apiStats = data?.stats || {};
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
      const e = err as CatchError;
      logger.error('[useDoctorQueue] Error loading queue:', err);
      setQueue([]);
      setStats(ZERO_STATS);
      setQueueControls({ canCallNext: false, nextCallEntryId: null });
      setError(e?.response?.data?.detail || e?.message || 'Ошибка загрузки очереди');
    } finally {
      setLoading(false);
    }
  }, [normalizedSpecialty]);

  const callNext = useCallback(async (): Promise<unknown> => {
    try {
      const currentQueue = await api.get(`/doctor/${encodeURIComponent(normalizedSpecialty)}/queue/today`);
      const nextCallEntryId = selectNextCallEntryId(currentQueue.data as QueuePayload);
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
