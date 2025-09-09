import React from 'react';
import { Eye, Edit, Trash2, User } from 'lucide-react';
import MedicalCard from './MedicalCard';
import { useTheme } from '../../contexts/ThemeContext';

/**
 * Карточка пациента в стиле MediLab
 */
const PatientCard = ({ 
  patient, 
  onView, 
  onEdit, 
  onDelete,
  className = '',
  ...props 
}) => {
  const { isDark } = useTheme();

  const {
    id,
    name = 'Unknown Patient',
    avatar,
    patientId,
    age,
    gender,
    lastVisit,
    department,
    status = 'active'
  } = patient;

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return '#10b981';
      case 'inactive': return '#6b7280';
      case 'urgent': return '#ef4444';
      case 'pending': return '#f59e0b';
      default: return '#6b7280';
    }
  };

  const getGenderIcon = (gender) => {
    return gender === 'M' ? '👨' : gender === 'F' ? '👩' : '👤';
  };

  return (
    <MedicalCard 
      className={`patient-card ${className}`}
      hover={true}
      padding="medium"
      {...props}
    >
      <div className="flex flex-col h-full">
        {/* Аватар и основная информация */}
        <div className="flex items-center gap-4 mb-4">
          <div 
            className="w-16 h-16 rounded-full flex items-center justify-center text-white text-xl font-semibold"
            style={{
              backgroundColor: avatar ? 'transparent' : '#3b82f6',
              backgroundImage: avatar ? `url(${avatar})` : 'none',
              backgroundSize: 'cover',
              backgroundPosition: 'center'
            }}
          >
            {!avatar && <User size={24} />}
          </div>
          
          <div className="flex-1 min-w-0">
            <h3 
              className="text-lg font-semibold truncate"
              style={{ color: isDark ? '#f8fafc' : '#1e293b' }}
            >
              {name}
            </h3>
            <p 
              className="text-sm text-gray-500 truncate"
              style={{ color: isDark ? '#94a3b8' : '#64748b' }}
            >
              ID: {patientId || id}
            </p>
          </div>

          {/* Статус */}
          <div 
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: getStatusColor(status) }}
            title={status}
          />
        </div>

        {/* Дополнительная информация */}
        <div className="space-y-2 mb-4">
          {age && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-gray-500">Age:</span>
              <span style={{ color: isDark ? '#cbd5e1' : '#374151' }}>
                {age} {getGenderIcon(gender)}
              </span>
            </div>
          )}
          
          {lastVisit && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-gray-500">Last visit:</span>
              <span style={{ color: isDark ? '#cbd5e1' : '#374151' }}>
                {lastVisit}
              </span>
            </div>
          )}
          
          {department && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-gray-500">Dept:</span>
              <span style={{ color: isDark ? '#cbd5e1' : '#374151' }}>
                {department}
              </span>
            </div>
          )}
        </div>

        {/* Действия */}
        <div className="flex gap-2 mt-auto">
          <button
            onClick={() => onView?.(patient)}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-green-500 text-white rounded-md hover:bg-green-600 transition-colors text-sm interactive-element hover-lift ripple-effect action-button-hover focus-ring"
            title="View details"
          >
            <Eye size={16} />
            View
          </button>
          
          <button
            onClick={() => onEdit?.(patient)}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors text-sm interactive-element hover-lift ripple-effect action-button-hover focus-ring"
            title="Edit patient"
          >
            <Edit size={16} />
            Edit
          </button>
          
          <button
            onClick={() => onDelete?.(patient)}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-red-500 text-white rounded-md hover:bg-red-600 transition-colors text-sm interactive-element hover-lift ripple-effect action-button-hover focus-ring"
            title="Delete patient"
          >
            <Trash2 size={16} />
            Delete
          </button>
        </div>
      </div>
    </MedicalCard>
  );
};

export default PatientCard;
