
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
import { useTranslation } from '../../i18n/useTranslation';

const ForceMajeureModal = ({
  isOpen,
  onClose,
  specialistId,
  specialistName,
  onSuccess
}) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
      setError(t('misc.fm_reason_required'));
      return;
    }

    if (confirmText !== 'ПОДТВЕРЖДАЮ') {
      setError(t('misc.fm_confirm_required'));
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
      setSuccess(t('misc.fm_transfer_success', { count: result.transferred || 0 }));
      logger.log('[ForceMajeureModal] Transfer successful:', result);
      if (onSuccess) onSuccess('transfer', result);
    } catch (err) {
      logger.error('[ForceMajeureModal] Transfer error:', err);
      setError(err.message || t('misc.fm_network_error'));
    } finally {
      setLoading(false);
    }
  };

  // Cancel with refund
  const handleCancel = async () => {
    if (!reason.trim() || reason.length < 5) {
      setError(t('misc.fm_reason_required'));
      return;
    }

    if (confirmText !== 'ПОДТВЕРЖДАЮ') {
      setError(t('misc.fm_confirm_required'));
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
      setSuccess(t('misc.fm_cancel_success', { cancelled: result.cancelled || 0, refunds: result.refunds_created || 0 }));
      logger.log('[ForceMajeureModal] Cancel successful:', result);
      if (onSuccess) onSuccess('cancel', result);
    } catch (err) {
      logger.error('[ForceMajeureModal] Cancel error:', err);
      setError(err.message || t('misc.fm_network_error'));
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const isConfirmValid = confirmText === 'ПОДТВЕРЖДАЮ';
  const isReasonValid = reason.trim().length >= 5;
  const primaryActionLabel = loading ? t('misc.fm_processing') : activeTab === 'transfer' ? t('misc.fm_transfer_button') : t('misc.fm_cancel_button');
  const primaryActionIcon = loading ? <Loader2 size={18 as unknown as "small" | "default" | "large" | "xlarge"} className="animate-spin" /> : activeTab === 'transfer' ? <ArrowRight size={18 as unknown as "small" | "default" | "large" | "xlarge"} /> : <XCircle size={18 as unknown as "small" | "default" | "large" | "xlarge"} />;
  const dialogSurfaceStyle = {
    backgroundColor: 'var(--mac-bg-primary)'
  };

  const header = (
    <div className="fmm-header">
      <div className="fmm-header-info">
        <div className="fmm-header-icon">
          <AlertTriangle size={20 as unknown as "small" | "default" | "large" | "xlarge"} />
        </div>
        <div className="fmm-header-text">
          <h2 className="fmm-header-title">
            {t('misc.fm_title')}
          </h2>
          <p className="fmm-header-subtitle">
            {specialistName || t('misc.fm_default_specialist')}
          </p>
        </div>
      </div>
      <button
        onClick={onClose}
        className="fmm-close-btn"
        aria-label={t('misc.fm_aria_close')}>
        <XCircle size={18 as unknown as "small" | "default" | "large" | "xlarge"} />
      </button>
    </div>
  );

  const actions = [
    {
      label: t('misc.fm_action_cancel'),
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
      title={t('misc.fm_title')}
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
            <Calendar size={18 as unknown as "small" | "default" | "large" | "xlarge"} />
            {t('misc.fm_tab_transfer')}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('cancel')}
            className={`fmm-tab-btn fmm-tab-btn--cancel ${activeTab === 'cancel' ? 'fmm-tab-btn--active' : ''}`}>
            <DollarSign size={18 as unknown as "small" | "default" | "large" | "xlarge"} />
            {t('misc.fm_tab_cancel')}
          </button>
        </div>

        {dryRunResult &&
        <div className="fmm-dry-run-card">
          <Users size={32 as unknown as "small" | "default" | "large" | "xlarge"} className="fmm-dry-run-icon" />
          <div className="fmm-dry-run-info">
            <p className="fmm-dry-run-count">
              {t('misc.fm_entries_count', { count: dryRunResult.count })}
            </p>
            <p className="fmm-dry-run-subtitle">
              {t('misc.fm_entries_action', { action: activeTab === 'transfer' ? t('misc.fm_transferred_word') : t('misc.fm_cancelled_word') })}
              {dryRunResult.totalAmount > 0 && t('misc.fm_entries_amount', { amount: dryRunResult.totalAmount.toLocaleString() })}
            </p>
          </div>
          <button
            type="button"
            onClick={loadPendingEntries}
            className="fmm-refresh-btn"
            aria-label={t('misc.fm_aria_refresh')}>
            <RefreshCw size={18 as unknown as "small" | "default" | "large" | "xlarge"} />
          </button>
        </div>
        }

        <div>
          <label className="fmm-field-label">
            {t('misc.fm_reason_label')}
          </label>
          <textarea
            aria-label="Force majeure reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={t('misc.fm_reason_placeholder')}
            className={`fmm-textarea ${error ? 'fmm-textarea--error' : ''}`} />
          {!isReasonValid && reason.length > 0 &&
          <p className="fmm-error-text">
            {t('misc.fm_reason_min')}
          </p>
          }
        </div>

        {activeTab === 'cancel' &&
        <div className="fmm-grid-gap-sm">
          <label className="fmm-field-label fmm-field-label--mb1">
            {t('misc.fm_refund_type_label')}
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
                <div className="fmm-refund-label">{t('misc.fm_refund_deposit')}</div>
                <div className="fmm-refund-label" style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>{t('misc.fm_refund_deposit_desc')}</div>
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
                <div className="fmm-refund-label">{t('misc.fm_refund_card')}</div>
                <div className="fmm-refund-label" style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>{t('misc.fm_refund_card_desc')}</div>
              </div>
            </label>
          </div>
        </div>
        }

        <div className="fmm-error-box" style={{ borderRadius: "14px" }}>
          <p className="fmm-warning-text">
            {t('misc.fm_warning_irreversible')}
          </p>
          <label className="fmm-field-label" style={{ fontSize: "var(--mac-font-size-sm)", color: "var(--mac-error)" }}>
            {t('misc.fm_confirm_prefix')}<strong>ПОДТВЕРЖДАЮ</strong>{t('misc.fm_confirm_suffix')}
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
          {t('misc.fm_success_prefix')} {success}
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
