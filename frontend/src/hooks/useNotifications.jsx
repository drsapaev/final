/**
 * Улучшенная система уведомлений для медицинских интерфейсов
 * Основана на принципах доступности и медицинских стандартах UX
 */

import React, { useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useAnimation } from './useAnimation';
import { useReducedMotion } from './useEnhancedMediaQuery';

// Типы уведомлений
export const notificationTypes = {
  SUCCESS: 'success',
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info',
  MEDICAL: 'medical',
  APPOINTMENT: 'appointment',
  PAYMENT: 'payment',
  EMERGENCY: 'emergency'
};

// Конфигурация уведомлений
export const notificationConfig = {
  defaultDuration: 5000,
  maxNotifications: 5,
  positions: {
    'top-right': { top: '20px', right: '20px' },
    'top-left': { top: '20px', left: '20px' },
    'bottom-right': { bottom: '20px', right: '20px' },
    'bottom-left': { bottom: '20px', left: '20px' },
    'top-center': { top: '20px', left: '50%', transform: 'translateX(-50%)' },
    'bottom-center': { bottom: '20px', left: '50%', transform: 'translateX(-50%)' }
  },
  animations: {
    enter: 'slideInRight',
    exit: 'slideOutRight'
  }
};

// Хук для управления уведомлениями
export const useNotifications = (options = {}) => {
  const {
    maxNotifications = notificationConfig.maxNotifications,
    defaultDuration = notificationConfig.defaultDuration

  } = options;

  const [notifications, setNotifications] = useState([]);
  const [isPaused, setIsPaused] = useState(false);void
  useReducedMotion();

  // Удаление уведомления
  const removeNotification = useCallback((id) => {
    setNotifications((prev) => prev.filter((notification) => notification.id !== id));
  }, []);

  // Добавление уведомления
  const addNotification = useCallback((notification) => {
    const id = Date.now() + Math.random();

    const newNotification = {
      id,
      type: notification.type || notificationTypes.INFO,
      title: notification.title || '',
      message: notification.message || '',
      duration: notification.duration !== undefined ? notification.duration : defaultDuration,
      persistent: notification.persistent || false,
      actions: notification.actions || [],
      metadata: notification.metadata || {},
      timestamp: new Date(),
      ...notification
    };

    setNotifications((prev) => {
      const updated = [newNotification, ...prev];
      return updated.slice(0, maxNotifications);
    });

    // Автоматическое удаление (если не persistent)
    if (!newNotification.persistent && newNotification.duration > 0) {
      setTimeout(() => {
        removeNotification(id);
      }, newNotification.duration);
    }

    return id;
  }, [maxNotifications, defaultDuration, removeNotification]);

  // Очистка всех уведомлений
  const clearAll = useCallback(() => {
    setNotifications([]);
  }, []);

  // Пауза/возобновление автоскрытия
  const pauseAutoHide = useCallback(() => {
    setIsPaused(true);
  }, []);

  const resumeAutoHide = useCallback(() => {
    setIsPaused(false);
  }, []);

  // Уведомления по типам
  const showSuccess = useCallback((message, options = {}) => {
    return addNotification({
      type: notificationTypes.SUCCESS,
      message,
      ...options
    });
  }, [addNotification]);

  const showError = useCallback((message, options = {}) => {
    return addNotification({
      type: notificationTypes.ERROR,
      message,
      persistent: true,
      ...options
    });
  }, [addNotification]);

  const showWarning = useCallback((message, options = {}) => {
    return addNotification({
      type: notificationTypes.WARNING,
      message,
      ...options
    });
  }, [addNotification]);

  const showInfo = useCallback((message, options = {}) => {
    return addNotification({
      type: notificationTypes.INFO,
      message,
      ...options
    });
  }, [addNotification]);

  const showMedical = useCallback((message, options = {}) => {
    return addNotification({
      type: notificationTypes.MEDICAL,
      message,
      ...options
    });
  }, [addNotification]);

  const showAppointment = useCallback((message, options = {}) => {
    return addNotification({
      type: notificationTypes.APPOINTMENT,
      message,
      ...options
    });
  }, [addNotification]);

  const showPayment = useCallback((message, options = {}) => {
    return addNotification({
      type: notificationTypes.PAYMENT,
      message,
      ...options
    });
  }, [addNotification]);

  const showEmergency = useCallback((message, options = {}) => {
    return addNotification({
      type: notificationTypes.EMERGENCY,
      message,
      persistent: true,
      ...options
    });
  }, [addNotification]);

  return {
    notifications,
    isPaused,
    addNotification,
    removeNotification,
    clearAll,
    pauseAutoHide,
    resumeAutoHide,
    showSuccess,
    showError,
    showWarning,
    showInfo,
    showMedical,
    showAppointment,
    showPayment,
    showEmergency
  };
};

// Компонент уведомления
export const Notification = ({
  notification,
  onRemove,
  onAction,
  position = 'top-right',
  className = '',
  ...props
}) => {
  const { shouldRender, animationClasses } = useAnimation(true, 'slideInRight', 300);
  const { prefersReducedMotion } = useReducedMotion();

  const handleAction = (action) => {
    if (action.onClick) {
      action.onClick(notification);
    }
    onAction?.(action, notification);
    if (action.closeOnClick !== false) {
      onRemove(notification.id);
    }
  };

  if (!shouldRender) return null;

  const typeConfig = {
    [notificationTypes.SUCCESS]: { icon: '✅', color: '#10b981', bgColor: '#d1fae5' },
    [notificationTypes.ERROR]: { icon: '❌', color: '#ef4444', bgColor: '#fee2e2' },
    [notificationTypes.WARNING]: { icon: '⚠️', color: '#f59e0b', bgColor: '#fef3c7' },
    [notificationTypes.INFO]: { icon: 'ℹ️', color: '#3b82f6', bgColor: '#dbeafe' },
    [notificationTypes.MEDICAL]: { icon: '🏥', color: '#8b5cf6', bgColor: '#e9d5ff' },
    [notificationTypes.APPOINTMENT]: { icon: '📅', color: '#06b6d4', bgColor: '#cffafe' },
    [notificationTypes.PAYMENT]: { icon: '💳', color: '#10b981', bgColor: '#d1fae5' },
    [notificationTypes.EMERGENCY]: { icon: '🚨', color: '#ef4444', bgColor: '#fee2e2' }
  };

  const config = typeConfig[notification.type] || typeConfig[notificationTypes.INFO];

  return (
    <div
      className={`notification ${notification.type} ${animationClasses} ${className}`}
      style={{
        position: 'relative',
        backgroundColor: config.bgColor,
        border: `1px solid ${config.color}`,
        borderRadius: '8px',
        padding: '16px',
        marginBottom: '12px',
        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
        minWidth: '300px',
        maxWidth: '400px',
        zIndex: 1000,
        ...notificationConfig.positions[position]
      }}
      {...props}>
      
      {/* Кнопка закрытия */}
      <button
        onClick={() => onRemove(notification.id)}
        style={{
          position: 'absolute',
          top: '8px',
          right: '8px',
          background: 'none',
          border: 'none',
          fontSize: '16px',
          cursor: 'pointer',
          color: config.color,
          padding: '4px',
          borderRadius: '4px',
          transition: prefersReducedMotion ? 'none' : 'background-color 0.2s ease'
        }}
        onMouseEnter={(e) => {
          if (!prefersReducedMotion) {
            e.target.style.backgroundColor = `${config.color}20`;
          }
        }}
        onMouseLeave={(e) => {
          if (!prefersReducedMotion) {
            e.target.style.backgroundColor = 'transparent';
          }
        }}
        aria-label="Закрыть уведомление">
        
        ×
      </button>

      {/* Содержимое */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
        <div
          style={{
            fontSize: '20px',
            flexShrink: 0,
            marginTop: '2px'
          }}>
          
          {config.icon}
        </div>

        <div style={{ flex: 1 }}>
          {notification.title &&
          <div
            style={{
              fontSize: '14px',
              fontWeight: '600',
              color: config.color,
              marginBottom: '4px'
            }}>
            
              {notification.title}
            </div>
          }

          <div
            style={{
              fontSize: '14px',
              color: '#374151',
              lineHeight: '1.4'
            }}>
            
            {notification.message}
          </div>

          {/* Действия */}
          {notification.actions && notification.actions.length > 0 &&
          <div
            style={{
              display: 'flex',
              gap: '8px',
              marginTop: '12px',
              flexWrap: 'wrap'
            }}>
            
              {notification.actions.map((action, index) =>
            <button
              key={index}
              onClick={() => handleAction(action)}
              style={{
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: '500',
                border: `1px solid ${config.color}`,
                borderRadius: '6px',
                backgroundColor: config.color,
                color: '#ffffff',
                cursor: 'pointer',
                transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                if (!prefersReducedMotion) {
                  e.target.style.opacity = '0.9';
                }
              }}
              onMouseLeave={(e) => {
                if (!prefersReducedMotion) {
                  e.target.style.opacity = '1';
                }
              }}>
              
                  {action.label}
                </button>
            )}
            </div>
          }
        </div>
      </div>

      {/* Прогресс бар для автоскрытия */}
      {!notification.persistent && notification.duration > 0 &&
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: '3px',
          backgroundColor: `${config.color}30`,
          borderRadius: '0 0 8px 8px'
        }}>
        
          <div
          style={{
            height: '100%',
            backgroundColor: config.color,
            borderRadius: '0 0 8px 8px',
            animation: `notificationProgress ${notification.duration}ms linear`,
            transformOrigin: 'left'
          }} />
        
        </div>
      }

      <style>
        {`
          @keyframes notificationProgress {
            from { transform: scaleX(1); }
            to { transform: scaleX(0); }
          }

          @keyframes slideInRight {
            from {
              transform: translateX(100%);
              opacity: 0;
            }
            to {
              transform: translateX(0);
              opacity: 1;
            }
          }

          @keyframes slideOutRight {
            from {
              transform: translateX(0);
              opacity: 1;
            }
            to {
              transform: translateX(100%);
              opacity: 0;
            }
          }
        `}
      </style>
    </div>);

};

// Контейнер уведомлений
export const NotificationContainer = ({
  notifications = [],
  onRemove,
  position = 'top-right',
  className = '',
  ...props
}) => {
  if (notifications.length === 0) return null;

  return (
    <div
      className={`notification-container ${className}`}
      style={{
        position: 'fixed',
        zIndex: 9999,
        pointerEvents: 'none',
        ...notificationConfig.positions[position]
      }}
      {...props}>
      
      {notifications.map((notification) =>
      <Notification
        key={notification.id}
        notification={notification}
        onRemove={onRemove}
        position={position}
        style={{ pointerEvents: 'auto' }} />

      )}
    </div>);

};

// Провайдер уведомлений
export const NotificationProvider = ({
  children,
  options = {},
  ...props
}) => {
  const notificationHook = useNotifications(options);

  return (
    <NotificationContext.Provider value={notificationHook} {...props}>
      {children}
      <NotificationContainer
        notifications={notificationHook.notifications}
        onRemove={notificationHook.removeNotification}
        position={options.position || 'top-right'} />
      
    </NotificationContext.Provider>);

};

// Контекст уведомлений
const NotificationContext = React.createContext();

// Хук для использования уведомлений в компонентах
export const useNotificationContext = () => {
  const context = React.useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotificationContext must be used within a NotificationProvider');
  }
  return context;
};

Notification.propTypes = {
  notification: PropTypes.object,
  onRemove: PropTypes.func,
  onAction: PropTypes.func,
  position: PropTypes.string,
  className: PropTypes.string
};

NotificationContainer.propTypes = {
  notifications: PropTypes.array,
  onRemove: PropTypes.func,
  position: PropTypes.string,
  className: PropTypes.string
};

NotificationProvider.propTypes = {
  children: PropTypes.node,
  options: PropTypes.object
};

export default useNotifications;
