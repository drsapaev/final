import { useTranslation } from '../../i18n/useTranslation';
import { useEffect, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import {
  User,
  Calendar,
  CreditCard,
  Printer,
  X,
  CheckCircle,
  Clock,

  Phone,
  Edit,
  Eye,
  AlertTriangle } from
'lucide-react';

const ACTION_ALIASES = {
  in_cabinet: ['in_cabinet', 'in-cabinet'],
  call: ['call', 'start_visit', 'start-visit'],
  complete: ['complete', 'complete_visit', 'complete-visit'],
  payment: ['payment', 'mark_paid', 'mark-paid'],
  print: ['print', 'print_ticket', 'print-ticket'],
  reschedule: ['reschedule', 'move', 'transfer'],
  cancel: ['cancel', 'cancel_visit', 'cancel-visit']
};

const hasBackendAction = (row, action, flagName) => {
  if (row && flagName && Object.prototype.hasOwnProperty.call(row, flagName)) {
    return Boolean(row[flagName]);
  }

  if (!Array.isArray(row?.available_actions)) {
    return false;
  }

  const actions = new Set(row.available_actions.map((item) => String(item).trim().toLowerCase()));
  const aliases = ACTION_ALIASES[action] || [action];
  return aliases.some((alias) => actions.has(alias));
};

const AppointmentContextMenu = ({
  row,
  position,
  onClose,
  onAction,
  theme = 'light',
  isDoctorView = false
}) => {
  const menuRef = useRef(null);
  const [isVisible, setIsVisible] = useState(false);

  const isDark = theme === 'dark';
  const colors = {
    bg: isDark ? 'var(--mac-text-primary)' : 'var(--mac-bg-primary)',
    border: isDark ? '#4b5563' : 'var(--mac-border)',
    text: isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-text-primary)',
    textSecondary: isDark ? 'var(--mac-border)' : 'var(--mac-text-secondary)',
    hover: isDark ? 'var(--mac-text-primary)' : 'var(--mac-bg-secondary)',
    accent: 'var(--mac-accent-blue)',
    success: 'var(--mac-success)',
    warning: 'var(--mac-warning)',
    error: 'var(--mac-error)'
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
    visible: hasBackendAction(row, 'in_cabinet', 'can_start_visit')
  },
  {
    id: 'call',
    label: 'Вызвать',
    icon: Clock,
    color: colors.success,
    visible: hasBackendAction(row, 'call', 'can_start_visit')
  },
  {
    id: 'complete',
    label: 'Завершить',
    icon: CheckCircle,
    color: colors.success,
    visible: hasBackendAction(row, 'complete', 'can_complete')
  },
  { type: 'divider' },
  {
    id: 'payment',
    label: 'Оплата',
    icon: CreditCard,
    color: colors.success,
    visible: hasBackendAction(row, 'payment', 'can_mark_paid')
  },
  {
    id: 'print',
    label: 'Печать талона',
    icon: Printer,
    color: colors.accent,
    visible: hasBackendAction(row, 'print', 'can_print_ticket')
  },
  { type: 'divider' },
  {
    id: 'reschedule',
    label: 'Перенести',
    icon: Calendar,
    color: colors.warning,
    visible: hasBackendAction(row, 'reschedule', 'can_reschedule')
  },
  {
    id: 'cancel',
    label: 'Отменить',
    icon: X,
    color: colors.error,
    visible: hasBackendAction(row, 'cancel', 'can_cancel')
  },
  { type: 'divider' },
  {
    id: 'call_patient',
    label: 'Позвонить',
    icon: Phone,
    color: colors.text,
    visible: !!row.patient_phone
  },
  { type: 'divider' },
  {
    id: 'force_majeure',
    label: 'Форс-мажор',
    // UX Audit R-2.7: tooltip объясняет, что произойдёт при клике.
    // Без tooltip «Форс-мажор» — внутренний термин, неинтуитивный для регистратора.
    title: t('final.emergency_actions_title'),
    icon: AlertTriangle,
    color: colors.warning,
    visible: !isDoctorView
  },
  {
    id: 'schedule_next',
    label: 'Назначить следующий визит',
    icon: Calendar,
    color: colors.accent,
    visible: !isDoctorView
  }].
  filter((item) => item.type === 'divider' || item.visible);

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
    onAction?.(itemId, row);
    onClose?.();
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
      }}>
      
      <div
        ref={menuRef}
        className="context-menu"
        style={{
          position: 'absolute',
          top: adjustedPosition.y,
          left: adjustedPosition.x,
          backgroundColor: colors.bg,
          border: `1px solid ${colors.border}`,
          borderRadius: 'var(--mac-radius-md)',
          boxShadow: 'var(--mac-shadow-lg)',
          minWidth: '180px',
          maxWidth: '220px',
          padding: 'var(--mac-spacing-2) 0',
          transform: isVisible ? 'scale(1)' : 'scale(0.95)',
          opacity: isVisible ? 1 : 0,
          transition: 'all 0.15s ease-out',
          transformOrigin: 'top left'
        }}>
        
        {menuItems.map((item, index) => {
          if (item.type === 'divider') {
            return (
              <div
                key={`divider-${index}`}
                style={{
                  height: '1px',
                  backgroundColor: colors.border,
                  margin: '4px 0'
                }} />);


          }

          const Icon = item.icon;

          return (
            <button
              key={item.id}
              onClick={() => handleItemClick(item.id)}
              style={{
                width: '100%',
                padding: 'var(--mac-spacing-2) var(--mac-spacing-4)',
                border: 'none',
                backgroundColor: 'transparent',
                color: item.color,
                fontSize: 'var(--mac-font-size-base)',
                textAlign: 'left',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--mac-spacing-3)',
                transition: 'background-color 0.15s ease'
              }}
              onMouseEnter={(e) => {
                e.target.style.backgroundColor = colors.hover;
              }}
              onMouseLeave={(e) => {
                e.target.style.backgroundColor = 'transparent';
              }}
              title={item.title}>
              
              <Icon size={16} />
              <span>{item.label}</span>
            </button>);

        })}
      </div>
    </div>);

};

AppointmentContextMenu.propTypes = {
  row: PropTypes.object,
  position: PropTypes.shape({
    x: PropTypes.number,
    y: PropTypes.number
  }),
  onClose: PropTypes.func,
  onAction: PropTypes.func,
  theme: PropTypes.string
};

export default AppointmentContextMenu;
