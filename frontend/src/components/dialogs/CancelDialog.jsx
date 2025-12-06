import React, { useState, useEffect } from 'react';
import { AlertTriangle, X } from 'lucide-react';
import ModernDialog from './ModernDialog';
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';

import logger from '../../utils/logger';
const CancelDialog = ({ 
  isOpen, 
  onClose, 
  appointment, 
  onCancel 
}) => {
  const { theme, getColor } = useTheme();
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
      return 'Причина отмены должна содержать минимум 3 символа';
    }
    if (value.trim().length > 500) {
      return 'Причина отмены не должна превышать 500 символов';
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
      
      toast.success('Запись успешно отменена');
      onClose();
    } catch (error) {
      logger.error('Cancel error:', error);
      toast.error('Ошибка при отмене записи: ' + error.message);
    } finally {
      setIsProcessing(false);
    }
  };

  if (!appointment) return null;

  const actions = [
    {
      label: 'Отмена',
      variant: 'secondary',
      onClick: onClose,
      disabled: isProcessing
    },
    {
      label: isProcessing ? 'Отменяем...' : 'Подтвердить отмену',
      variant: 'danger',
      icon: isProcessing ? null : <X size={16} />,
      onClick: handleCancel,
      disabled: isProcessing || !!error || !reason.trim()
    }
  ];

  return (
    <ModernDialog
      isOpen={isOpen}
      onClose={onClose}
      title="Отменить запись"
      actions={actions}
      closeOnBackdrop={!isProcessing}
      closeOnEscape={!isProcessing}
    >
      <div>
        {/* Предупреждение */}
        <div style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '12px',
          padding: '16px',
          backgroundColor: theme === 'dark' ? '#451a03' : '#fef3c7',
          border: `1px solid ${theme === 'dark' ? '#92400e' : '#f59e0b'}`,
          borderRadius: '8px',
          marginBottom: '24px'
        }}>
          <AlertTriangle 
            size={20} 
            style={{ 
              color: theme === 'dark' ? '#fbbf24' : '#d97706',
              flexShrink: 0,
              marginTop: '2px'
            }} 
          />
          <div>
            <h4 style={{
              color: theme === 'dark' ? '#fbbf24' : '#92400e',
              fontSize: '14px',
              fontWeight: '600',
              margin: '0 0 4px 0'
            }}>
              Внимание!
            </h4>
            <p style={{
              color: theme === 'dark' ? '#fcd34d' : '#a16207',
              fontSize: '13px',
              margin: 0,
              lineHeight: '1.4'
            }}>
              Отмена записи необратима. Пациент получит уведомление об отмене.
            </p>
          </div>
        </div>

        {/* Информация о записи */}
        <div style={{ 
          marginBottom: '24px',
          padding: '16px',
          backgroundColor: theme === 'dark' ? '#374151' : '#f3f4f6',
          borderRadius: '8px'
        }}>
          <h4 style={{ 
            color: getColor('textPrimary'),
            margin: '0 0 12px 0',
            fontSize: '16px',
            fontWeight: '600'
          }}>
            Информация о записи
          </h4>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ 
                color: getColor('textSecondary'),
                fontSize: '14px'
              }}>
                Пациент:
              </span>
              <span style={{ 
                color: getColor('textPrimary'),
                fontSize: '14px',
                fontWeight: '500'
              }}>
                {appointment.patient_fio}
              </span>
            </div>
            
            {appointment.services && (
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ 
                  color: getColor('textSecondary'),
                  fontSize: '14px'
                }}>
                  Услуги:
                </span>
                <span style={{ 
                  color: getColor('textPrimary'),
                  fontSize: '14px',
                  fontWeight: '500',
                  textAlign: 'right',
                  maxWidth: '60%'
                }}>
                  {Array.isArray(appointment.services) 
                    ? appointment.services.join(', ') 
                    : appointment.services}
                </span>
              </div>
            )}
            
            {appointment.cost && (
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ 
                  color: getColor('textSecondary'),
                  fontSize: '14px'
                }}>
                  Стоимость:
                </span>
                <span style={{ 
                  color: getColor('textPrimary'),
                  fontSize: '14px',
                  fontWeight: '500'
                }}>
                  {appointment.cost.toLocaleString()} ₽
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Причина отмены */}
        <div>
          <label style={{
            display: 'block',
            fontSize: '14px',
            fontWeight: '500',
            marginBottom: '8px',
            color: getColor('textPrimary')
          }}>
            Причина отмены *
          </label>
          
          <textarea
            value={reason}
            onChange={handleReasonChange}
            placeholder="Укажите причину отмены записи..."
            rows={4}
            style={{
              width: '100%',
              padding: '12px',
              border: `2px solid ${error 
                ? '#ef4444' 
                : theme === 'dark' ? '#374151' : '#d1d5db'}`,
              borderRadius: '8px',
              backgroundColor: theme === 'dark' ? '#374151' : 'white',
              color: getColor('textPrimary'),
              fontSize: '14px',
              resize: 'vertical',
              minHeight: '100px',
              transition: 'border-color 0.2s ease',
              fontFamily: 'inherit'
            }}
            onFocus={(e) => {
              if (!error) {
                e.target.style.borderColor = '#3b82f6';
              }
            }}
            onBlur={(e) => {
              e.target.style.borderColor = error 
                ? '#ef4444' 
                : theme === 'dark' ? '#374151' : '#d1d5db';
            }}
            autoFocus
          />
          
          {/* Счетчик символов и ошибка */}
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginTop: '8px'
          }}>
            <div>
              {error && (
                <p style={{ 
                  color: '#ef4444', 
                  fontSize: '12px', 
                  margin: 0
                }}>
                  {error}
                </p>
              )}
            </div>
            <span style={{
              color: getColor('textSecondary'),
              fontSize: '12px'
            }}>
              {reason.length}/500
            </span>
          </div>
          
          {/* Подсказка */}
          <p style={{
            color: getColor('textSecondary'),
            fontSize: '12px',
            margin: '8px 0 0 0',
            fontStyle: 'italic'
          }}>
            Примеры: "Пациент заболел", "Изменились планы", "Врач недоступен"
          </p>
        </div>
      </div>
    </ModernDialog>
  );
};

export default CancelDialog;

