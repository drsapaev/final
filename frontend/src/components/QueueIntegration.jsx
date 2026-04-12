import { useCallback, useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import ModernQueueManager from './queue/ModernQueueManager';
import { fetchAvailableSpecialists } from '../api/queue';
import logger from '../utils/logger';

const normalizeSpecialty = (value) =>
  String(value || '').toLowerCase().trim();

const getSpecialtyCandidates = (value) => {
  const normalized = normalizeSpecialty(value);
  if (!normalized) {
    return [];
  }

  const aliases = {
    cardio: ['cardiology'],
    cardiology: ['cardio'],
    derma: ['dermatology'],
    dermatology: ['derma'],
    dentist: ['dentistry', 'stomatology'],
    dentistry: ['dentist', 'stomatology'],
    stomatology: ['dentist', 'dentistry'],
    lab: ['laboratory'],
    laboratory: ['lab'],
    кардиолог: ['cardiology', 'cardio'],
    дерматолог: ['dermatology', 'derma'],
    'дерматолог-косметолог': ['dermatology', 'derma'],
    стоматолог: ['dentist', 'dentistry', 'stomatology'],
    лаборатория: ['laboratory', 'lab'],
  };

  return Array.from(new Set([normalized, ...(aliases[normalized] || [])]));
};

/**
 * Легкий адаптер, который подключает макос-панели к новому ModernQueueManager.
 * Вся бизнес-логика очереди вынесена на backend и в кастомные хуки.
 */
const QueueIntegration = ({
  specialist = 'Дерматолог',
  department,
  onPatientSelect,
  onStartVisit,
}) => {
  const [availableSpecialists, setAvailableSpecialists] = useState([]);

  useEffect(() => {
    let cancelled = false;

    const loadSpecialists = async () => {
      try {
        const specialists = await fetchAvailableSpecialists();
        if (!cancelled) {
          setAvailableSpecialists(Array.isArray(specialists) ? specialists : []);
        }
      } catch (error) {
        logger.error('[QueueIntegration] Failed to load specialists:', error);
        if (!cancelled) {
          setAvailableSpecialists([]);
        }
      }
    };

    loadSpecialists();

    return () => {
      cancelled = true;
    };
  }, []);

  const resolvedSpecialist = useMemo(() => {
    const candidates = getSpecialtyCandidates(department || specialist);
    if (candidates.length === 0 || availableSpecialists.length === 0) {
      return null;
    }

    return availableSpecialists.find((item) => {
      const itemCandidates = [
        ...getSpecialtyCandidates(item.specialty),
        ...getSpecialtyCandidates(item.specialty_display),
        ...getSpecialtyCandidates(item.doctor_name),
      ];

      return itemCandidates.some((candidate) => candidates.includes(candidate));
    }) || null;
  }, [availableSpecialists, department, specialist]);

  const queueDoctors = useMemo(() => (
    availableSpecialists.map((item) => ({
      id: item.id,
      specialty: item.specialty,
      department: item.specialty,
      full_name: item.doctor_name || item.specialty_display || item.specialty,
      name: item.doctor_name || item.specialty_display || item.specialty,
      cabinet: item.cabinet,
      active: true,
      user: {
        full_name: item.doctor_name,
        is_active: true,
      },
    }))
  ), [availableSpecialists]);

  const handleQueueUpdate = useCallback(() => {
    if (onPatientSelect) {
      onPatientSelect(null);
    }
    if (onStartVisit) {
      onStartVisit(null);
    }
  }, [onPatientSelect, onStartVisit]);

  return (
    <ModernQueueManager
      selectedDoctor={resolvedSpecialist?.id ? String(resolvedSpecialist.id) : ''}
      doctors={queueDoctors}
      onQueueUpdate={handleQueueUpdate}
    />
  );
};

QueueIntegration.propTypes = {
  specialist: PropTypes.string,
  department: PropTypes.string,
  onPatientSelect: PropTypes.func,
  onStartVisit: PropTypes.func,
};

export default QueueIntegration;
