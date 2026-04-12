import { useCallback, useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import ModernQueueManager from './queue/ModernQueueManager';
import { fetchAvailableSpecialists } from '../api/queue';
import auth from '../stores/auth.js';
import logger from '../utils/logger';

/**
 * Легкий адаптер, который подключает макос-панели к новому ModernQueueManager.
 * Вся бизнес-логика очереди вынесена на backend и в кастомные хуки.
 */
const QueueIntegration = ({
  specialistId = '',
  onPatientSelect,
  onStartVisit,
}) => {
  const [availableSpecialists, setAvailableSpecialists] = useState([]);
  const [authProfile, setAuthProfile] = useState(auth.getState().profile);

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

  useEffect(() => {
    const unsubscribe = auth.subscribe((state) => {
      setAuthProfile(state.profile || null);
    });

    return unsubscribe;
  }, []);

  const resolvedSpecialist = useMemo(() => {
    if (availableSpecialists.length === 0) {
      return null;
    }

    const canonicalSpecialistId = specialistId || authProfile?.doctor_id || authProfile?.specialist_id;
    if (canonicalSpecialistId) {
      const matchedById = availableSpecialists.find(
        (item) => String(item.id) === String(canonicalSpecialistId)
      );
      if (matchedById) {
        return matchedById;
      }
    }

    return availableSpecialists[0] || null;
  }, [availableSpecialists, authProfile?.doctor_id, authProfile?.specialist_id, specialistId]);

  const queueDoctors = useMemo(() => (
    availableSpecialists.map((item) => ({
      id: item.id,
      specialty: item.specialty,
      department: item.specialty,
      full_name: item.doctor_name || item.specialty_display || null,
      name: item.doctor_name || item.specialty_display || null,
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
  specialistId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
};

export default QueueIntegration;
