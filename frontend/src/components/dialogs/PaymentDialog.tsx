import { useState, useEffect, useRef } from 'react';
import { Check, Printer } from 'lucide-react';
import ModernDialog from './ModernDialog';
import React from 'react';
import { toast } from 'react-toastify';
import { usePaymentMethods } from '../../hooks/usePaymentMethods';
import './PaymentDialog.css';

import logger from '../../utils/logger';
import { Input } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import type { Appointment } from '../../types/domain/clinic';
import { getRegistrarPaymentSummary } from '../../api/registrarPayments';
import type { RegistrarPaymentInput, RegistrarPaymentSummary } from '../../api/registrarPayments';

interface PaymentDialogProps {
  isOpen: boolean;
  onClose: () => void;
  appointment: Appointment | null;
  onPaymentSuccess: (paymentData: RegistrarPaymentInput) => Promise<RegistrarPaymentSummary>;
  onPrintTicket?: (appointment?: unknown) => void;
}

const PaymentDialog = ({
  isOpen,
  onClose,
  appointment,
  onPaymentSuccess,
  onPrintTicket,
}: PaymentDialogProps) => {
  const { t: rawT } = useTranslation(); const t = rawT;
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPaid, setIsPaid] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [summary, setSummary] = useState<RegistrarPaymentSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [reload, setReload] = useState(0);
  const processingRef = useRef(false);
  const sessionRef = useRef(0);

  // Инициализация данных при открытии
  useEffect(() => {
    const session = ++sessionRef.current;
    if (isOpen && appointment) {
      setSummary(null);
      setIsLoading(true);
      setPaymentMethod('cash');
      setIsPaid(false);
      setErrors({});
      setIsProcessing(false);
      processingRef.current = false;
      getRegistrarPaymentSummary(appointment as Record<string, unknown>)
        .then((data) => {
          if (session !== sessionRef.current) return;
          setSummary(data);
          setPaymentAmount(String(data.remaining_amount));
        })
        .catch(() => {
          if (session === sessionRef.current) setErrors({ request: 'admin2.bill_load_error' });
        })
        .finally(() => {
          if (session === sessionRef.current) setIsLoading(false);
        });
    }
    return () => { sessionRef.current += 1; };
  }, [isOpen, appointment, reload]);

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!/^\d+(\.\d{1,2})?$/.test(paymentAmount) || !Number.isFinite(Number(paymentAmount)) || Number(paymentAmount) <= 0 || (summary && Number(paymentAmount) > Number(summary.remaining_amount))) {
      newErrors.amount = t('misc.pd_ukazhite_korrektnuyu_summu');
    }

    if (!paymentMethod) {
      newErrors.method = t('misc.pd_vyberite_sposob_oplaty');
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handlePayment = async () => {
    if (processingRef.current || !summary?.can_pay || !onPaymentSuccess) return;
    if (!validateForm()) return;
    if (!appointment) return;

    processingRef.current = true;
    setIsProcessing(true);
    const session = sessionRef.current;

    try {
      const result = await onPaymentSuccess({
        amount: Number(paymentAmount), method: paymentMethod,
        payment_snapshot: summary.snapshot,
      });
      if (!result?.snapshot) throw new Error('Payment receipt is missing');
      if (session !== sessionRef.current) return;
      setSummary(result);
      setIsPaid(true);
      toast.success(t('admin2.bill_pay_recorded'));
    } catch {
      if (session !== sessionRef.current) return;
      logger.error('Registrar payment was not confirmed');
      setSummary(null);
      setErrors({ request: 'admin2.bill_pay_record_error' });
      toast.error(t('admin2.bill_pay_record_error'));
    } finally {
      if (session === sessionRef.current) {
        processingRef.current = false;
        setIsProcessing(false);
      }
    }
  };

  const handlePrintAndClose = () => {
    if (onPrintTicket) {
      onPrintTicket(appointment);
    }
    onClose();
  };

  // UX Audit R-4.3 (Phase 3): payment methods через usePaymentMethods hook.
  // enableBackendFetch=true — fetches from GET /api/v1/payments/payment-methods.
  // Fallback на DEFAULT_PAYMENT_METHODS при ошибке API.
  const { paymentMethods } = usePaymentMethods({ enableBackendFetch: true });

  if (!appointment) return null;

  const actions = isPaid
    ? [
        {
          label: t('misc.pd_pechat_talona'),
          variant: 'primary',
          icon: <Printer size={16} />,
          onClick: handlePrintAndClose,
        },
        {
          label: t('misc.pd_zakryt'),
          variant: 'secondary',
          onClick: onClose,
        },
      ]
    : [
        {
          label: t('misc.pd_otmena_2'),
          variant: 'secondary',
          onClick: onClose,
          disabled: isProcessing,
        },
        {
          label: isProcessing ? t('misc.pd_obrabotka') : t('misc.pd_oplatit'),
          variant: 'success',
          icon: isProcessing ? null : <Check size={16} />,
          onClick: handlePayment,
          disabled: isProcessing || isLoading || !summary?.can_pay || !onPaymentSuccess,
        },
      ];

  // UX Audit Registrar #5: emoji в заголовке (✅/💳) заменены на text-only.
  // Иконки есть в actions (Printer/Check) и в success state (CheckCircle2).
  const dialogTitle = isPaid ? t('admin2.bill_pay_recorded') : t('misc.pd_oplata_uslug');
  const money = (value: string | number) => new Intl.NumberFormat('ru-RU').format(Number(value));

  return (
    <ModernDialog
      isOpen={isOpen}
      onClose={onClose}
      title={dialogTitle}
      actions={actions}
      dialogClassName="payment-dialog--styled"
      closeOnBackdrop={!isProcessing}
      closeOnEscape={!isProcessing}
      showCloseButton={!isProcessing}
    >
      {isLoading && <p role="status">{t('common.loading')}</p>}
      {errors.request && <div role="alert">
        <p>{t(errors.request)}</p>
        <button type="button" onClick={() => setReload((value) => value + 1)}>{t('common.refresh')}</button>
      </div>}
      {summary && <dl className="payment-patient-card" aria-live="polite">
        <dt>{t('admin2.bill_stat_total_amount')}</dt><dd>{money(summary.total_amount)} {t('admin2.bill_currency')}</dd>
        <dt>{t('admin2.bill_stat_paid')}</dt><dd>{money(summary.paid_amount)} {t('admin2.bill_currency')}</dd>
        <dt>{t('admin2.bill_balance_due')}</dt><dd>{money(summary.remaining_amount)} {t('admin2.bill_currency')}</dd>
      </dl>}
      {isPaid ? (
        <div className="payment-success">
          <div className="payment-success-icon">
            <Check size={28} />
          </div>
          <h4 className="payment-success-title">
            {t(summary?.payment_status === 'paid' ? 'admin2.bill_status_paid' : 'admin2.bill_status_partially_paid')}
          </h4>
          <p className="payment-success-details">
            Сумма:{' '}
            <strong>{new Intl.NumberFormat('ru-RU').format(parseFloat(paymentAmount))} сум</strong>
            <br />
            Способ: <strong>{paymentMethods.find((method) => method.value === paymentMethod)?.label || paymentMethod}</strong>
          </p>
          <div className="payment-success-cta">
            <p className="payment-success-cta-text">
              Теперь вы можете распечатать талон для пациента
            </p>
          </div>
        </div>
      ) : (
        <div>
          {/* Информация о пациенте */}
          <div className="payment-patient-card">
            <h4 className="payment-patient-title">
              Пациент
            </h4>
            <p className="payment-patient-name">
              {String(appointment.patient_fio ?? '')}
            </p>
            {!!appointment.services && (
              <p className="payment-patient-services">
                Услуги:{' '}
                {Array.isArray(appointment.services)
                  ? (appointment.services as unknown[]).map((s) => String(s)).join(', ')
                  : String(appointment.services ?? '')}
              </p>
            )}
          </div>

          {/* Форма оплаты */}
          <div className="payment-form">
            {/* Сумма */}
            <div>
              <label htmlFor="payment-amount" className="payment-field-label">
                {t('admin2.bill_pay_amount_label')} *
              </label>
              <Input
                id="payment-amount"
                type="number"
                aria-label={t('misc.pd_summa_k_oplate')}
                aria-invalid={!!errors.amount}
                aria-describedby={errors.amount ? 'payment-amount-error' : undefined}
                value={paymentAmount}
                disabled={isProcessing || isLoading || !summary?.can_pay}
                min="0.01"
                step="0.01"
                max={summary ? String(summary.remaining_amount) : undefined}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
                  setPaymentAmount(e.target.value);
                  if (errors.amount) {
                    setErrors((prev) => ({ ...prev, amount: '' }));
                  }
                }}
                placeholder={t('misc.pd_vvedite_summu')}
                className={`payment-amount-input ${errors.amount ? 'payment-amount-input--error' : ''}`}
              />
              {errors.amount && (
                <p id="payment-amount-error" className="payment-field-error">
                  {errors.amount}
                </p>
              )}
            </div>

            {/* Способ оплаты */}
            <div>
              <label className="payment-field-label">
                Способ оплаты *
              </label>
              <div className="payment-methods-grid">
                {paymentMethods.map((method) => {
                  // FIX (paymentMethods-jsx): config теперь хранит компонент
                  // Icon, а не React-элемент. Рендерим как компонент.
                  const MethodIcon = method.Icon || method.Icon;
                  return (
                  <button
                    key={method.value}
                    type="button"
                    disabled={isProcessing || isLoading || !summary?.can_pay}
                    onClick={() => {
                      setPaymentMethod(method.value);
                      if (errors.method) {
                        setErrors((prev) => ({ ...prev, method: '' }));
                      }
                    }}
                    className={`payment-method-btn ${paymentMethod === method.value ? 'payment-method-btn--selected' : ''}`}
                  >
                    {MethodIcon && <MethodIcon size={16} />}
                    {method.label}
                  </button>
                  );
                })}
              </div>
              {errors.method && (
                <p className="payment-field-error">
                  {errors.method}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </ModernDialog>
  );
};


export default PaymentDialog;
