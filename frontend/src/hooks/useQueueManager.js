import { useState, useEffect, useCallback } from 'react';
import {
  fetchAvailableSpecialists,
  fetchQueuesToday,
  generateDoctorQrToken,
  generateClinicQrToken,
  openReceptionSlot,
  callNextQueuePatient,
} from '../api/queue';

const toError = (err, fallback) => {
  if (err instanceof Error) {
    return err;
  }
  if (typeof err === 'string') {
    return new Error(err);
  }
  if (err?.detail) {
    return new Error(
      typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail)
    );
  }
  return new Error(fallback);
};

const normalizeSpecialty = (value) =>
  value ? value.toString().toLowerCase().trim() : '';

const pickQueueForDoctor = (payload, specialistId, doctor) => {
  if (!payload?.queues) {
    return null;
  }

  const normalizedSpecialty = normalizeSpecialty(doctor?.specialty);
  const doctorId = Number(specialistId);

  return (
    payload.queues.find((queue) => {
      if (queue.specialty && normalizedSpecialty) {
        if (normalizeSpecialty(queue.specialty) === normalizedSpecialty) {
          return true;
        }
      }
      return Number(queue.specialist_id) === doctorId;
    }) || null
  );
};

const buildStatsFromEntries = (entries = []) => ({
  total_entries: entries.length,
  waiting: entries.filter((entry) => entry.status === 'waiting').length,
  completed: entries.filter((entry) => entry.status === 'completed').length,
});

export const useQueueManager = () => {
  const [loading, setLoading] = useState(false);
  const [specialists, setSpecialists] = useState([]);
  const [queueData, setQueueData] = useState(null);
  const [statistics, setStatistics] = useState(null);
  const [qrData, setQrData] = useState(null);

  const loadSpecialists = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAvailableSpecialists();
      setSpecialists(data);
      return data;
    } catch (err) {
      throw toError(err, 'Не удалось загрузить список доступных специалистов');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadQueueSnapshot = useCallback(
    async ({ specialistId, targetDate, doctor }) => {
      if (!specialistId) {
        return null;
      }

      setLoading(true);
      try {
        const payload = await fetchQueuesToday(targetDate);
        const queue =
          pickQueueForDoctor(payload, specialistId, doctor) || {
            id: Number(specialistId),
            entries: [],
            stats: null,
            opened_at: null,
          };

        setQueueData(queue);

        const statsPayload =
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
      } catch (err) {
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
    }) => {
      if (!specialistId || !targetDate) {
        throw new Error('Выберите врача и дату');
      }

      setLoading(true);
      try {
        const payload = await generateDoctorQrToken({
          specialistId,
          department,
          targetDate,
          expiresHours,
        });
        setQrData({
          ...payload,
          specialist_name: payload.specialist_name || specialistName || 'Врач',
          day: payload.day || targetDate,
          is_clinic_wide: false,
        });
        return payload;
      } catch (err) {
        throw toError(err, 'Ошибка генерации QR кода');
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const generateClinicQRCode = useCallback(
    async ({ targetDate, expiresHours = 24 }) => {
      if (!targetDate) {
        throw new Error('Выберите дату');
      }

      setLoading(true);
      try {
        const payload = await generateClinicQrToken({
          targetDate,
          expiresHours,
        });
        setQrData({
          ...payload,
          specialist_name: 'Все специалисты',
          day: payload.day || targetDate,
          is_clinic_wide: true,
        });
        return payload;
      } catch (err) {
        throw toError(err, 'Ошибка генерации общего QR кода');
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const openReceptionForDoctor = useCallback(
    async ({ specialistId, targetDate }) => {
      if (!specialistId) {
        throw new Error('Выберите врача');
      }

      setLoading(true);
      try {
        return await openReceptionSlot({
          day: targetDate,
          specialistId,
        });
      } catch (err) {
        throw toError(err, 'Ошибка открытия приема');
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const callNextPatientInQueue = useCallback(
    async ({ specialistId, targetDate }) => {
      if (!specialistId) {
        throw new Error('Выберите врача');
      }

      setLoading(true);
      try {
        return await callNextQueuePatient({
          specialistId,
          targetDate,
        });
      } catch (err) {
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
    callNextPatientInQueue,
    setQrData,
  };
};
