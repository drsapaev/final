import { useState, useEffect, useCallback } from 'react';
import logger from '../utils/logger';
import {
  fetchAvailableSpecialists,
  fetchQueuesToday,
  generateDoctorQrToken,
  generateClinicQrToken,
  openReceptionSlot,
  closeReceptionSlot,
  callNextQueuePatient,
} from '../api/queue';
import type {
  QueueSpecialist,
  QueueStats,
  QueueEntry,
  QueueData,
  QueuePayload,
  QrData,
  LoadQueueSnapshotArgs,
  GenerateDoctorQRCodeArgs,
  GenerateClinicQRCodeArgs,
  ReceptionSlotArgs,
  QueueActionResponse,
} from '../types/domain/queue';

// Re-export domain types for backwards compatibility with any callers
// that still import from '@/hooks/useQueueManager'. New code should
// import directly from '@/types/domain/queue'.
export type {
  QueueSpecialist,
  QueueStats,
  QueueEntry,
  QueueData,
  QueuePayload,
  QrData,
  LoadQueueSnapshotArgs,
  GenerateDoctorQRCodeArgs,
  GenerateClinicQRCodeArgs,
  ReceptionSlotArgs,
  QueueActionResponse,
} from '../types/domain/queue';

// Hook-specific return type — React surface, stays local.
export interface UseQueueManagerReturn {
  loading: boolean;
  specialists: QueueSpecialist[];
  queueData: QueueData | null;
  statistics: QueueStats | null;
  qrData: QrData | null;
  loadSpecialists: () => Promise<QueueSpecialist[]>;
  loadQueueSnapshot: (args: LoadQueueSnapshotArgs) => Promise<QueueData | null>;
  generateDoctorQRCode: (args: GenerateDoctorQRCodeArgs) => Promise<QrData>;
  generateClinicQRCode: (args: GenerateClinicQRCodeArgs) => Promise<QrData>;
  openReceptionForDoctor: (args: ReceptionSlotArgs) => Promise<QueueActionResponse>;
  closeReceptionForDoctor: (args: ReceptionSlotArgs) => Promise<QueueActionResponse>;
  callNextPatientInQueue: (args: ReceptionSlotArgs) => Promise<QueueActionResponse>;
  setQrData: (data: QrData | null) => void;
}

const toError = (err: unknown, fallback: string): Error => {
  if (err instanceof Error) {
    return err;
  }
  if (typeof err === 'string') {
    return new Error(err);
  }
  if (err && typeof err === 'object' && 'detail' in err) {
    return new Error(
      typeof (err as Record<string, unknown>).detail === 'string' ? (err as Record<string, unknown>).detail as string : JSON.stringify((err as Record<string, unknown>).detail)
    );
  }
  return new Error(fallback);
};

const pickQueueForDoctor = (
  payload: QueuePayload | null | undefined,
  specialistId: string | number,
  doctor?: QueueSpecialist,
): QueueData | null => {
  if (!payload?.queues) {
    logger.warn('[useQueueManager] pickQueueForDoctor: payload.queues отсутствует');
    return null;
  }

  const doctorId = Number(specialistId);

  // ✅ ОТЛАДКА: Логируем входные данные (только в dev — logger.debug
  // is gated by isDevelopment check in utils/logger.js)
  logger.debug('[useQueueManager] pickQueueForDoctor:', {
    specialistId,
    doctorId,
    doctorIdFromDoctor: doctor?.id,
    availableQueues: payload.queues.map(q => ({
      specialist_id: q.specialist_id,
      specialty: q.specialty,
      queue_id: q.queue_id
    }))
  });

  // ✅ ИСПРАВЛЕНО: Проверяем только по specialist_id (точное совпадение)
  // Это гарантирует, что для врача с ID=1,2,3 будет найдена именно его очередь
  const foundQueue = payload.queues.find((queue) => {
    // Приоритет 1: Точное совпадение по specialist_id
    if (queue.specialist_id !== undefined && queue.specialist_id !== null) {
      const queueSpecialistId = Number(queue.specialist_id);
      if (queueSpecialistId === doctorId || (doctor?.id && queueSpecialistId === Number(doctor.id))) {
        logger.debug('[useQueueManager] ✅ Найдена очередь по specialist_id:', {
          queueSpecialistId,
          doctorId,
          doctorIdFromDoctor: doctor?.id,
          specialty: queue.specialty
        });
        return true;
      }
    }
    return false;
  });

  if (!foundQueue) {
    logger.warn('[useQueueManager] ❌ Очередь не найдена для врача:', {
      specialistId,
      doctorId,
      doctorIdFromDoctor: doctor?.id,
      availableQueues: payload.queues.map(q => ({
        specialist_id: q.specialist_id,
        specialty: q.specialty
      }))
    });
  }

  return foundQueue || null;
};

const buildStatsFromEntries = (entries: QueueEntry[] = []): QueueStats => ({
  total_entries: entries.length,
  waiting: entries.filter((entry) => entry.status === 'waiting').length,
  completed: entries.filter((entry) => entry.status === 'completed').length,
});

export const useQueueManager = (): UseQueueManagerReturn => {
  const [loading, setLoading] = useState<boolean>(false);
  const [specialists, setSpecialists] = useState<QueueSpecialist[]>([]);
  const [queueData, setQueueData] = useState<QueueData | null>(null);
  const [statistics, setStatistics] = useState<QueueStats | null>(null);
  const [qrData, setQrData] = useState<QrData | null>(null);

  const loadSpecialists = useCallback(async () => {
    setLoading(true);
    try {
      const data = (await fetchAvailableSpecialists()) as QueueSpecialist[];
      setSpecialists(data);
      return data;
    } catch (err: unknown) {
      throw toError(err, 'Не удалось загрузить список доступных специалистов');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadQueueSnapshot = useCallback(
    async ({ specialistId, targetDate, doctor }: LoadQueueSnapshotArgs): Promise<QueueData | null> => {
      if (!specialistId) {
        return null;
      }

      setLoading(true);
      try {
        const payload = (await fetchQueuesToday(targetDate)) as QueuePayload;
        const queue: QueueData =
          pickQueueForDoctor(payload, specialistId, doctor) || {
            id: Number(specialistId),
            entries: [],
            stats: null,
            opened_at: null,
          };

        setQueueData(queue);

        const statsPayload: QueueStats =
          queue.stats ||
          queue.statistics ||
          buildStatsFromEntries(queue.entries);

        setStatistics({
          total_entries:
            statsPayload.total_entries ??
            statsPayload.total ??
            statsPayload.totalEntries ??
            0,
          waiting:
            statsPayload.waiting ??
            statsPayload.waiting_entries ??
            statsPayload.waitingCount ??
            0,
          completed:
            statsPayload.completed ??
            statsPayload.served ??
            statsPayload.served_count ??
            0,
        });

        return queue;
      } catch (err: unknown) {
        throw toError(err, 'Ошибка загрузки очереди');
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const generateDoctorQRCode = useCallback(
    async ({
      specialistId,
      targetDate,
      department,
      specialistName,
      expiresHours = 24,
    }: GenerateDoctorQRCodeArgs) => {
      if (!specialistId || !targetDate) {
        throw new Error('Выберите врача и дату');
      }

      setLoading(true);
      try {
        const payload = (await generateDoctorQrToken({
          specialistId,
          department,
          targetDate,
          expiresHours,
        })) as QrData;
        setQrData({
          ...payload,
          specialist_name: payload.specialist_name || specialistName || 'Врач',
          day: payload.day || targetDate,
          is_clinic_wide: false,
        });
        return payload;
      } catch (err: unknown) {
        throw toError(err, 'Ошибка генерации QR кода');
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const generateClinicQRCode = useCallback(
    async ({ targetDate, expiresHours = 24 }: GenerateClinicQRCodeArgs) => {
      if (!targetDate) {
        throw new Error('Выберите дату');
      }

      setLoading(true);
      try {
        const payload = (await generateClinicQrToken({
          targetDate,
          expiresHours,
        })) as QrData;
        setQrData({
          ...payload,
          specialist_name: 'Все специалисты',
          day: payload.day || targetDate,
          is_clinic_wide: true,
        });
        return payload;
      } catch (err: unknown) {
        throw toError(err, 'Ошибка генерации общего QR кода');
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const openReceptionForDoctor = useCallback(
    async ({ specialistId, targetDate }: ReceptionSlotArgs): Promise<QueueActionResponse> => {
      if (!specialistId) {
        throw new Error('Выберите врача');
      }

      setLoading(true);
      try {
        const result = (await openReceptionSlot({
          day: targetDate,
          specialistId,
        })) as QueueActionResponse;
        return result;
      } catch (err: unknown) {
        throw toError(err, 'Ошибка открытия приема');
      } finally {
        setLoading(false);
      }
    },
    []
  );

  // UX Audit Registrar #7: closeReceptionForDoctor — закрытие приёма.
  const closeReceptionForDoctor = useCallback(
    async ({ specialistId, targetDate }: ReceptionSlotArgs): Promise<QueueActionResponse> => {
      if (!specialistId) {
        throw new Error('Выберите врача');
      }

      setLoading(true);
      try {
        const result = (await closeReceptionSlot({
          day: targetDate,
          specialistId,
        })) as QueueActionResponse;
        return result;
      } catch (err: unknown) {
        throw toError(err, 'Ошибка закрытия приема');
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const callNextPatientInQueue = useCallback(
    async ({ specialistId, targetDate }: ReceptionSlotArgs): Promise<QueueActionResponse> => {
      if (!specialistId) {
        throw new Error('Выберите врача');
      }

      setLoading(true);
      try {
        const result = (await callNextQueuePatient({
          specialistId,
          targetDate,
        })) as QueueActionResponse;
        return result;
      } catch (err: unknown) {
        throw toError(err, 'Ошибка вызова пациента');
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    loadSpecialists().catch(() => undefined);
  }, [loadSpecialists]);

  return {
    loading,
    specialists,
    queueData,
    statistics,
    qrData,
    loadSpecialists,
    loadQueueSnapshot,
    generateDoctorQRCode,
    generateClinicQRCode,
    openReceptionForDoctor,
    closeReceptionForDoctor,
    callNextPatientInQueue,
    setQrData,
  };
};
