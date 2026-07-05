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
import { tokenManager } from '../../utils/tokenManager';
import ModernDialog from '../dialogs/ModernDialog';
import { useTheme } from '../../contexts/ThemeContext';
import PropTypes from 'prop-types';
import { Input } from '../ui/macos';

const ForceMajeureModal = ({
  isOpen,
  onClose,
  specialistId,
  specialistName = 'Специалист',
  onSuccess
}) => {
  const { theme, getColor } = useTheme();
  const [activeTab, setActiveTab] = useState('transfer'); // 'transfer' | 'cancel'
  const [reason, setReason] = useState('');
  const [refundType, setRefundType] = useState('deposit'); // 'deposit' | 'bank_transfer'
  const [confirmText, setConfirmText] = useState('');
  const [loading, setLoading] = useState(false);
  const [dryRunResult, setDryRunResult] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const getAuthToken = () => {
    return tokenManager.getAccessToken();
  };

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
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      justifyContent: 'space-between',
      gap: 'var(--mac-spacing-4)',
      width: '100%'
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--mac-spacing-3)', minWidth: 0 }}>
        <div style={{
          width: '40px',
          height: '40px',
          borderRadius: '14px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          background: theme === 'dark'
            ? 'linear-gradient(135deg, rgba(245, 158, 11, 0.28), rgba(217, 119, 6, 0.2))'
            : 'linear-gradient(135deg, rgba(251, 191, 36, 0.25), rgba(245, 158, 11, 0.16))',
          border: `1px solid ${theme === 'dark' ? 'rgba(245, 158, 11, 0.25)' : 'rgba(245, 158, 11, 0.18)'}`,
          color: 'var(--mac-warning-hover, var(--mac-warning))',
          boxShadow: '0 10px 24px rgba(245, 158, 11, 0.12)'
        }}>
          <AlertTriangle size={20} />
        </div>
        <div style={{ minWidth: 0 }}>
          <h2 style={{
            margin: 0,
            fontSize: 'var(--mac-font-size-xl)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: getColor('textPrimary'),
            lineHeight: 1.2
          }}>
            Форс-мажор
          </h2>
          <p style={{
            margin: '4px 0 0',
            fontSize: 'var(--mac-font-size-sm)',
            color: getColor('textSecondary'),
            lineHeight: 1.4
          }}>
            {specialistName}
          </p>
        </div>
      </div>
      <button
        onClick={onClose}
        style={{
          width: '32px',
          height: '32px',
          borderRadius: '999px',
          border: `1px solid ${theme === 'dark' ? 'rgba(255,255,255,0.12)' : 'var(--mac-border)'}`,
          background: theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'var(--mac-bg-secondary)',
          color: getColor('textSecondary'),
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: 'var(--mac-shadow-sm)',
          cursor: 'pointer',
          flexShrink: 0
        }}
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
      <div style={{ display: 'grid', gap: 'var(--mac-spacing-4)' }}>
        <div style={{
          display: 'flex',
          gap: 'var(--mac-spacing-2)',
          padding: 'var(--mac-spacing-2)',
          borderRadius: '14px',
          background: theme === 'dark' ? 'color-mix(in srgb, white, transparent 96%)' : 'rgba(148, 163, 184, 0.12)',
          border: `1px solid ${theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(148, 163, 184, 0.16)'}`
        }}>
          <button
            type="button"
            onClick={() => setActiveTab('transfer')}
            style={{
              flex: 1,
              padding: '10px 12px',
              border: 'none',
              borderRadius: 'var(--mac-radius-lg)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 'var(--mac-spacing-2)',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: activeTab === 'transfer' ? 'var(--mac-accent-blue-hover)' : getColor('textSecondary'),
              background: activeTab === 'transfer'
                ? (theme === 'dark' ? 'rgba(59, 130, 246, 0.16)' : 'white')
                : 'transparent',
              boxShadow: activeTab === 'transfer' && theme !== 'dark' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none'
            }}>
            <Calendar size={18} />
            Перенести на завтра
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('cancel')}
            style={{
              flex: 1,
              padding: '10px 12px',
              border: 'none',
              borderRadius: 'var(--mac-radius-lg)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 'var(--mac-spacing-2)',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: activeTab === 'cancel' ? 'var(--mac-error)' : getColor('textSecondary'),
              background: activeTab === 'cancel'
                ? (theme === 'dark' ? 'rgba(239, 68, 68, 0.14)' : 'white')
                : 'transparent',
              boxShadow: activeTab === 'cancel' && theme !== 'dark' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none'
            }}>
            <DollarSign size={18} />
            Отменить с возвратом
          </button>
        </div>

        {dryRunResult &&
        <div style={{
          background: theme === 'dark' ? 'color-mix(in srgb, white, transparent 96%)' : 'var(--mac-bg-secondary)',
          border: `1px solid ${theme === 'dark' ? 'color-mix(in srgb, white, transparent 92%)' : 'var(--mac-border)'}`,
          borderRadius: '14px',
          padding: 'var(--mac-spacing-4)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-4)'
        }}>
          <Users size={32} color={theme === 'dark' ? 'var(--mac-text-tertiary)' : 'var(--mac-text-secondary)'} />
          <div style={{ minWidth: 0 }}>
            <p style={{ margin: 0, fontSize: 'var(--mac-font-size-3xl)', fontWeight: 'var(--mac-font-weight-bold)', color: getColor('textPrimary') }}>
              {dryRunResult.count} записей
            </p>
            <p style={{ margin: 0, fontSize: 'var(--mac-font-size-sm)', color: getColor('textSecondary') }}>
              будут {activeTab === 'transfer' ? 'перенесены' : 'отменены'}
              {dryRunResult.totalAmount > 0 && ` • ${dryRunResult.totalAmount.toLocaleString()} сум`}
            </p>
          </div>
          <button
            type="button"
            onClick={loadPendingEntries}
            style={{
              marginLeft: 'auto',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 'var(--mac-spacing-2)',
              color: getColor('textSecondary')
            }}
            aria-label="Обновить список">
            <RefreshCw size={18} />
          </button>
        </div>
        }

        <div>
          <label style={{
            display: 'block',
            marginBottom: 'var(--mac-spacing-2)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: getColor('textPrimary'),
            fontSize: 'var(--mac-font-size-base)'
          }}>
            Причина *
          </label>
          <textarea
            aria-label="Force majeure reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Опишите причину форс-мажора..."
            style={{
              width: '100%',
              padding: '12px 14px',
              border: `1px solid ${error ? 'var(--mac-error)' : theme === 'dark' ? 'color-mix(in srgb, white, transparent 90%)' : 'var(--mac-border)'}`,
              borderRadius: 'var(--mac-radius-lg)',
              fontSize: 'var(--mac-font-size-base)',
              minHeight: '96px',
              resize: 'vertical',
              color: getColor('textPrimary'),
              backgroundColor: theme === 'dark' ? 'color-mix(in srgb, white, transparent 96%)' : 'white',
              fontFamily: 'inherit',
              outline: 'none'
            }} />
          {!isReasonValid && reason.length > 0 &&
          <p style={{ margin: '6px 0 0', fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-error)' }}>
            Минимум 5 символов
          </p>
          }
        </div>

        {activeTab === 'cancel' &&
        <div style={{ display: 'grid', gap: '10px' }}>
          <label style={{
            display: 'block',
            marginBottom: 'var(--mac-spacing-1)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: getColor('textPrimary'),
            fontSize: 'var(--mac-font-size-base)'
          }}>
            Тип возврата
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 'var(--mac-spacing-3)' }}>
            <label style={{
              padding: 'var(--mac-spacing-3)',
              border: refundType === 'deposit' ? '1px solid var(--mac-accent-blue)' : `1px solid ${theme === 'dark' ? 'color-mix(in srgb, white, transparent 92%)' : 'var(--mac-border)'}`,
              borderRadius: 'var(--mac-radius-lg)',
              cursor: 'pointer',
              background: refundType === 'deposit' ? (theme === 'dark' ? 'rgba(59,130,246,0.14)' : 'var(--mac-accent-bg)') : (theme === 'dark' ? 'color-mix(in srgb, white, transparent 96%)' : 'white')
            }}>
              <input
                type="radio"
                name="refundType"
                value="deposit"
                aria-label="Refund to deposit"
                checked={refundType === 'deposit'}
                onChange={(e) => setRefundType(e.target.value)}
                style={{ display: 'none' }} />
              <div style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: getColor('textPrimary'), fontSize: 'var(--mac-font-size-base)' }}>На депозит</div>
              <div style={{ fontSize: 'var(--mac-font-size-xs)', color: getColor('textSecondary'), marginTop: 'var(--mac-spacing-1)' }}>Мгновенно на баланс</div>
            </label>
            <label style={{
              padding: 'var(--mac-spacing-3)',
              border: refundType === 'bank_transfer' ? '1px solid var(--mac-accent-blue)' : `1px solid ${theme === 'dark' ? 'color-mix(in srgb, white, transparent 92%)' : 'var(--mac-border)'}`,
              borderRadius: 'var(--mac-radius-lg)',
              cursor: 'pointer',
              background: refundType === 'bank_transfer' ? (theme === 'dark' ? 'rgba(59,130,246,0.14)' : 'var(--mac-accent-bg)') : (theme === 'dark' ? 'color-mix(in srgb, white, transparent 96%)' : 'white')
            }}>
              <input
                type="radio"
                name="refundType"
                value="bank_transfer"
                aria-label="Refund to bank card"
                checked={refundType === 'bank_transfer'}
                onChange={(e) => setRefundType(e.target.value)}
                style={{ display: 'none' }} />
              <div style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: getColor('textPrimary'), fontSize: 'var(--mac-font-size-base)' }}>На карту</div>
              <div style={{ fontSize: 'var(--mac-font-size-xs)', color: getColor('textSecondary'), marginTop: 'var(--mac-spacing-1)' }}>Заявка на возврат</div>
            </label>
          </div>
        </div>
        }

        <div style={{
          background: theme === 'dark' ? 'rgba(239, 68, 68, 0.10)' : 'var(--mac-error-bg)',
          border: `1px solid ${theme === 'dark' ? 'rgba(239, 68, 68, 0.28)' : 'var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))'}`,
          borderRadius: '14px',
          padding: 'var(--mac-spacing-4)'
        }}>
          <p style={{ margin: '0 0 10px', fontSize: 'var(--mac-font-size-base)', color: '#991b1b', fontWeight: 'var(--mac-font-weight-semibold)' }}>
            ⚠️ Это действие нельзя отменить!
          </p>
          <label style={{ display: 'block', marginBottom: 'var(--mac-spacing-2)', fontSize: 'var(--mac-font-size-sm)', color: theme === 'dark' ? 'var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))' : '#7f1d1d' }}>
            Введите <strong>ПОДТВЕРЖДАЮ</strong> для продолжения:
          </label>
          <Input
            type="text"
            aria-label="Type confirmation phrase"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value.toUpperCase())}
            placeholder="ПОДТВЕРЖДАЮ"
            style={{
              width: '100%',
              padding: '10px 12px',
              border: `1px solid ${isConfirmValid ? 'var(--mac-success)' : theme === 'dark' ? 'color-mix(in srgb, white, transparent 90%)' : 'var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))'}`,
              borderRadius: 'var(--mac-radius-lg)',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              textAlign: 'center',
              letterSpacing: '2px',
              color: getColor('textPrimary'),
              backgroundColor: theme === 'dark' ? 'color-mix(in srgb, white, transparent 96%)' : 'white',
              outline: 'none'
            }} />
        </div>

        {error &&
        <div style={{
          background: theme === 'dark' ? 'rgba(239, 68, 68, 0.10)' : 'var(--mac-error-bg)',
          color: 'var(--mac-error)',
          padding: '12px 14px',
          borderRadius: 'var(--mac-radius-lg)',
          fontSize: 'var(--mac-font-size-base)',
          border: `1px solid ${theme === 'dark' ? 'rgba(239, 68, 68, 0.28)' : 'var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))'}`
        }}>
          {error}
        </div>
        }

        {success &&
        <div style={{
          background: theme === 'dark' ? 'rgba(16, 185, 129, 0.10)' : '#f0fdf4',
          color: 'var(--mac-success)',
          padding: '12px 14px',
          borderRadius: 'var(--mac-radius-lg)',
          fontSize: 'var(--mac-font-size-base)',
          border: `1px solid ${theme === 'dark' ? 'rgba(16, 185, 129, 0.24)' : '#bbf7d0'}`
        }}>
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
