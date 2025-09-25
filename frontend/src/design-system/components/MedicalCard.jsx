/**
 * Унифицированная медицинская карточка
 * Используется во всех панелях для отображения информации о пациентах, записях, услугах
 */

import React from 'react';
import Card from './Card';
import Badge from './Badge';
import Button from './Button';
import { medicalTheme, getDepartmentStyle, getPatientStatusStyle, getPriorityStyle } from '../theme/medical';
import { 
  User, 
  Calendar, 
  Clock, 
  MapPin, 
  Phone, 
  Mail,
  AlertCircle,
  CheckCircle,
  XCircle,
  Clock as ClockIcon,
  Heart,
  Activity
} from 'lucide-react';

const MedicalCard = ({
  // Основные данные
  title,
  subtitle,
  description,
  
  // Медицинская информация
  patient,
  appointment,
  department,
  doctor,
  services,
  
  // Статусы
  status,
  priority,
  paymentStatus,
  
  // Действия
  actions,
  onCardClick,
  
  // Стилизация
  variant = 'default', // default, compact, detailed
  showAvatar = true,
  showBadges = true,
  showActions = true,
  
  // Дополнительные опции
  className = '',
  style = {},
  ...props
}) => {
  // Определяем стили на основе отделения
  const departmentStyle = department ? getDepartmentStyle(department) : null;
  const statusStyle = status ? getPatientStatusStyle(status) : null;
  const priorityStyle = priority ? getPriorityStyle(priority) : null;
  
  // Иконки статусов
  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
      case 'paid':
      case 'confirmed':
        return <CheckCircle size={16} className="text-green-500" />;
      case 'cancelled':
      case 'failed':
      case 'noShow':
        return <XCircle size={16} className="text-red-500" />;
      case 'pending':
      case 'scheduled':
        return <ClockIcon size={16} className="text-yellow-500" />;
      case 'inProgress':
        return <Activity size={16} className="text-blue-500" />;
      default:
        return null;
    }
  };
  
  // Иконки отделений
  const getDepartmentIcon = (dept) => {
    const icons = {
      cardiology: '❤️',
      dermatology: '🧴',
      dentistry: '🦷',
      laboratory: '🔬',
      general: '🏥',
      emergency: '🚨'
    };
    return icons[dept] || icons.general;
  };
  
  // Базовые стили карточки
  const cardStyle = {
    background: departmentStyle?.background || 'white',
    borderLeft: departmentStyle?.accent ? `4px solid ${departmentStyle.accent}` : undefined,
    transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
    cursor: onCardClick ? 'pointer' : 'default',
    ...style
  };
  
  const handleCardClick = () => {
    if (onCardClick) {
      onCardClick({ patient, appointment, department, doctor });
    }
  };
  
  return (
    <Card 
      className={`medical-card ${variant} ${className}`}
      style={cardStyle}
      onClick={handleCardClick}
      hoverable={!!onCardClick}
      {...props}
    >
      {/* Заголовок карточки */}
      <div className="medical-card-header">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            {/* Аватар или иконка отделения */}
            {showAvatar && (
              <div className="medical-card-avatar">
                {patient?.avatar ? (
                  <img 
                    src={patient.avatar} 
                    alt={patient.name}
                    className="w-10 h-10 rounded-full object-cover"
                  />
                ) : (
                  <div 
                    className="w-10 h-10 rounded-full flex items-center justify-center text-lg"
                    style={{ 
                      background: departmentStyle?.accent || '#f3f4f6',
                      color: 'white'
                    }}
                  >
                    {department ? getDepartmentIcon(department) : <User size={20} />}
                  </div>
                )}
              </div>
            )}
            
            {/* Основная информация */}
            <div className="medical-card-info">
              <h3 className="font-semibold text-gray-900 text-sm">
                {title || patient?.name || 'Без названия'}
              </h3>
              {subtitle && (
                <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
              )}
            </div>
          </div>
          
          {/* Бейджи статусов */}
          {showBadges && (
            <div className="flex items-center space-x-2">
              {priority && priority !== 'normal' && (
                <Badge 
                  variant={priority === 'emergency' ? 'danger' : priority === 'urgent' ? 'warning' : 'info'}
                  size="sm"
                  className="flex items-center space-x-1"
                >
                  {priority === 'emergency' && <AlertCircle size={12} />}
                  <span className="capitalize">{priority}</span>
                </Badge>
              )}
              
              {status && (
                <Badge 
                  variant={
                    status === 'completed' || status === 'paid' || status === 'confirmed' ? 'success' :
                    status === 'cancelled' || status === 'failed' ? 'danger' :
                    status === 'pending' || status === 'scheduled' ? 'warning' : 'info'
                  }
                  size="sm"
                  className="flex items-center space-x-1"
                >
                  {getStatusIcon(status)}
                  <span className="capitalize">{status}</span>
                </Badge>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* Контент карточки */}
      <div className="medical-card-content mt-3">
        {/* Описание */}
        {description && (
          <p className="text-sm text-gray-600 mb-3">{description}</p>
        )}
        
        {/* Детали пациента */}
        {patient && variant !== 'compact' && (
          <div className="patient-details space-y-2 mb-3">
            {patient.phone && (
              <div className="flex items-center space-x-2 text-xs text-gray-500">
                <Phone size={12} />
                <span>{patient.phone}</span>
              </div>
            )}
            {patient.email && (
              <div className="flex items-center space-x-2 text-xs text-gray-500">
                <Mail size={12} />
                <span>{patient.email}</span>
              </div>
            )}
            {patient.address && (
              <div className="flex items-center space-x-2 text-xs text-gray-500">
                <MapPin size={12} />
                <span>{patient.address}</span>
              </div>
            )}
          </div>
        )}
        
        {/* Информация о записи */}
        {appointment && (
          <div className="appointment-details space-y-2 mb-3">
            {appointment.date && (
              <div className="flex items-center space-x-2 text-xs text-gray-600">
                <Calendar size={12} />
                <span>{new Date(appointment.date).toLocaleDateString('ru-RU')}</span>
              </div>
            )}
            {appointment.time && (
              <div className="flex items-center space-x-2 text-xs text-gray-600">
                <Clock size={12} />
                <span>{appointment.time}</span>
              </div>
            )}
            {doctor && (
              <div className="flex items-center space-x-2 text-xs text-gray-600">
                <User size={12} />
                <span>Врач: {doctor.name || doctor}</span>
              </div>
            )}
          </div>
        )}
        
        {/* Услуги */}
        {services && services.length > 0 && variant === 'detailed' && (
          <div className="services-list mb-3">
            <p className="text-xs font-medium text-gray-700 mb-2">Услуги:</p>
            <div className="space-y-1">
              {services.slice(0, 3).map((service, index) => (
                <div key={index} className="flex justify-between items-center text-xs">
                  <span className="text-gray-600">{service.name}</span>
                  {service.price && (
                    <span className="font-medium text-gray-900">
                      {service.price.toLocaleString()} сум
                    </span>
                  )}
                </div>
              ))}
              {services.length > 3 && (
                <p className="text-xs text-gray-500">
                  +{services.length - 3} услуг...
                </p>
              )}
            </div>
          </div>
        )}
        
        {/* Общая сумма */}
        {appointment?.totalAmount && (
          <div className="total-amount flex justify-between items-center py-2 border-t border-gray-100">
            <span className="text-sm font-medium text-gray-700">Итого:</span>
            <span className="text-sm font-bold text-gray-900">
              {appointment.totalAmount.toLocaleString()} сум
            </span>
          </div>
        )}
      </div>
      
      {/* Действия */}
      {showActions && actions && actions.length > 0 && (
        <div className="medical-card-actions mt-4 pt-3 border-t border-gray-100">
          <div className="flex space-x-2">
            {actions.map((action, index) => (
              <Button
                key={index}
                variant={action.variant || 'outline'}
                size="sm"
                onClick={action.onClick}
                disabled={action.disabled}
                className="flex-1"
              >
                {action.icon && <action.icon size={14} className="mr-1" />}
                {action.label}
              </Button>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
};

// Стили для компонента
const medicalCardStyles = `
  .medical-card {
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  }
  
  .medical-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
  }
  
  .medical-card.compact {
    padding: 12px;
  }
  
  .medical-card.detailed {
    padding: 20px;
  }
  
  .medical-card-header {
    margin-bottom: 8px;
  }
  
  .medical-card-content {
    font-size: 14px;
    line-height: 1.4;
  }
  
  .medical-card-actions {
    margin-top: 12px;
  }
  
  @media (max-width: 768px) {
    .medical-card {
      padding: 12px;
    }
    
    .medical-card-actions {
      flex-direction: column;
    }
    
    .medical-card-actions .flex {
      flex-direction: column;
      space-y: 8px;
    }
  }
`;

// Добавляем стили в документ
if (typeof document !== 'undefined') {
  const styleSheet = document.createElement('style');
  styleSheet.textContent = medicalCardStyles;
  document.head.appendChild(styleSheet);
}

export default MedicalCard;
