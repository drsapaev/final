import PropTypes from 'prop-types';
import MedicalCard from './MedicalCard';
import Icon from '../Icon';
import { useTheme } from '../../contexts/ThemeContext';

/**
 * Карточка пациента в стиле MediLab
 */
const PatientCard = ({
  patient,
  onView,
  onEdit,
  onDelete,
  onArchive,  // Soft-delete handler
  onRestore,  // Restore handler
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
    status = 'active',
    is_deleted = false  // Soft-delete flag
  } = patient;

  const getStatusColor = (status) => {
    if (is_deleted) return '#9ca3af';  // Gray for archived
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
      className={`patient-card ${className} ${is_deleted ? 'archived' : ''}`}
      hover={true}
      padding="medium"
      style={is_deleted ? { opacity: 0.7 } : {}}
      {...props}
    >
      <div className="flex flex-col h-full">
        {/* Archived Badge */}
        {is_deleted && (
          <div style={{
            background: '#fee2e2',
            color: '#dc2626',
            padding: '4px 12px',
            borderRadius: '12px',
            fontSize: '12px',
            fontWeight: '500',
            marginBottom: '12px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            alignSelf: 'flex-start'
          }}>
            📦 Архивирован
          </div>
        )}

        {/* Аватар и основная информация */}
        <div className="flex items-center gap-4 mb-4">
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center text-white text-xl font-semibold"
            style={{
              backgroundColor: avatar ? 'transparent' : (is_deleted ? '#9ca3af' : '#3b82f6'),
              backgroundImage: avatar ? `url(${avatar})` : 'none',
              backgroundSize: 'cover',
              backgroundPosition: 'center'
            }}
          >
            {!avatar && <Icon name="User" size={24} />}
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
            title={is_deleted ? 'Архивирован' : status}
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
            <Icon name="Eye" size={16} />
            View
          </button>

          {!is_deleted && (
            <>
              <button
                onClick={() => onEdit?.(patient)}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors text-sm interactive-element hover-lift ripple-effect action-button-hover focus-ring"
                title="Edit patient"
              >
                <Icon name="Edit" size={16} />
                Edit
              </button>

              <button
                onClick={() => (onArchive || onDelete)?.(patient)}
                className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-orange-500 text-white rounded-md hover:bg-orange-600 transition-colors text-sm interactive-element hover-lift ripple-effect action-button-hover focus-ring"
                title="Архивировать пациента"
              >
                <Icon name="Archive" size={16} />
                Архив
              </button>
            </>
          )}

          {is_deleted && onRestore && (
            <button
              onClick={() => onRestore?.(patient)}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-emerald-500 text-white rounded-md hover:bg-emerald-600 transition-colors text-sm interactive-element hover-lift ripple-effect action-button-hover focus-ring"
              title="Восстановить пациента"
            >
              <Icon name="RotateCcw" size={16} />
              Восстановить
            </button>
          )}
        </div>
      </div>
    </MedicalCard>
  );
};

PatientCard.propTypes = {
  patient: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    name: PropTypes.string,
    avatar: PropTypes.string,
    patientId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    age: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    gender: PropTypes.string,
    lastVisit: PropTypes.string,
    department: PropTypes.string,
    status: PropTypes.string,
    is_deleted: PropTypes.bool
  }),
  onView: PropTypes.func,
  onEdit: PropTypes.func,
  onDelete: PropTypes.func,
  onArchive: PropTypes.func,
  onRestore: PropTypes.func,
  className: PropTypes.string
};

export default PatientCard;

