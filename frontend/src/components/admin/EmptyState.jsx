import React from 'react';
import { FileX, Users, Calendar, CreditCard, BarChart3, Settings } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

const EmptyState = ({ 
  type = 'default', 
  title, 
  description, 
  action, 
  icon: CustomIcon,
  className = '' 
}) => {
  const { theme, getColor, getSpacing, getFontSize } = useTheme();

  const iconMap = {
    users: Users,
    appointments: Calendar,
    payments: CreditCard,
    analytics: BarChart3,
    settings: Settings,
    default: FileX
  };

  const Icon = CustomIcon || iconMap[type] || iconMap.default;

  const containerStyle = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '300px',
    padding: getSpacing('xl'),
    textAlign: 'center',
    background: theme === 'light' 
      ? 'rgba(255, 255, 255, 0.9)' 
      : 'rgba(15, 23, 42, 0.9)',
    backdropFilter: 'blur(20px)',
    border: `1px solid ${theme === 'light' ? 'rgba(255, 255, 255, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderRadius: '20px',
    boxShadow: theme === 'light' 
      ? '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
      : '0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.1)'
  };

  const iconStyle = {
    width: '64px',
    height: '64px',
    color: getColor('gray', 400),
    marginBottom: getSpacing('lg')
  };

  const titleStyle = {
    fontSize: getFontSize('lg'),
    fontWeight: '600',
    color: 'var(--text-primary)',
    marginBottom: getSpacing('sm')
  };

  const descriptionStyle = {
    fontSize: getFontSize('md'),
    color: 'var(--text-secondary)',
    marginBottom: getSpacing('lg'),
    maxWidth: '400px',
    lineHeight: 1.6
  };

  const actionStyle = {
    display: 'flex',
    gap: getSpacing('md'),
    flexWrap: 'wrap',
    justifyContent: 'center'
  };

  const buttonStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('sm'),
    padding: `${getSpacing('sm')} ${getSpacing('lg')}`,
    background: getColor('primary', 500),
    color: 'white',
    border: 'none',
    borderRadius: '12px',
    fontSize: getFontSize('sm'),
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
    textDecoration: 'none'
  };

  const defaultMessages = {
    users: {
      title: 'Пользователи не найдены',
      description: 'В системе пока нет пользователей. Добавьте первого пользователя, чтобы начать работу.'
    },
    appointments: {
      title: 'Записи не найдены',
      description: 'На выбранную дату нет записей. Создайте новую запись или выберите другую дату.'
    },
    payments: {
      title: 'Платежи не найдены',
      description: 'За выбранный период платежей не найдено. Проверьте другие даты или создайте новый платеж.'
    },
    analytics: {
      title: 'Нет данных для анализа',
      description: 'Недостаточно данных для построения аналитики. Добавьте больше записей для получения статистики.'
    },
    settings: {
      title: 'Настройки не загружены',
      description: 'Не удалось загрузить настройки системы. Проверьте подключение к серверу.'
    },
    default: {
      title: 'Данные не найдены',
      description: 'По вашему запросу ничего не найдено. Попробуйте изменить параметры поиска.'
    }
  };

  const messages = defaultMessages[type] || defaultMessages.default;
  const finalTitle = title || messages.title;
  const finalDescription = description || messages.description;

  return (
    <div style={containerStyle} className={className}>
      <Icon style={iconStyle} />
      <h3 style={titleStyle}>{finalTitle}</h3>
      <p style={descriptionStyle}>{finalDescription}</p>
      {action && (
        <div style={actionStyle}>
          {action}
        </div>
      )}
    </div>
  );
};

export default EmptyState;
