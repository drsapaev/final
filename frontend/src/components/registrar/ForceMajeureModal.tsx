
/**
 * ForceMajeureModal - Modal for mass queue operations
 * 
 * Features:
 * - Transfer all waiting patients to tomorrow
 * - Mass cancellation with refund
 * - Safety confirmation (dry run + type CONFIRM)
 */
import { api } from '../../api/client';
import { useState, useEffect, useCallback, useRef } from 'react';
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
import { Input } from '../ui/macos';
// UX Audit: inline-стили перенесены в ForceMajeureModal.css.
// useTheme + tokenManager удалены (auth через axios-interceptor, theme через CSS).
import './ForceMajeureModal.css';
import { useTranslation } from '../../i18n/useTranslation';
import { getErrorMessage } from '../../utils/type-guards';

interface ForceMajeureModalProps {
  isOpen: boolean;
  onClose: () => void;
  specialistId: string | number | null;
  specialistName?: string;
  /**
   * 3808 (REG-FE-025): канонический день очереди строки, открывшей
   * модал. Preview и мутация обязаны ссылаться на одного специалиста и
   * одну дату; null — SSOT-день клиники на бэкенде.
   */
  targetDate?: string | null;
  /**
   * 3808 review round 2 (P1 queue identity): канонический ID очереди
   * (DailyQueue) строки. Preview и обе мутации передают его бэкенду,
   * чтобы операция была жёстко привязана к очереди строки, а не к
   * резолюции специалиста (которая может выбрать общую ресурсную
   * очередь специальности).
   */
  dailyQueueId?: number | null;
  onSuccess?: (...args: unknown[]) => void;
}

interface DryRunResult {
  count: number;
  entries: unknown[];
  totalAmount: number;
}

/** Скоуп, валидированный последним успешным preview (round 2 P1). */
interface ValidatedPreviewScope {
  specialistId: string | number | null;
  targetDate: string | null;
  dailyQueueId: number | null;
}

const ForceMajeureModal = ({
  isOpen,
  onClose,
  specialistId,
  specialistName,
  targetDate,
  dailyQueueId,
  onSuccess
}: ForceMajeureModalProps) => {
  const { t: rawT } = useTranslation(); const t = rawT;
  const [activeTab, setActiveTab] = useState('transfer'); // 'transfer' | 'cancel'
  const [reason, setReason] = useState('');
  const [refundType, setRefundType] = useState('deposit'); // 'deposit' | 'bank_transfer'
  const [confirmText, setConfirmText] = useState('');
  const [loading, setLoading] = useState(false);
  const [dryRunResult, setDryRunResult] = useState<DryRunResult | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  // 3808: хранит i18n-ключ ошибки preview (перевод — в рендере).
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  // 3808: синхронный in-flight предохранитель — два клика в одном стеке
  // (до ре-рендера) не могут повторить финансовую мутацию.
  const submitInFlight = useRef(false);
  // 3808 review round 2 (P1 stale preview): поколение запросов preview.
  // Каждое новое открытие/перенаведение/refresh инвалидирует все
  // предыдущие: поздний (out-of-order) ответ чужой строки отбрасывается
  // и не может авторизовать мутацию текущей.
  const previewSeq = useRef(0);
  // Скоуп последнего УСПЕШНОГО preview — авторизация действия
  // привязана к нему и должна совпадать с текущей целью модала.
  const validatedScope = useRef<ValidatedPreviewScope | null>(null);

  // UX Audit: getAuthToken + tokenManager удалены — auth через axios-interceptor.

  // Load pending entries (dry run)
  const loadPendingEntries = useCallback(async () => {
    if (!specialistId) return;

    // 3808 review round 2 (P1 stale preview): фиксируем поколение запроса;
    // ответ применяется только если он всё ещё последний.
    const seq = ++previewSeq.current;

    // 3808: предыдущий снапшот сбрасывается ДО загрузки — устаревший
    // preview (другая строка/дата/очередь) не может авторизовать мутацию.
    setPreviewLoading(true);
    setPreviewError(null);
    setDryRunResult(null);
    validatedScope.current = null;

    try {
      // Preview и мутация связаны одним контрактом: specialist_id +
      // target_date + daily_queue_id. Дата и очередь передаются явно,
      // а не выводятся хостом или резолюцией специалиста на бэкенде.
      const targetParam = targetDate ? `&target_date=${encodeURIComponent(targetDate)}` : '';
      const queueParam = dailyQueueId ? `&daily_queue_id=${dailyQueueId}` : '';
      const response = await api.get(`/force-majeure/pending-entries?specialist_id=${specialistId}${targetParam}${queueParam}`);
      if (seq !== previewSeq.current) return; // поздний ответ чужой цели
      const data = response.data;
      setDryRunResult({
        count: data.length,
        entries: data,
        totalAmount: data.reduce((sum: number, e: Record<string, unknown>) => sum + (Number(e.total_amount) || 0), 0)
      });
      validatedScope.current = {
        specialistId,
        targetDate: targetDate ?? null,
        dailyQueueId: dailyQueueId ?? null,
      };
    } catch (err) {
      if (seq !== previewSeq.current) return; // ошибка устаревшего запроса
      logger.error('[ForceMajeureModal] Error loading pending entries:', err);
      // ключ, а не перевод: t нестабильна между рендерами и не должна
      // попадать в deps этого callback (иначе reset-effect зациклится)
      setPreviewError('misc.fm_preview_failed');
    } finally {
      if (seq === previewSeq.current) {
        setPreviewLoading(false);
      }
    }
  }, [specialistId, targetDate, dailyQueueId]);

  // Reset state when modal opens (or is re-targeted at another row/day/queue)
  useEffect(() => {
    if (isOpen) {
      setReason('');
      setConfirmText('');
      setError(null);
      setSuccess(null);
      setDryRunResult(null);
      setPreviewError(null);
      setPreviewLoading(false);
      validatedScope.current = null;
      loadPendingEntries();
    } else {
      // Закрытие модала инвалидирует висящий preview этого экземпляра.
      previewSeq.current += 1;
      validatedScope.current = null;
    }
  }, [isOpen, specialistId, targetDate, dailyQueueId, loadPendingEntries]);

  // Transfer to tomorrow
  const handleTransfer = async () => {
    // 3808: in-flight предохранитель — повторный клик в том же стеке
    // не может запустить вторую финансовую мутацию.
    if (submitInFlight.current || loading) return;

    if (!reason.trim() || reason.length < 5) {
      setError(t('misc.fm_reason_required'));
      return;
    }

    if (confirmText !== 'ПОДТВЕРЖДАЮ') {
      setError(t('misc.fm_confirm_required'));
      return;
    }

    // 3808: разрушающее действие разрешено только после успешного
    // непустого dry-run — ввод ПОДТВЕРЖДАЮ сам по себе ничего не
    // авторизует.
    if (!isScopeValidated) {
      setError(t('misc.fm_preview_required'));
      return;
    }

    submitInFlight.current = true;
    setLoading(true);
    setError(null);

    try {
      const response = await api.post('/force-majeure/transfer', {
          specialist_id: specialistId,
          // 3808: мутация привязана к той же дате и очереди, что и preview
          ...(targetDate ? { target_date: targetDate } : {}),
          ...(dailyQueueId ? { daily_queue_id: dailyQueueId } : {}),
          reason: reason,
          send_notifications: true
      });

      const result = response.data;
      setSuccess(t('misc.fm_transfer_success', { count: result.transferred || 0 }));
      logger.log('[ForceMajeureModal] Transfer successful:', result);
      if (onSuccess) onSuccess('transfer', result);
    } catch (err) {
      logger.error('[ForceMajeureModal] Transfer error:', err);
      setError(getErrorMessage(err) || t('misc.fm_network_error'));
    } finally {
      submitInFlight.current = false;
      setLoading(false);
    }
  };

  // Cancel with refund
  const handleCancel = async () => {
    // 3808: in-flight предохранитель — повторный клик в том же стеке
    // не может запустить вторую финансовую мутацию.
    if (submitInFlight.current || loading) return;

    if (!reason.trim() || reason.length < 5) {
      setError(t('misc.fm_reason_required'));
      return;
    }

    if (confirmText !== 'ПОДТВЕРЖДАЮ') {
      setError(t('misc.fm_confirm_required'));
      return;
    }

    // 3808: разрушающее действие разрешено только после успешного
    // непустого dry-run.
    if (!isScopeValidated) {
      setError(t('misc.fm_preview_required'));
      return;
    }

    submitInFlight.current = true;
    setLoading(true);
    setError(null);

    try {
      const response = await api.post('/force-majeure/cancel-with-refund', {
        specialist_id: specialistId,
        // 3808: мутация привязана к той же дате и очереди, что и preview
        ...(targetDate ? { target_date: targetDate } : {}),
        ...(dailyQueueId ? { daily_queue_id: dailyQueueId } : {}),
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
      setError(getErrorMessage(err) || t('misc.fm_network_error'));
    } finally {
      submitInFlight.current = false;
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const isConfirmValid = confirmText === 'ПОДТВЕРЖДАЮ';
  const isReasonValid = reason.trim().length >= 5;
  // 3808: серверный скоуп валидирован только успешным непустым dry-run,
  // причём скоуп этого dry-run обязан совпадать с ТЕКУЩЕЙ целью модала
  // (round 2 P1: поздний ответ другой строки не авторизует мутацию).
  const validated = validatedScope.current;
  const isScopeValidated =
    !previewLoading &&
    !previewError &&
    dryRunResult !== null &&
    dryRunResult.count > 0 &&
    validated !== null &&
    validated.specialistId === specialistId &&
    validated.targetDate === (targetDate ?? null) &&
    validated.dailyQueueId === (dailyQueueId ?? null);
  const primaryActionLabel = loading ? t('misc.fm_processing') : activeTab === 'transfer' ? t('misc.fm_transfer_button') : t('misc.fm_cancel_button');
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
        <XCircle size={18} />
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
      disabled: loading || !isConfirmValid || !isReasonValid || !isScopeValidated || Boolean(success)
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
            <Calendar size={18} />
            {t('misc.fm_tab_transfer')}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('cancel')}
            className={`fmm-tab-btn fmm-tab-btn--cancel ${activeTab === 'cancel' ? 'fmm-tab-btn--active' : ''}`}>
            <DollarSign size={18} />
            {t('misc.fm_tab_cancel')}
          </button>
        </div>

        {/* 3808: ошибка preview — разрушающее действие остаётся
            заблокированным; ввод ПОДТВЕРЖДАЮ ничего не авторизует */}
        {previewError &&
        <div className="fmm-error-box">
          {t(previewError)}
        </div>
        }

        {dryRunResult &&
        <div className="fmm-dry-run-card">
          <Users size={32} className="fmm-dry-run-icon" />
          <div className="fmm-dry-run-info">
            <p className="fmm-dry-run-count">
              {t('misc.fm_entries_count', { count: dryRunResult.count })}
            </p>
            <p className="fmm-dry-run-subtitle">
              {t('misc.fm_entries_action', { action: activeTab === 'transfer' ? t('misc.fm_transferred_word') : t('misc.fm_cancelled_word') })}
              {dryRunResult.totalAmount > 0 && t('misc.fm_entries_amount', { amount: dryRunResult.totalAmount.toLocaleString() })}
            </p>
            {dryRunResult.count === 0 &&
            <p className="fmm-error-text">
              {t('misc.fm_no_entries')}
            </p>
            }
          </div>
          <button
            type="button"
            onClick={loadPendingEntries}
            className="fmm-refresh-btn"
            aria-label={t('misc.fm_aria_refresh')}>
            <RefreshCw size={18} />
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
            onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setReason(e.target.value)}
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
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setRefundType(e.target.value)}
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
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setRefundType(e.target.value)}
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
            onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setConfirmText(e.target.value.toUpperCase())}
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



export default ForceMajeureModal;
