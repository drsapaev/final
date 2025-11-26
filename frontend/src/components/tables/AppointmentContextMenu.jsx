import React, { useState, useRef, useEffect } from 'react';
import { 
  User, 
  Calendar, 
  CreditCard, 
  Printer, 
  X, 
  CheckCircle, 
  Clock,
  FileText,
  Phone,
  Edit,
  Eye
} from 'lucide-react';

const AppointmentContextMenu = ({ 
  row, 
  position, 
  onClose, 
  onAction,
  theme = 'light' 
}) => {
  const menuRef = useRef(null);
  const [isVisible, setIsVisible] = useState(false);

  const isDark = theme === 'dark';
  const colors = {
    bg: isDark ? '#1f2937' : '#ffffff',
    border: isDark ? '#4b5563' : '#e5e7eb',
    text: isDark ? '#f9fafb' : '#111827',
    textSecondary: isDark ? '#d1d5db' : '#6b7280',
    hover: isDark ? '#374151' : '#f3f4f6',
    accent: '#3b82f6',
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444'
  };

  useEffect(() => {
    setIsVisible(true);
    
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        onClose();
      }
    };

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  const menuItems = [
    {
      id: 'view',
      label: 'Просмотр',
      icon: Eye,
      color: colors.text,
      visible: true
    },
    {
      id: 'edit',
      label: 'Редактировать',
      icon: Edit,
      color: colors.text,
      visible: true
    },
    { type: 'divider' },
    {
      id: 'in_cabinet',
      label: 'В кабинет',
      icon: User,
      color: colors.accent,
      visible: row.status === 'confirmed' || row.status === 'queued'
    },
    {
      id: 'call',
      label: 'Вызвать',
      icon: Clock,
      color: colors.success,
      visible: row.status === 'queued'
    },
    {
      id: 'complete',
      label: 'Завершить',
      icon: CheckCircle,
      color: colors.success,
      visible: row.status === 'in_cabinet'
    },
    { type: 'divider' },
    {
      id: 'payment',
      label: 'Оплата',
      icon: CreditCard,
      color: colors.success,
      visible: (() => {
        const s = (row.status || '').toLowerCase();
        const ps = (row.payment_status || '').toLowerCase();
        return s !== 'paid' && ps !== 'paid' && (s === 'paid_pending' || !ps);
      })()
    },
    {
      id: 'print',
      label: 'Печать талона',
      icon: Printer,
      color: colors.accent,
      visible: (row.payment_status === 'paid') || (row.status === 'queued')
    },
    { type: 'divider' },
    {
      id: 'reschedule',
      label: 'Перенести',
      icon: Calendar,
      color: colors.warning,
      visible: row.status !== 'done' && row.status !== 'in_cabinet'
    },
    {
      id: 'cancel',
      label: 'Отменить',
      icon: X,
      color: colors.error,
      visible: row.status !== 'canceled' && row.status !== 'done'
    },
    { type: 'divider' },
    {
      id: 'call_patient',
      label: 'Позвонить',
      icon: Phone,
      color: colors.text,
      visible: !!row.patient_phone
    }
  ].filter(item => item.type === 'divider' || item.visible);

  // Вычисляем правильную позицию меню с учетом границ экрана
  const getAdjustedPosition = () => {
    const menuWidth = 220;
    const menuHeight = menuItems.length * 40; // примерная высота
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    
    let adjustedX = position.x;
    let adjustedY = position.y;
    
    // Проверяем, не выходит ли меню за правую границу экрана
    if (position.x + menuWidth > viewportWidth) {
      adjustedX = position.x - menuWidth;
    }
    
    // Проверяем, не выходит ли меню за нижнюю границу экрана
    if (position.y + menuHeight > viewportHeight) {
      adjustedY = position.y - menuHeight;
    }
    
    // Убеждаемся, что меню не выходит за левую и верхнюю границы
    adjustedX = Math.max(10, adjustedX);
    adjustedY = Math.max(10, adjustedY);
    
    return { x: adjustedX, y: adjustedY };
  };

  const adjustedPosition = getAdjustedPosition();

  const handleItemClick = (itemId) => {
    onAction(itemId, row);
    onClose();
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        zIndex: 1000,
        pointerEvents: 'auto'
      }}
    >
      <div
        ref={menuRef}
        className="context-menu"
        style={{
          position: 'absolute',
          top: adjustedPosition.y,
          left: adjustedPosition.x,
          backgroundColor: colors.bg,
          border: `1px solid ${colors.border}`,
          borderRadius: '8px',
          boxShadow: '0 10px 25px rgba(0, 0, 0, 0.15)',
          minWidth: '180px',
          maxWidth: '220px',
          padding: '8px 0',
          transform: isVisible ? 'scale(1)' : 'scale(0.95)',
          opacity: isVisible ? 1 : 0,
          transition: 'all 0.15s ease-out',
          transformOrigin: 'top left'
        }}
      >
        {menuItems.map((item, index) => {
          if (item.type === 'divider') {
            return (
              <div
                key={`divider-${index}`}
                style={{
                  height: '1px',
                  backgroundColor: colors.border,
                  margin: '4px 0'
                }}
              />
            );
          }

          const Icon = item.icon;
          
          return (
            <button
              key={item.id}
              onClick={() => handleItemClick(item.id)}
              style={{
                width: '100%',
                padding: '8px 16px',
                border: 'none',
                backgroundColor: 'transparent',
                color: item.color,
                fontSize: '14px',
                textAlign: 'left',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                transition: 'background-color 0.15s ease'
              }}
              onMouseEnter={(e) => {
                e.target.style.backgroundColor = colors.hover;
              }}
              onMouseLeave={(e) => {
                e.target.style.backgroundColor = 'transparent';
              }}
            >
              <Icon size={16} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default AppointmentContextMenu;

