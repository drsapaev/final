import React, { useState } from 'react';
import { 
  CheckCircle, 
  AlertCircle, 
  Info, 
  X, 
  AlertTriangle,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import './ModernAlert.css';

const ModernAlert = ({
  type = 'info',
  title,
  children,
  dismissible = false,
  collapsible = false,
  defaultExpanded = true,
  variant = 'filled',
  size = 'medium',
  icon = true,
  onDismiss,
  className = '',
  ...props
}) => {
  const { theme, getColor } = useTheme();
  const [isVisible, setIsVisible] = useState(true);
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  // Обработка закрытия
  const handleDismiss = () => {
    setIsVisible(false);
    setTimeout(() => {
      onDismiss?.();
    }, 300);
  };

  // Переключение развернутости
  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  // Получение конфигурации для типа
  const getTypeConfig = () => {
    const configs = {
      success: {
        icon: CheckCircle,
        color: getColor('success'),
        bgColor: theme === 'dark' 
          ? 'rgba(34, 197, 94, 0.15)' 
          : 'rgba(34, 197, 94, 0.1)',
        borderColor: getColor('success')
      },
      error: {
        icon: AlertCircle,
        color: getColor('danger'),
        bgColor: theme === 'dark' 
          ? 'rgba(239, 68, 68, 0.15)' 
          : 'rgba(239, 68, 68, 0.1)',
        borderColor: getColor('danger')
      },
      warning: {
        icon: AlertTriangle,
        color: getColor('warning'),
        bgColor: theme === 'dark' 
          ? 'rgba(245, 158, 11, 0.15)' 
          : 'rgba(245, 158, 11, 0.1)',
        borderColor: getColor('warning')
      },
      info: {
        icon: Info,
        color: getColor('info'),
        bgColor: theme === 'dark' 
          ? 'rgba(14, 165, 233, 0.15)' 
          : 'rgba(14, 165, 233, 0.1)',
        borderColor: getColor('info')
      }
    };

    return configs[type] || configs.info;
  };

  const typeConfig = getTypeConfig();
  const IconComponent = typeConfig.icon;

  if (!isVisible) return null;

  // Стили alert
  const alertStyles = {
    backgroundColor: variant === 'filled' 
      ? typeConfig.bgColor 
      : getColor('cardBg'),
    borderColor: typeConfig.borderColor,
    color: getColor('textPrimary')
  };

  return (
    <div
      className={`modern-alert ${type} ${variant} ${size} ${!isExpanded ? 'collapsed' : ''} ${className}`}
      style={alertStyles}
      role="alert"
      {...props}
    >
      {/* Заголовок */}
      <div className="alert-header">
        {/* Иконка */}
        {icon && (
          <div 
            className="alert-icon"
            style={{ color: typeConfig.color }}
          >
            <IconComponent size={size === 'small' ? 16 : size === 'large' ? 24 : 20} />
          </div>
        )}

        {/* Заголовок и кнопка сворачивания */}
        <div className="alert-title-section">
          {title && (
            <div 
              className={`alert-title ${collapsible ? 'clickable' : ''}`}
              onClick={collapsible ? toggleExpanded : undefined}
              style={{ color: getColor('textPrimary') }}
            >
              {title}
              {collapsible && (
                <span className="alert-toggle">
                  {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Кнопка закрытия */}
        {dismissible && (
          <button
            type="button"
            className="alert-dismiss"
            onClick={handleDismiss}
            aria-label="Закрыть уведомление"
            style={{ color: getColor('textSecondary') }}
          >
            <X size={16} />
          </button>
        )}
      </div>

      {/* Контент */}
      {(!collapsible || isExpanded) && children && (
        <div className="alert-content">
          {children}
        </div>
      )}
    </div>
  );
};

export default ModernAlert;


