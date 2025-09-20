import React, { useState, useEffect } from 'react';
import { CreditCard, DollarSign, Check, Printer } from 'lucide-react';
import ModernDialog from './ModernDialog';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-hot-toast';

const PaymentDialog = ({ 
  isOpen, 
  onClose, 
  appointment, 
  onPaymentSuccess,
  onPrintTicket 
}) => {
  const { theme, getColor } = useTheme();
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
      // Имитация обработки платежа
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      setIsPaid(true);
      toast.success('Оплата прошла успешно!');
      
      // Вызываем callback с данными об оплате
      if (onPaymentSuccess) {
        onPaymentSuccess({
          appointmentId: appointment.id,
          amount: parseFloat(paymentAmount),
          method: paymentMethod,
          timestamp: new Date().toISOString()
        });
      }
    } catch (error) {
      console.error('Payment error:', error);
      toast.error('Ошибка при обработке платежа');
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
    { value: 'Карта', label: 'Банковская карта', icon: <CreditCard size={16} /> },
    { value: 'Наличные', label: 'Наличные', icon: <DollarSign size={16} /> },
    { value: 'Перевод', label: 'Банковский перевод', icon: <CreditCard size={16} /> },
    { value: 'Онлайн', label: 'Онлайн платеж', icon: <CreditCard size={16} /> }
  ];

  if (!appointment) return null;

  const actions = isPaid ? [
    {
      label: 'Печать талона',
      variant: 'primary',
      icon: <Printer size={16} />,
      onClick: handlePrintAndClose
    },
    {
      label: 'Закрыть',
      variant: 'secondary',
      onClick: onClose
    }
  ] : [
    {
      label: 'Отмена',
      variant: 'secondary',
      onClick: onClose,
      disabled: isProcessing
    },
    {
      label: isProcessing ? 'Обработка...' : 'Оплатить',
      variant: 'success',
      icon: isProcessing ? null : <Check size={16} />,
      onClick: handlePayment,
      disabled: isProcessing
    }
  ];

  return (
    <ModernDialog
      isOpen={isOpen}
      onClose={onClose}
      title={isPaid ? "✅ Оплата завершена" : "💳 Оплата услуг"}
      actions={actions}
      closeOnBackdrop={!isProcessing}
      closeOnEscape={!isProcessing}
    >
      {isPaid ? (
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <div style={{ 
            fontSize: '48px', 
            marginBottom: '16px',
            color: '#10b981'
          }}>
            ✅
          </div>
          <h4 style={{ 
            color: getColor('textPrimary'),
            marginBottom: '8px',
            fontSize: '18px',
            fontWeight: '600'
          }}>
            Оплата успешно завершена
          </h4>
          <p style={{ 
            color: getColor('textSecondary'),
            marginBottom: '16px'
          }}>
            Сумма: <strong>{parseFloat(paymentAmount).toLocaleString()} ₽</strong><br />
            Способ: <strong>{paymentMethod}</strong>
          </p>
          <div style={{
            padding: '12px',
            backgroundColor: theme === 'dark' ? '#065f46' : '#d1fae5',
            borderRadius: '8px',
            border: `1px solid ${theme === 'dark' ? '#059669' : '#10b981'}`
          }}>
            <p style={{ 
              color: theme === 'dark' ? '#34d399' : '#065f46',
              fontSize: '14px',
              margin: 0
            }}>
              Теперь вы можете распечатать талон для пациента
            </p>
          </div>
        </div>
      ) : (
        <div>
          {/* Информация о пациенте */}
          <div style={{ 
            marginBottom: '24px',
            padding: '16px',
            backgroundColor: theme === 'dark' ? '#374151' : '#f3f4f6',
            borderRadius: '8px'
          }}>
            <h4 style={{ 
              color: getColor('textPrimary'),
              margin: '0 0 8px 0',
              fontSize: '16px',
              fontWeight: '600'
            }}>
              Пациент
            </h4>
            <p style={{ 
              color: getColor('textSecondary'),
              margin: 0,
              fontSize: '14px'
            }}>
              {appointment.patient_fio}
            </p>
            {appointment.services && (
              <p style={{ 
                color: getColor('textSecondary'),
                margin: '4px 0 0 0',
                fontSize: '12px'
              }}>
                Услуги: {Array.isArray(appointment.services) 
                  ? appointment.services.join(', ') 
                  : appointment.services}
              </p>
            )}
          </div>

          {/* Форма оплаты */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Сумма */}
            <div>
              <label style={{
                display: 'block',
                fontSize: '14px',
                fontWeight: '500',
                marginBottom: '8px',
                color: getColor('textPrimary')
              }}>
                Сумма к оплате *
              </label>
              <input
                type="number"
                value={paymentAmount}
                onChange={(e) => {
                  setPaymentAmount(e.target.value);
                  if (errors.amount) {
                    setErrors(prev => ({ ...prev, amount: null }));
                  }
                }}
                placeholder="Введите сумму"
                style={{
                  width: '100%',
                  padding: '12px',
                  border: `2px solid ${errors.amount 
                    ? '#ef4444' 
                    : theme === 'dark' ? '#374151' : '#d1d5db'}`,
                  borderRadius: '8px',
                  backgroundColor: theme === 'dark' ? '#374151' : 'white',
                  color: getColor('textPrimary'),
                  fontSize: '16px',
                  transition: 'border-color 0.2s ease'
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = '#3b82f6';
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = errors.amount 
                    ? '#ef4444' 
                    : theme === 'dark' ? '#374151' : '#d1d5db';
                }}
              />
              {errors.amount && (
                <p style={{ 
                  color: '#ef4444', 
                  fontSize: '12px', 
                  margin: '4px 0 0 0' 
                }}>
                  {errors.amount}
                </p>
              )}
            </div>

            {/* Способ оплаты */}
            <div>
              <label style={{
                display: 'block',
                fontSize: '14px',
                fontWeight: '500',
                marginBottom: '8px',
                color: getColor('textPrimary')
              }}>
                Способ оплаты *
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                {paymentMethods.map((method) => (
                  <button
                    key={method.value}
                    type="button"
                    onClick={() => {
                      setPaymentMethod(method.value);
                      if (errors.method) {
                        setErrors(prev => ({ ...prev, method: null }));
                      }
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '12px',
                      border: `2px solid ${paymentMethod === method.value 
                        ? '#3b82f6' 
                        : theme === 'dark' ? '#374151' : '#d1d5db'}`,
                      borderRadius: '8px',
                      backgroundColor: paymentMethod === method.value
                        ? theme === 'dark' ? '#1e3a8a' : '#dbeafe'
                        : theme === 'dark' ? '#374151' : 'white',
                      color: paymentMethod === method.value
                        ? '#3b82f6'
                        : getColor('textPrimary'),
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      fontSize: '14px'
                    }}
                  >
                    {method.icon}
                    {method.label}
                  </button>
                ))}
              </div>
              {errors.method && (
                <p style={{ 
                  color: '#ef4444', 
                  fontSize: '12px', 
                  margin: '4px 0 0 0' 
                }}>
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
