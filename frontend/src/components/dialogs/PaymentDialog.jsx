import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { CreditCard, Check, Printer, Banknote, ArrowLeftRight, Globe } from 'lucide-react';
import ModernDialog from './ModernDialog';
import { toast } from 'react-toastify';
// UX Audit Registrar #5: все inline-стили перенесены в PaymentDialog.css.
// useTheme удалён — больше не нужен (всё через macos tokens + [data-theme="dark"]).
// Также: emoji в заголовке (✅/💳) заменены на text-only (иконки и так есть в actions).
import './PaymentDialog.css';

import logger from '../../utils/logger';
import { Input } from '../ui/macos';
const PaymentDialog = ({
  isOpen,
  onClose,
  appointment,
  onPaymentSuccess,
  onPrintTicket,
}) => {
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('Карта');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPaid, setIsPaid] = useState(false);
  const [errors, setErrors] = useState({});

  // Инициализация данных при открытии
  useEffect(() => {
    if (isOpen && appointment) {
      setPaymentAmount(appointment.cost || appointment.payment_amount || '');
      setPaymentMethod(appointment.payment_type || 'Карта');
      setIsPaid(false);
      setErrors({});
      setIsProcessing(false);
    }
  }, [isOpen, appointment]);

  const validateForm = () => {
    const newErrors = {};

    if (!paymentAmount || !Number.isFinite(parseFloat(paymentAmount)) || parseFloat(paymentAmount) <= 0) {
      newErrors.amount = 'Укажите корректную сумму';
    }

    if (!paymentMethod) {
      newErrors.method = 'Выберите способ оплаты';
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
      toast.success('Оплата отмечена как полученная');
    } catch (error) {
      logger.error('Payment error:', error);
      toast.error(error?.message || 'Ошибка при обработке платежа');
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

  // UX Audit R-4.3: уникальные иконки для каждого способа оплаты.
  // Раньше: 3 из 4 кнопок имели одинаковую иконку CreditCard —
  // пользователь не различал их визуально (Nielsen #2 + #4).
  const paymentMethods = [
    {
      value: 'Карта',
      label: 'Банковская карта',
      icon: <CreditCard size={16} />,
    },
    { value: 'Наличные', label: 'Наличные', icon: <Banknote size={16} /> },
    {
      value: 'Перевод',
      label: 'Банковский перевод',
      icon: <ArrowLeftRight size={16} />,
    },
    { value: 'Онлайн', label: 'Онлайн платеж', icon: <Globe size={16} /> },
  ];

  if (!appointment) return null;

  const actions = isPaid
    ? [
        {
          label: 'Печать талона',
          variant: 'primary',
          icon: <Printer size={16} />,
          onClick: handlePrintAndClose,
        },
        {
          label: 'Закрыть',
          variant: 'secondary',
          onClick: onClose,
        },
      ]
    : [
        {
          label: 'Отмена',
          variant: 'secondary',
          onClick: onClose,
          disabled: isProcessing,
        },
        {
          label: isProcessing ? 'Обработка...' : 'Оплатить',
          variant: 'success',
          icon: isProcessing ? null : <Check size={16} />,
          onClick: handlePayment,
          disabled: isProcessing,
        },
      ];

  // UX Audit Registrar #5: emoji в заголовке (✅/💳) заменены на text-only.
  // Иконки есть в actions (Printer/Check) и в success state (CheckCircle2).
  const dialogTitle = isPaid ? 'Оплата завершена' : 'Оплата услуг';

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
                aria-label="Сумма к оплате"
                aria-invalid={!!errors.amount}
                aria-describedby={errors.amount ? 'payment-amount-error' : undefined}
                value={paymentAmount}
                onChange={(e) => {
                  setPaymentAmount(e.target.value);
                  if (errors.amount) {
                    setErrors((prev) => ({ ...prev, amount: null }));
                  }
                }}
                placeholder="Введите сумму"
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
                {paymentMethods.map((method) => (
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
                    {method.icon}
                    {method.label}
                  </button>
                ))}
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
