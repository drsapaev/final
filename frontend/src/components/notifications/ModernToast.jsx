import React, { useState, useEffect } from 'react';
import { 
  CheckCircle, 
  AlertCircle, 
  Info, 
  X, 
  AlertTriangle 
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import './ModernToast.css';

const ModernToast = ({
  id,
  type = 'info',
  title,
  message,
  duration = 5000,
  persistent = false,
  position = 'bottom-right',
  showProgress = true,
  onClose,
  action,
  className = '',
  ...props
}) => {
  const { theme, getColor } = useTheme();
  const [isVisible, setIsVisible] = useState(false);
  const [isExiting, setIsExiting] = useState(false);
  const [progress, setProgress] = useState(100);

  // Показать toast при монтировании
  useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), 50);
    return () => clearTimeout(timer);
  }, []);

  // Автоматическое закрытие
  useEffect(() => {
    if (persistent || duration <= 0) return;

    const progressInterval = setInterval(() => {
      setProgress(prev => {
        const newProgress = prev - (100 / (duration / 100));
        return Math.max(0, newProgress);
      });
    }, 100);

    const closeTimer = setTimeout(() => {
      handleClose();
    }, duration);

    return () => {
      clearInterval(progressInterval);
      clearTimeout(closeTimer);
    };
  }, [duration, persistent]);

  // Обработка закрытия
  const handleClose = () => {
    setIsExiting(true);
    setTimeout(() => {
      onClose?.(id);
    }, 300);
  };

  // Получение иконки и цветов для типа
  const getTypeConfig = () => {
    const configs = {
      success: {
        icon: CheckCircle,
        color: getColor('success'),
        bgColor: 'rgba(34, 197, 94, 0.1)',
        borderColor: getColor('success')
      },
      error: {
        icon: AlertCircle,
        color: getColor('danger'),
        bgColor: 'rgba(239, 68, 68, 0.1)',
        borderColor: getColor('danger')
      },
      warning: {
        icon: AlertTriangle,
        color: getColor('warning'),
        bgColor: 'rgba(245, 158, 11, 0.1)',
        borderColor: getColor('warning')
      },
      info: {
        icon: Info,
        color: getColor('info'),
        bgColor: 'rgba(14, 165, 233, 0.1)',
        borderColor: getColor('info')
      }
    };

    return configs[type] || configs.info;
  };

  const typeConfig = getTypeConfig();
  const IconComponent = typeConfig.icon;

  // Стили toast
  const toastStyles = {
    backgroundColor: getColor('cardBg'),
    color: getColor('textPrimary'),
    borderColor: typeConfig.borderColor,
    borderLeftColor: typeConfig.color,
    boxShadow: theme === 'dark' 
      ? '0 10px 25px rgba(0, 0, 0, 0.3)' 
      : '0 10px 25px rgba(0, 0, 0, 0.1)'
  };

  return (
    <div
      className={`modern-toast ${type} ${position} ${isVisible ? 'visible' : ''} ${isExiting ? 'exiting' : ''} ${className}`}
      style={toastStyles}
      role="alert"
      aria-live="polite"
      {...props}
    >
      {/* Иконка */}
      <div 
        className="toast-icon"
        style={{ color: typeConfig.color }}
      >
        <IconComponent size={20} />
      </div>

      {/* Контент */}
      <div className="toast-content">
        {title && (
          <div 
            className="toast-title"
            style={{ color: getColor('textPrimary') }}
          >
            {title}
          </div>
        )}
        {message && (
          <div 
            className="toast-message"
            style={{ color: getColor('textSecondary') }}
          >
            {message}
          </div>
        )}
        
        {/* Действие */}
        {action && (
          <div className="toast-action">
            <button
              type="button"
              className="toast-action-btn"
              onClick={action.onClick}
              style={{
                color: typeConfig.color,
                backgroundColor: 'transparent'
              }}
            >
              {action.label}
            </button>
          </div>
        )}
      </div>

      {/* Кнопка закрытия */}
      <button
        type="button"
        className="toast-close"
        onClick={handleClose}
        aria-label="Закрыть уведомление"
        style={{ color: getColor('textSecondary') }}
      >
        <X size={16} />
      </button>

      {/* Прогресс-бар */}
      {showProgress && !persistent && duration > 0 && (
        <div 
          className="toast-progress"
          style={{
            backgroundColor: typeConfig.color,
            width: `${progress}%`
          }}
        />
      )}
    </div>
  );
};

export default ModernToast;


