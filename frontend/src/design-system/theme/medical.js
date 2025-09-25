/**
 * Медицинская тема для клиники
 * Специализированные цвета и стили для медицинского интерфейса
 */

export const medicalTheme = {
  // Медицинские цвета
  colors: {
    // Основная медицинская палитра
    medical: {
      50: '#f0fff4',   // Очень светло-зеленый
      100: '#dcfce7',  // Светло-зеленый
      200: '#bbf7d0',  // Зеленый для успеха
      300: '#86efac',  // Средний зеленый
      400: '#4ade80',  // Яркий зеленый
      500: '#22c55e',  // Основной медицинский зеленый
      600: '#16a34a',  // Темно-зеленый
      700: '#15803d',  // Очень темно-зеленый
      800: '#166534',  // Глубокий зеленый
      900: '#14532d'   // Самый темный зеленый
    },
    
    // Статусы пациентов
    patient: {
      healthy: '#22c55e',     // Здоров
      sick: '#ef4444',        // Болен
      recovery: '#f59e0b',    // Выздоравливает
      critical: '#dc2626',    // Критическое состояние
      stable: '#3b82f6'       // Стабильное состояние
    },
    
    // Отделения клиники
    departments: {
      cardiology: '#dc2626',    // Красный - кардиология
      dermatology: '#f59e0b',   // Оранжевый - дерматология
      dentistry: '#3b82f6',     // Синий - стоматология
      laboratory: '#8b5cf6',    // Фиолетовый - лаборатория
      general: '#64748b',       // Серый - общее
      emergency: '#dc2626',     // Красный - экстренная помощь
      pediatrics: '#06b6d4',    // Голубой - педиатрия
      surgery: '#1e40af',       // Темно-синий - хирургия
      radiology: '#7c3aed',     // Фиолетовый - рентген
      pharmacy: '#059669'       // Зеленый - аптека
    },
    
    // Приоритеты и срочность
    priority: {
      low: '#64748b',      // Низкий приоритет
      normal: '#3b82f6',   // Обычный
      high: '#f59e0b',     // Высокий
      urgent: '#ef4444',   // Срочный
      emergency: '#dc2626' // Экстренный
    },
    
    // Статусы записей
    appointment: {
      scheduled: '#3b82f6',    // Запланирована
      confirmed: '#22c55e',    // Подтверждена
      inProgress: '#f59e0b',   // В процессе
      completed: '#22c55e',    // Завершена
      cancelled: '#64748b',    // Отменена
      noShow: '#ef4444',       // Не явился
      rescheduled: '#8b5cf6'   // Перенесена
    },
    
    // Платежи
    payment: {
      pending: '#f59e0b',    // Ожидает оплаты
      paid: '#22c55e',       // Оплачено
      failed: '#ef4444',     // Ошибка оплаты
      refunded: '#64748b',   // Возвращено
      partial: '#8b5cf6'     // Частичная оплата
    }
  },
  
  // Медицинские градиенты
  gradients: {
    medical: 'linear-gradient(135deg, #f0fff4 0%, #dcfce7 100%)',
    cardiology: 'linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)',
    dermatology: 'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)',
    dentistry: 'linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)',
    laboratory: 'linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)',
    emergency: 'linear-gradient(135deg, #fef2f2 0%, #fecaca 100%)'
  },
  
  // Тени для медицинских карточек
  shadows: {
    card: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    cardHover: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    modal: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
    tooltip: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
  },
  
  // Анимации для медицинского интерфейса
  animations: {
    heartbeat: {
      keyframes: `
        @keyframes heartbeat {
          0% { transform: scale(1); }
          14% { transform: scale(1.1); }
          28% { transform: scale(1); }
          42% { transform: scale(1.1); }
          70% { transform: scale(1); }
        }
      `,
      duration: '1.5s',
      timing: 'ease-in-out',
      iteration: 'infinite'
    },
    
    pulse: {
      keyframes: `
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `,
      duration: '2s',
      timing: 'cubic-bezier(0.4, 0, 0.6, 1)',
      iteration: 'infinite'
    },
    
    slideIn: {
      keyframes: `
        @keyframes slideIn {
          from { transform: translateX(-100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `,
      duration: '0.3s',
      timing: 'cubic-bezier(0.4, 0, 0.2, 1)'
    },
    
    fadeIn: {
      keyframes: `
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `,
      duration: '0.2s',
      timing: 'cubic-bezier(0.4, 0, 0.2, 1)'
    }
  },
  
  // Специальные стили для медицинских элементов
  medical: {
    // Стили для статусов пациентов
    patientStatus: {
      healthy: {
        background: '#f0fdf4',
        color: '#166534',
        border: '1px solid #bbf7d0'
      },
      sick: {
        background: '#fef2f2',
        color: '#991b1b',
        border: '1px solid #fecaca'
      },
      recovery: {
        background: '#fffbeb',
        color: '#92400e',
        border: '1px solid #fde68a'
      }
    },
    
    // Стили для приоритетов
    priority: {
      emergency: {
        background: '#fef2f2',
        color: '#991b1b',
        border: '2px solid #dc2626',
        animation: 'pulse 1s infinite'
      },
      urgent: {
        background: '#fffbeb',
        color: '#92400e',
        border: '1px solid #f59e0b'
      },
      normal: {
        background: '#eff6ff',
        color: '#1e40af',
        border: '1px solid #93c5fd'
      }
    },
    
    // Стили для отделений
    department: {
      cardiology: {
        background: 'linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)',
        accent: '#dc2626',
        icon: '❤️'
      },
      dermatology: {
        background: 'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)',
        accent: '#f59e0b',
        icon: '🧴'
      },
      dentistry: {
        background: 'linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)',
        accent: '#3b82f6',
        icon: '🦷'
      },
      laboratory: {
        background: 'linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)',
        accent: '#8b5cf6',
        icon: '🔬'
      }
    }
  }
};

// Функции для работы с медицинской темой
export const getMedicalColor = (category, shade = 500) => {
  return medicalTheme.colors[category]?.[shade] || medicalTheme.colors.medical[shade];
};

export const getDepartmentStyle = (department) => {
  return medicalTheme.medical.department[department] || medicalTheme.medical.department.general;
};

export const getPatientStatusStyle = (status) => {
  return medicalTheme.medical.patientStatus[status] || medicalTheme.medical.patientStatus.normal;
};

export const getPriorityStyle = (priority) => {
  return medicalTheme.medical.priority[priority] || medicalTheme.medical.priority.normal;
};
