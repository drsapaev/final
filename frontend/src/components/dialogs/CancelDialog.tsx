import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import ModernDialog from './ModernDialog';
import React from 'react';
import { toast } from 'react-toastify';
import './CancelDialog.css';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

interface CancelDialogAppointment {
  id?: string | number;
  patient_fio?: string;
  patient_name?: string;
  services?: string[] | string;
  cost?: number | string;
  appointment_date?: string;
  appointment_time?: string;
  [key: string]: unknown;
}

interface CancelDialogProps {
  isOpen: boolean;
  onClose: () => void;
  appointment: CancelDialogAppointment | null;
  onCancel: (appointmentId: unknown, reason: string) => Promise<void>;
}

const CancelDialog = ({ isOpen, onClose, appointment, onCancel }: CancelDialogProps) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
      return t('misc.cd_prichina_otmeny_dolzhna_sode');
    }
    if (value.trim().length > 500) {
      return t('misc.cd_prichina_otmeny_ne_dolzhna_p');
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

      toast.success(t('misc.cd_zapis_uspeshno_otmenena'));
      onClose();
    } catch (error) {
      logger.error('Cancel error:', error);
      toast.error(t('misc.cd_oshibka_pri_otmene_zapisi') + error.message);
    } finally {
      setIsProcessing(false);
    }
  };

  if (!appointment) return null;

  const actions = [
    {
      label: t('misc.cd_otmena'),
      variant: 'secondary',
      onClick: onClose,
      disabled: isProcessing,
    },
    {
      label: isProcessing ? t('misc.cd_otmenyaem') : t('misc.cd_podtverdit_otmenu'),
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
      title={t('misc.cd_otmenit_zapis')}
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
                  {new Intl.NumberFormat('ru-RU').format(Number(appointment.cost ?? 0))} сум
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
            aria-label={t('misc.cd_prichina_otmeny_zapisi')}
            value={reason}
            onChange={handleReasonChange}
            placeholder={t('misc.cd_ukazhite_prichinu_otmeny_zap')}
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


export default CancelDialog;
