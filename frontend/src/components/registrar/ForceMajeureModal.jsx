/**
 * ForceMajeureModal - Modal for mass queue operations
 * 
 * Features:
 * - Transfer all waiting patients to tomorrow
 * - Mass cancellation with refund
 * - Safety confirmation (dry run + type CONFIRM)
 */
import { api } from '../../api/client';
import { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  XCircle,
  RefreshCw,
  Calendar,
  DollarSign,
  Users,
  Loader2 } from
'lucide-react';

import logger from '../../utils/logger';
import ModernDialog from '../dialogs/ModernDialog';
import PropTypes from 'prop-types';
import { Input } from '../ui/macos';
// UX Audit: inline-стили перенесены в ForceMajeureModal.css.
// useTheme + tokenManager удалены (auth через axios-interceptor, theme через CSS).
import './ForceMajeureModal.css';
import { useTranslation } from '../../i18n/adapter';

const ForceMajeureModal = ({
  isOpen,
  onClose,
  specialistId,
  specialistName = 'Специалист',
  onSuccess
}) => {
  const [activeTab, setActiveTab] = useState('transfer'); // 'transfer' | 'cancel'
  const [reason, setReason] = useState('');
  const [refundType, setRefundType] = useState('deposit'); // 'deposit' | 'bank_transfer'
  const [confirmText, setConfirmText] = useState('');
  const [loading, setLoading] = useState(false);
  const [dryRunResult, setDryRunResult] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // UX Audit: getAuthToken + tokenManager удалены — auth через axios-interceptor.

  // Load pending entries (dry run)
  const loadPendingEntries = useCallback(async () => {
    if (!specialistId) return;

    try {
      const response = await api.get(`/force-majeure/pending-entries?specialist_id=${specialistId}`);
      const data = response.data;
      setDryRunResult({
        count: data.length,
        entries: data,
        totalAmount: data.reduce((sum, e) => sum + (e.total_amount || 0), 0)
      });
    } catch (err) {
      logger.error('[ForceMajeureModal] Error loading pending entries:', err);
    }
  }, [specialistId]);

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setReason('');
      setConfirmText('');
      setError(null);
      setSuccess(null);
      setDryRunResult(null);
      loadPendingEntries();
    }
  }, [isOpen, specialistId, loadPendingEntries]);

  // Transfer to tomorrow
  const handleTransfer = async () => {
    if (!reason.trim() || reason.length < 5) {
      setError('Укажите причину (минимум 5 символов)');
      return;
    }

    if (confirmText !== 'ПОДТВЕРЖДАЮ') {
      setError('Введите "ПОДТВЕРЖДАЮ" для подтверждения');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await api.post('/force-majeure/transfer', {
          specialist_id: specialistId,
          reason: reason,
          send_notifications: true
      });

      const result = response.data;
      setSuccess(`Перенесено записей: ${result.transferred || 0}`);
      logger.log('[ForceMajeureModal] Transfer successful:', result);
      if (onSuccess) onSuccess('transfer', result);
    } catch (err) {
      logger.error('[ForceMajeureModal] Transfer error:', err);
      setError(err.message || 'Ошибка сети');
    } finally {
      setLoading(false);
    }
  };

  // Cancel with refund
  const handleCancel = async () => {
    if (!reason.trim() || reason.length < 5) {
      setError('Укажите причину (минимум 5 символов)');
      return;
    }

    if (confirmText !== 'ПОДТВЕРЖДАЮ') {
      setError('Введите "ПОДТВЕРЖДАЮ" для подтверждения');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await api.post('/force-majeure/cancel-with-refund', {
        specialist_id: specialistId,
        reason: reason,
        refund_type: refundType,
        send_notifications: true
      });

      const result = response.data;
      setSuccess(`Отменено записей: ${result.cancelled || 0}, возвратов: ${result.refunds_created || 0}`);
      logger.log('[ForceMajeureModal] Cancel successful:', result);
      if (onSuccess) onSuccess('cancel', result);
    } catch (err) {
      logger.error('[ForceMajeureModal] Cancel error:', err);
      setError(err.message || 'Ошибка сети');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const isConfirmValid = confirmText === 'ПОДТВЕРЖДАЮ';
  const isReasonValid = reason.trim().length >= 5;
  const primaryActionLabel = loading ? 'Обработка...' : activeTab === 'transfer' ? 'Перенести' : 'Отменить и вернуть';
  const primaryActionIcon = loading ? <Loader2 size={18} className="animate-spin" /> : activeTab === 'transfer' ? <ArrowRight size={18} /> : <XCircle size={18} />;
  const dialogSurfaceStyle = {
    backgroundColor: 'var(--mac-bg-primary)'
  };

  const header = (
    <div className="fmm-header">
      <div className="fmm-header-info">
        <div className="fmm-header-icon">
          <AlertTriangle size={20} />
        </div>
        <div className="fmm-header-text">
          <h2 className="fmm-header-title">
            Форс-мажор
          </h2>
          <p className="fmm-header-subtitle">
            {specialistName}
          </p>
        </div>
      </div>
      <button
        onClick={onClose}
        className="fmm-close-btn"
        aria-label="Закрыть диалог">
        <XCircle size={18} />
      </button>
    </div>
  );

  const actions = [
    {
      label: 'Отмена',
      variant: 'secondary',
      onClick: onClose,
      disabled: loading
    },
    {
      label: primaryActionLabel,
      variant: activeTab === 'transfer' ? 'primary' : 'danger',
      icon: primaryActionIcon,
      onClick: activeTab === 'transfer' ? handleTransfer : handleCancel,
      disabled: loading || !isConfirmValid || !isReasonValid || Boolean(success)
    }
  ];

  return (
    <ModernDialog
      isOpen={isOpen}
      onClose={onClose}
      title="Форс-мажор"
      customHeader={header}
      actions={actions}
      maxWidth="40rem"
      maxHeight="calc(100dvh - 2rem)"
      closeOnBackdrop={!loading}
      closeOnEscape={!loading}
      showCloseButton={false}
      dialogStyle={dialogSurfaceStyle}>
      <div className="fmm-grid-gap">
        <div className="fmm-tab-container">
          <button
            type="button"
            onClick={() => setActiveTab('transfer')}
            className={`fmm-tab-btn fmm-tab-btn--transfer ${activeTab === 'transfer' ? 'fmm-tab-btn--active' : ''}`}>
            <Calendar size={18} />
            Перенести на завтра
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('cancel')}
            className={`fmm-tab-btn fmm-tab-btn--cancel ${activeTab === 'cancel' ? 'fmm-tab-btn--active' : ''}`}>
            <DollarSign size={18} />
            Отменить с возвратом
          </button>
        </div>

        {dryRunResult &&
        <div className="fmm-dry-run-card">
          <Users size={32} className="fmm-dry-run-icon" />
          <div className="fmm-dry-run-info">
            <p className="fmm-dry-run-count">
              {dryRunResult.count} записей
            </p>
            <p className="fmm-dry-run-subtitle">
              будут {activeTab === 'transfer' ? 'перенесены' : 'отменены'}
              {dryRunResult.totalAmount > 0 && ` • ${dryRunResult.totalAmount.toLocaleString()} сум`}
            </p>
          </div>
          <button
            type="button"
            onClick={loadPendingEntries}
            className="fmm-refresh-btn"
            aria-label="Обновить список">
            <RefreshCw size={18} />
          </button>
        </div>
        }

        <div>
          <label className="fmm-field-label">
            Причина *
          </label>
          <textarea
            aria-label="Force majeure reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Опишите причину форс-мажора..."
            className={`fmm-textarea ${error ? 'fmm-textarea--error' : ''}`} />
          {!isReasonValid && reason.length > 0 &&
          <p className="fmm-error-text">
            Минимум 5 символов
          </p>
          }
        </div>

        {activeTab === 'cancel' &&
        <div className="fmm-grid-gap-sm">
          <label className="fmm-field-label fmm-field-label--mb1">
            Тип возврата
          </label>
          <div className="fmm-refund-grid">
            <label className={`fmm-refund-option ${refundType === 'deposit' ? 'fmm-refund-option--selected' : ''}`}>
              <input
                type="radio"
                name="refundType"
                value="deposit"
                aria-label="Refund to deposit"
                checked={refundType === 'deposit'}
                onChange={(e) => setRefundType(e.target.value)}
                style={{ display: 'none' }} />
              <div className={`fmm-refund-radio ${refundType === 'deposit' ? 'fmm-refund-radio--selected' : ''}`}>
                {refundType === 'deposit' && <div className="fmm-refund-radio-dot" />}
              </div>
              <div>
                <div className="fmm-refund-label">На депозит</div>
                <div className="fmm-refund-label" style="font-size: var(--mac-font-size-xs); color: var(--mac-text-secondary);">Мгновенно на баланс</div>
              </div>
            </label>
            <label className={`fmm-refund-option ${refundType === 'bank_transfer' ? 'fmm-refund-option--selected' : ''}`}>
              <input
                type="radio"
                name="refundType"
                value="bank_transfer"
                aria-label="Refund to bank card"
                checked={refundType === 'bank_transfer'}
                onChange={(e) => setRefundType(e.target.value)}
                style={{ display: 'none' }} />
              <div className={`fmm-refund-radio ${refundType === 'bank_transfer' ? 'fmm-refund-radio--selected' : ''}`}>
                {refundType === 'bank_transfer' && <div className="fmm-refund-radio-dot" />}
              </div>
              <div>
                <div className="fmm-refund-label">На карту</div>
                <div className="fmm-refund-label" style="font-size: var(--mac-font-size-xs); color: var(--mac-text-secondary);">Заявка на возврат</div>
              </div>
            </label>
          </div>
        </div>
        }

        <div className="fmm-error-box" style="border-radius: 14px;">
          <p className="fmm-warning-text">
            ⚠️ Это действие нельзя отменить!
          </p>
          <label className="fmm-field-label" style="font-size: var(--mac-font-size-sm); color: var(--mac-error);">
            Введите <strong>ПОДТВЕРЖДАЮ</strong> для продолжения:
          </label>
          <Input
            type="text"
            aria-label="Type confirmation phrase"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value.toUpperCase())}
            placeholder="ПОДТВЕРЖДАЮ"
            className={`fmm-confirm-input ${isConfirmValid ? 'fmm-confirm-input--valid' : ''}`} />
        </div>

        {error &&
        <div className="fmm-error-box">
          {error}
        </div>
        }

        {success &&
        <div className="fmm-success-box">
          ✅ {success}
        </div>
        }
      </div>
    </ModernDialog>);

};


ForceMajeureModal.propTypes = {
  ...(ForceMajeureModal.propTypes || {}),
  isOpen: PropTypes.any,
  onClose: PropTypes.any,
  onSuccess: PropTypes.any,
  specialistId: PropTypes.any,
  specialistName: PropTypes.any,
};

export default ForceMajeureModal;
