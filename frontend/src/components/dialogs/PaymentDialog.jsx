import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { CreditCard, DollarSign, Check, Printer } from 'lucide-react';
import ModernDialog from './ModernDialog';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';

import logger from '../../utils/logger';
const PaymentDialog = ({
  isOpen,
  onClose,
  appointment,
  onPaymentSuccess,
  onPrintTicket,
}) => {
  const { theme, getColor } = useTheme();
  const surfaceStyle = {
    backgroundColor: 'var(--mac-bg-secondary)',
    border: `1px solid ${theme === 'dark' ? 'color-mix(in srgb, white, transparent 92%)' : 'var(--mac-border)'}`,
    borderRadius: '14px',
  };
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

    if (!paymentAmount || parseFloat(paymentAmount) <= 0) {
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
      // Раньше здесь был `await new Promise(resolve => setTimeout(resolve, 1500))`
      // — искусственная задержка, которая тратила ~60 сек/день регистратора.
      //
      // Теперь: onPaymentSuccess callback делает РЕАЛЬНЫЙ API-запрос
      // (api.post('/registrar/records/actions', {action: 'mark_paid', ...}))
      // в useRegistrarActions.handlePayment(). Мы await'им этот callback
      // и показываем loading state до реального завершения.
      //
      // Если callback не передан — просто отмечаем как оплачено (fallback
      // для тестов/демо без backend).
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
      // Не меняем isPaid — диалог остаётся в режиме ввода оплаты.
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

  const paymentMethods = [
    {
      value: 'Карта',
      label: 'Банковская карта',
      icon: <CreditCard size={16} />,
    },
    { value: 'Наличные', label: 'Наличные', icon: <DollarSign size={16} /> },
    {
      value: 'Перевод',
      label: 'Банковский перевод',
      icon: <CreditCard size={16} />,
    },
    { value: 'Онлайн', label: 'Онлайн платеж', icon: <CreditCard size={16} /> },
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

  return (
    <ModernDialog
      isOpen={isOpen}
      onClose={onClose}
      title={isPaid ? '✅ Оплата завершена' : '💳 Оплата услуг'}
      actions={actions}
      dialogStyle={{
        backgroundColor: 'var(--mac-bg-primary)',
      }}
      closeOnBackdrop={!isProcessing}
      closeOnEscape={!isProcessing}
    >
      {isPaid ? (
        <div style={{ textAlign: 'center', padding: '8px 0 4px' }}>
          <div
            style={{
              width: '64px',
              height: '64px',
              margin: '0 auto 16px',
              borderRadius: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background:
                theme === 'dark' ? 'rgba(16, 185, 129, 0.14)' : 'var(--mac-success-bg)',
              color: 'var(--mac-success)',
              border: `1px solid ${theme === 'dark' ? 'rgba(16, 185, 129, 0.24)' : 'var(--mac-success-border, color-mix(in srgb, var(--mac-success), transparent 60%))'}`,
            }}
          >
            <Check size={28} />
          </div>
          <h4
            style={{
              color: getColor('textPrimary'),
              marginBottom: '8px',
              fontSize: '18px',
              fontWeight: '600',
            }}
          >
            Оплата успешно завершена
          </h4>
          <p
            style={{
              color: getColor('textSecondary'),
              marginBottom: '16px',
              lineHeight: 1.5,
            }}
          >
            Сумма:{' '}
            <strong>{parseFloat(paymentAmount).toLocaleString()} ₽</strong>
            <br />
            Способ: <strong>{paymentMethod}</strong>
          </p>
          <div
            style={{
              padding: '14px',
              backgroundColor:
                theme === 'dark' ? 'rgba(16, 185, 129, 0.08)' : '#f0fdf4',
              borderRadius: '12px',
              border: `1px solid ${theme === 'dark' ? 'rgba(16, 185, 129, 0.24)' : '#bbf7d0'}`,
            }}
          >
            <p
              style={{
                color: theme === 'dark' ? '#6ee7b7' : '#065f46',
                fontSize: '14px',
                margin: 0,
                lineHeight: 1.5,
              }}
            >
              Теперь вы можете распечатать талон для пациента
            </p>
          </div>
        </div>
      ) : (
        <div>
          {/* Информация о пациенте */}
          <div
            style={{
              marginBottom: '24px',
              padding: '16px',
              ...surfaceStyle,
            }}
          >
            <h4
              style={{
                color: getColor('textPrimary'),
                margin: '0 0 8px 0',
                fontSize: '16px',
                fontWeight: '600',
              }}
            >
              Пациент
            </h4>
            <p
              style={{
                color: getColor('textSecondary'),
                margin: 0,
                fontSize: '14px',
              }}
            >
              {appointment.patient_fio}
            </p>
            {appointment.services && (
              <p
                style={{
                  color: getColor('textSecondary'),
                  margin: '4px 0 0 0',
                  fontSize: '12px',
                }}
              >
                Услуги:{' '}
                {Array.isArray(appointment.services)
                  ? appointment.services.join(', ')
                  : appointment.services}
              </p>
            )}
          </div>

          {/* Форма оплаты */}
          <div
            style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}
          >
            {/* Сумма */}
            <div>
              <label
                htmlFor="payment-amount"
                style={{
                  display: 'block',
                  fontSize: '14px',
                  fontWeight: '500',
                  marginBottom: '8px',
                  color: getColor('textPrimary'),
                }}
              >
                Сумма к оплате *
              </label>
              <input
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
                style={{
                  width: '100%',
                  padding: '12px 14px',
                  border: `1px solid ${
                    errors.amount
                      ? 'var(--mac-error)'
                      : theme === 'dark'
                        ? 'color-mix(in srgb, white, transparent 90%)'
                        : 'var(--mac-border)'
                  }`,
                  borderRadius: '12px',
                  backgroundColor:
                    theme === 'dark' ? 'color-mix(in srgb, white, transparent 96%)' : 'white',
                  color: getColor('textPrimary'),
                  fontSize: '16px',
                  transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
                  outline: 'none',
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = 'var(--mac-accent-blue)';
                  e.target.style.boxShadow =
                    '0 0 0 3px rgba(59, 130, 246, 0.12)';
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = errors.amount
                    ? 'var(--mac-error)'
                    : theme === 'dark'
                      ? 'color-mix(in srgb, white, transparent 90%)'
                      : 'var(--mac-border)';
                  e.target.style.boxShadow = 'none';
                }}
              />
              {errors.amount && (
                <p
                  id="payment-amount-error"
                  style={{
                    color: 'var(--mac-error)',
                    fontSize: '12px',
                    margin: '4px 0 0 0',
                  }}
                >
                  {errors.amount}
                </p>
              )}
            </div>

            {/* Способ оплаты */}
            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '14px',
                  fontWeight: '500',
                  marginBottom: '8px',
                  color: getColor('textPrimary'),
                }}
              >
                Способ оплаты *
              </label>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '8px',
                }}
              >
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
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '12px 14px',
                      border: `1px solid ${
                        paymentMethod === method.value
                          ? 'var(--mac-accent-blue)'
                          : theme === 'dark'
                            ? 'color-mix(in srgb, white, transparent 90%)'
                            : 'var(--mac-border)'
                      }`,
                      borderRadius: '12px',
                      backgroundColor:
                        paymentMethod === method.value
                          ? theme === 'dark'
                            ? 'rgba(59, 130, 246, 0.16)'
                            : 'var(--mac-accent-bg)'
                          : theme === 'dark'
                            ? 'color-mix(in srgb, white, transparent 96%)'
                            : 'white',
                      color:
                        paymentMethod === method.value
                          ? 'var(--mac-accent-blue-hover)'
                          : getColor('textPrimary'),
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      fontSize: '14px',
                      fontWeight: '500',
                    }}
                  >
                    {method.icon}
                    {method.label}
                  </button>
                ))}
              </div>
              {errors.method && (
                <p
                  style={{
                    color: 'var(--mac-error)',
                    fontSize: '12px',
                    margin: '4px 0 0 0',
                  }}
                >
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
