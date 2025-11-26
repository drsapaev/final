import { useCallback } from 'react';
import PropTypes from 'prop-types';
import ModernQueueManager from './queue/ModernQueueManager';

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
      selectedDoctor={department || specialist}
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

