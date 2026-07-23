
import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Check, Printer } from 'lucide-react';
import ModernDialog from './ModernDialog';
import React from 'react';
import { toast } from 'react-toastify';
// UX Audit R-4.3 (Phase 2): usePaymentMethods hook (future: backend-driven).
import { usePaymentMethods } from '../../hooks/usePaymentMethods';
// UX Audit Registrar #5: все inline-стили перенесены в PaymentDialog.css.
// useTheme удалён — больше не нужен (всё через macos tokens + [data-theme="dark"]).
// Также: emoji в заголовке (✅/💳) заменены на text-only (иконки и так есть в actions).
import './PaymentDialog.css';

import logger from '../../utils/logger';
import { Input } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
const PaymentDialog = ({
  isOpen,
  onClose,
  appointment,
  onPaymentSuccess,
  onPrintTicket,
}) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentMethod, setPaymentMethod] = useState(t('misc.pd_karta'));
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPaid, setIsPaid] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Инициализация данных при открытии
  useEffect(() => {
    if (isOpen && appointment) {
      setPaymentAmount(appointment.cost || appointment.payment_amount || '');
      setPaymentMethod(appointment.payment_type || t('misc.pd_karta'));
      setIsPaid(false);
      setErrors({});
      setIsProcessing(false);
    }
  }, [isOpen, appointment]);

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!paymentAmount || !Number.isFinite(parseFloat(paymentAmount)) || parseFloat(paymentAmount) <= 0) {
      newErrors.amount = t('misc.pd_ukazhite_korrektnuyu_summu');
    }

    if (!paymentMethod) {
      newErrors.method = t('misc.pd_vyberite_sposob_oplaty');
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handlePayment = async () => {
    if (!validateForm()) return;

    setIsProcessing(true);

    try {
      // UX Audit Registrar: убрана 1.5-секундная «имитация» (setTimeout).
      // Теперь: onPaymentSuccess callback делает РЕАЛЬНЫЙ API-запрос.
      if (onPaymentSuccess) {
        await onPaymentSuccess({
          appointmentId: appointment.id,
          amount: parseFloat(paymentAmount),
          method: paymentMethod,
          timestamp: new Date().toISOString(),
        });
      }

      setIsPaid(true);
      toast.success(t('misc.pd_oplata_otmechena_kak_poluche'));
    } catch (error) {
      logger.error('Payment error:', error);
      toast.error(error?.message || t('misc.pd_oshibka_pri_obrabotke_platez'));
    } finally {
      setIsProcessing(false);
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
          disabled: isProcessing,
        },
      ];

  // UX Audit Registrar #5: emoji в заголовке (✅/💳) заменены на text-only.
  // Иконки есть в actions (Printer/Check) и в success state (CheckCircle2).
  const dialogTitle = isPaid ? t('misc.pd_oplata_zavershena') : t('misc.pd_oplata_uslug');

  return (
    <ModernDialog
      isOpen={isOpen}
      onClose={onClose}
      title={dialogTitle}
      actions={actions}
      dialogClassName="payment-dialog--styled"
      closeOnBackdrop={!isProcessing}
      closeOnEscape={!isProcessing}
    >
      {isPaid ? (
        <div className="payment-success">
          <div className="payment-success-icon">
            <Check size={28} />
          </div>
          <h4 className="payment-success-title">
            Оплата успешно завершена
          </h4>
          <p className="payment-success-details">
            Сумма:{' '}
            <strong>{new Intl.NumberFormat('ru-RU').format(parseFloat(paymentAmount))} сум</strong>
            <br />
            Способ: <strong>{paymentMethod}</strong>
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
              {appointment.patient_fio}
            </p>
            {appointment.services && (
              <p className="payment-patient-services">
                Услуги:{' '}
                {Array.isArray(appointment.services)
                  ? appointment.services.join(', ')
                  : appointment.services}
              </p>
            )}
          </div>

          {/* Форма оплаты */}
          <div className="payment-form">
            {/* Сумма */}
            <div>
              <label htmlFor="payment-amount" className="payment-field-label">
                Сумма к оплате *
              </label>
              <Input
                id="payment-amount"
                type="number"
                aria-label={t('misc.pd_summa_k_oplate')}
                aria-invalid={!!errors.amount}
                aria-describedby={errors.amount ? 'payment-amount-error' : undefined}
                value={paymentAmount}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
                  setPaymentAmount(e.target.value);
                  if (errors.amount) {
                    setErrors((prev) => ({ ...prev, amount: null }));
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
                    onClick={() => {
                      setPaymentMethod(method.value);
                      if (errors.method) {
                        setErrors((prev) => ({ ...prev, method: null }));
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

PaymentDialog.propTypes = {
  isOpen: PropTypes.bool,
  onClose: PropTypes.func,
  appointment: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    patient_fio: PropTypes.string,
    cost: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    payment_amount: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    payment_type: PropTypes.string,
    services: PropTypes.oneOfType([
      PropTypes.arrayOf(PropTypes.string),
      PropTypes.string,
    ]),
  }),
  onPaymentSuccess: PropTypes.func,
  onPrintTicket: PropTypes.func,
};

export default PaymentDialog;
