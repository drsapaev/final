import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { AlertTriangle, X } from 'lucide-react';
import ModernDialog from './ModernDialog';
import { toast } from 'react-toastify';
// UX Audit Registrar #5: все inline-стили перенесены в CancelDialog.css.
// useTheme удалён — больше не нужен (всё через macos tokens + [data-theme="dark"]).
import './CancelDialog.css';

import logger from '../../utils/logger';
const CancelDialog = ({ isOpen, onClose, appointment, onCancel }) => {
  const [reason, setReason] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState('');

  // Сброс состояния при открытии/закрытии
  useEffect(() => {
    if (isOpen) {
      setReason('');
      setError('');
      setIsProcessing(false);
    }
  }, [isOpen]);

  const validateReason = (value) => {
    if (!value || value.trim().length < 3) {
      return 'Причина отмены должна содержать минимум 3 символа';
    }
    if (value.trim().length > 500) {
      return 'Причина отмены не должна превышать 500 символов';
    }
    return '';
  };

  const handleReasonChange = (e) => {
    const value = e.target.value;
    setReason(value);

    // Валидация в реальном времени
    const validationError = validateReason(value);
    setError(validationError);
  };

  const handleCancel = async () => {
    const validationError = validateReason(reason);
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsProcessing(true);

    try {
      if (onCancel) {
        await onCancel(appointment.id, reason.trim());
      }

      toast.success('Запись успешно отменена');
      onClose();
    } catch (error) {
      logger.error('Cancel error:', error);
      toast.error('Ошибка при отмене записи: ' + error.message);
    } finally {
      setIsProcessing(false);
    }
  };

  if (!appointment) return null;

  const actions = [
    {
      label: 'Отмена',
      variant: 'secondary',
      onClick: onClose,
      disabled: isProcessing,
    },
    {
      label: isProcessing ? 'Отменяем...' : 'Подтвердить отмену',
      variant: 'danger',
      icon: isProcessing ? null : <X size={16} />,
      onClick: handleCancel,
      disabled: isProcessing || !!error || !reason.trim(),
    },
  ];

  return (
    <ModernDialog
      isOpen={isOpen}
      onClose={onClose}
      title="Отменить запись"
      actions={actions}
      dialogClassName="cancel-dialog--styled"
      closeOnBackdrop={!isProcessing}
      closeOnEscape={!isProcessing}
    >
      <div>
        {/* Предупреждение */}
        <div className="cancel-warning">
          <AlertTriangle size={20} className="cancel-warning-icon" />
          <div>
            <h4 className="cancel-warning-title">
              Внимание!
            </h4>
            <p className="cancel-warning-text">
              Отмена записи необратима. Пациент получит уведомление об отмене.
            </p>
          </div>
        </div>

        {/* Информация о записи */}
        <div className="cancel-info-card">
          <h4 className="cancel-info-title">
            Информация о записи
          </h4>

          <div className="cancel-info-rows">
            <div className="cancel-info-row">
              <span className="cancel-info-label">
                Пациент:
              </span>
              <span className="cancel-info-value">
                {appointment.patient_fio}
              </span>
            </div>

            {appointment.services && (
              <div className="cancel-info-row">
                <span className="cancel-info-label">
                  Услуги:
                </span>
                <span className="cancel-info-value--right">
                  {Array.isArray(appointment.services)
                    ? appointment.services.join(', ')
                    : appointment.services}
                </span>
              </div>
            )}

            {appointment.cost && (
              <div className="cancel-info-row">
                <span className="cancel-info-label">
                  Стоимость:
                </span>
                <span className="cancel-info-value">
                  {new Intl.NumberFormat('ru-RU').format(appointment.cost)} сум
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Причина отмены */}
        <div>
          <label htmlFor="cancel-reason" className="cancel-reason-label">
            Причина отмены *
          </label>

          <textarea
            id="cancel-reason"
            aria-label="Причина отмены записи"
            value={reason}
            onChange={handleReasonChange}
            placeholder="Укажите причину отмены записи..."
            rows={4}
            aria-invalid={!!error}
            aria-describedby={error ? 'cancel-reason-error' : undefined}
            className={`cancel-reason-textarea ${error ? 'cancel-reason-textarea--error' : ''}`}
            autoFocus
          />

          {/* Счетчик символов и ошибка */}
          <div className="cancel-reason-meta">
            <div>
              {error && (
                <p id="cancel-reason-error" className="cancel-reason-error">
                  {error}
                </p>
              )}
            </div>
            <span className="cancel-reason-counter">
              {reason.length}/500
            </span>
          </div>

          {/* Подсказка */}
          <p className="cancel-reason-hint">
            Примеры: «Пациент заболел», «Изменились планы», «Врач недоступен»
          </p>
        </div>
      </div>
    </ModernDialog>
  );
};

CancelDialog.propTypes = {
  isOpen: PropTypes.bool,
  onClose: PropTypes.func,
  appointment: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    patient_fio: PropTypes.string,
    services: PropTypes.oneOfType([
      PropTypes.arrayOf(PropTypes.string),
      PropTypes.string,
    ]),
    cost: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  }),
  onCancel: PropTypes.func,
};

export default CancelDialog;
