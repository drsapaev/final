import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { AlertTriangle, X } from 'lucide-react';
import ModernDialog from './ModernDialog';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';

import logger from '../../utils/logger';
const CancelDialog = ({ isOpen, onClose, appointment, onCancel }) => {
  const { theme, getColor } = useTheme();
  const surfaceStyle = {
    backgroundColor: 'var(--mac-bg-secondary)',
    border: `1px solid ${theme === 'dark' ? 'color-mix(in srgb, white, transparent 92%)' : 'var(--mac-border)'}`,
    borderRadius: '14px',
  };
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
      dialogStyle={{
        backgroundColor: 'var(--mac-bg-primary)',
      }}
      closeOnBackdrop={!isProcessing}
      closeOnEscape={!isProcessing}
    >
      <div>
        {/* Предупреждение */}
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 'var(--mac-spacing-3)',
            padding: 'var(--mac-spacing-4)',
            backgroundColor:
              theme === 'dark' ? 'rgba(245, 158, 11, 0.10)' : 'var(--mac-error-bg)',
            border: `1px solid ${theme === 'dark' ? 'rgba(245, 158, 11, 0.24)' : 'var(--mac-error-border, color-mix(in srgb, var(--mac-warning), transparent 50%))'}`,
            borderRadius: '14px',
            marginBottom: 'var(--mac-spacing-6)',
          }}
        >
          <AlertTriangle
            size={20}
            style={{
              color: theme === 'dark' ? 'var(--mac-warning)' : 'var(--mac-warning-hover, var(--mac-warning))',
              flexShrink: 0,
              marginTop: '2px',
            }}
          />
          <div>
            <h4
              style={{
                color: theme === 'dark' ? 'var(--mac-warning)' : '#92400e',
                fontSize: 'var(--mac-font-size-base)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                margin: '0 0 4px 0',
              }}
            >
              Внимание!
            </h4>
            <p
              style={{
                color: theme === 'dark' ? '#fcd34d' : '#a16207',
                fontSize: 'var(--mac-font-size-sm)',
                margin: 0,
                lineHeight: '1.4',
              }}
            >
              Отмена записи необратима. Пациент получит уведомление об отмене.
            </p>
          </div>
        </div>

        {/* Информация о записи */}
        <div
          style={{
            marginBottom: 'var(--mac-spacing-6)',
            padding: 'var(--mac-spacing-4)',
            ...surfaceStyle,
          }}
        >
          <h4
            style={{
              color: getColor('textPrimary'),
              margin: '0 0 12px 0',
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)',
            }}
          >
            Информация о записи
          </h4>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span
                style={{
                  color: getColor('textSecondary'),
                  fontSize: 'var(--mac-font-size-base)',
                }}
              >
                Пациент:
              </span>
              <span
                style={{
                  color: getColor('textPrimary'),
                  fontSize: 'var(--mac-font-size-base)',
                  fontWeight: 'var(--mac-font-weight-medium)',
                }}
              >
                {appointment.patient_fio}
              </span>
            </div>

            {appointment.services && (
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span
                  style={{
                    color: getColor('textSecondary'),
                    fontSize: 'var(--mac-font-size-base)',
                  }}
                >
                  Услуги:
                </span>
                <span
                  style={{
                    color: getColor('textPrimary'),
                    fontSize: 'var(--mac-font-size-base)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    textAlign: 'right',
                    maxWidth: '60%',
                  }}
                >
                  {Array.isArray(appointment.services)
                    ? appointment.services.join(', ')
                    : appointment.services}
                </span>
              </div>
            )}

            {appointment.cost && (
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span
                  style={{
                    color: getColor('textSecondary'),
                    fontSize: 'var(--mac-font-size-base)',
                  }}
                >
                  Стоимость:
                </span>
                <span
                  style={{
                    color: getColor('textPrimary'),
                    fontSize: 'var(--mac-font-size-base)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                  }}
                >
                  {appointment.cost.toLocaleString()} ₽
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Причина отмены */}
        <div>
          <label
            htmlFor="cancel-reason"
            style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-medium)',
              marginBottom: 'var(--mac-spacing-2)',
              color: getColor('textPrimary'),
            }}
          >
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
            style={{
              width: '100%',
              padding: '12px 14px',
              border: `1px solid ${
                error
                  ? 'var(--mac-error)'
                  : theme === 'dark'
                    ? 'color-mix(in srgb, white, transparent 90%)'
                    : 'var(--mac-border)'
              }`,
              borderRadius: 'var(--mac-radius-lg)',
              backgroundColor:
                theme === 'dark' ? 'color-mix(in srgb, white, transparent 96%)' : 'white',
              color: getColor('textPrimary'),
              fontSize: 'var(--mac-font-size-base)',
              resize: 'vertical',
              minHeight: '100px',
              transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
              fontFamily: 'inherit',
              outline: 'none',
            }}
            onFocus={(e) => {
              if (!error) {
                e.target.style.borderColor = 'var(--mac-accent-blue)';
                e.target.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.12)';
              }
            }}
            onBlur={(e) => {
              e.target.style.borderColor = error
                ? 'var(--mac-error)'
                : theme === 'dark'
                  ? 'color-mix(in srgb, white, transparent 90%)'
                  : 'var(--mac-border)';
              e.target.style.boxShadow = 'none';
            }}
            autoFocus
          />

          {/* Счетчик символов и ошибка */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginTop: 'var(--mac-spacing-2)',
            }}
          >
            <div>
              {error && (
                <p
                  id="cancel-reason-error"
                  style={{
                    color: 'var(--mac-error)',
                    fontSize: 'var(--mac-font-size-xs)',
                    margin: 0,
                  }}
                >
                  {error}
                </p>
              )}
            </div>
            <span
              style={{
                color: getColor('textSecondary'),
                fontSize: 'var(--mac-font-size-xs)',
              }}
            >
              {reason.length}/500
            </span>
          </div>

          {/* Подсказка */}
          <p
            style={{
              color: getColor('textSecondary'),
              fontSize: 'var(--mac-font-size-xs)',
              margin: '8px 0 0 0',
              fontStyle: 'italic',
            }}
          >
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
