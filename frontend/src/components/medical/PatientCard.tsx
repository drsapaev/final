
import PropTypes from 'prop-types';
import MedicalCard from './MedicalCard';
import Icon from '../Icon';
import { useTheme } from '../../contexts/ThemeContext';
import { useTranslation } from '../../i18n/useTranslation';

// === Domain types ===
// PatientCard displays a single patient as a tile. The shape covers both
// MediLabDemo's structured Patient objects and DentistPanelUnified's
// selectedPatient (which is a superset with visit_id, examinationData,
// etc. — those extra fields ride along via the index signature).

export interface PatientCardPatient {
  id?: string | number;
  name?: string;
  avatar?: string | null;
  patientId?: string | number;
  age?: string | number;
  gender?: string;
  lastVisit?: string;
  department?: string;
  status?: string;
  is_deleted?: boolean;
  [key: string]: unknown;
}

export interface PatientCardProps {
  /** Patient data to render. */
  patient: PatientCardPatient;
  /** Open patient details view. */
  onView?: (patient: PatientCardPatient) => void;
  /** Open edit form. */
  onEdit?: (patient: PatientCardPatient) => void;
  /** Hard-delete (used as fallback when onArchive is not provided). */
  onDelete?: (patient: PatientCardPatient) => void;
  /** Soft-delete (archive) handler — preferred over onDelete. */
  onArchive?: (patient: PatientCardPatient) => void;
  /** Restore an archived patient. */
  onRestore?: (patient: PatientCardPatient) => void;
  /** Save handler (used by DentistPanelUnified modal flow). */
  onSave?: (updatedPatient: PatientCardPatient) => void;
  /** Close handler (used by DentistPanelUnified modal flow). */
  onClose?: () => void;
  /** Extra CSS class. */
  className?: string;
  /** Pass-through props to underlying MedicalCard. */
  [key: string]: unknown;
}

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
}: PatientCardProps) => {
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

  const getStatusColor = (status: string | undefined) => {
    if (is_deleted) return 'var(--mac-text-tertiary)';  // Gray for archived
    switch (status) {
      case 'active': return 'var(--mac-success)';
      case 'inactive': return 'var(--mac-text-secondary)';
      case 'urgent': return 'var(--mac-error)';
      case 'pending': return 'var(--mac-warning)';
      default: return 'var(--mac-text-secondary)';
    }
  };

  const getGenderIcon = (gender: string | undefined) => {
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
            background: 'var(--mac-error-bg)',
            color: 'var(--mac-error)',
            padding: '4px 12px',
            borderRadius: 'var(--mac-radius-lg)',
            fontSize: 'var(--mac-font-size-xs)',
            fontWeight: 'var(--mac-font-weight-medium)',
            marginBottom: 'var(--mac-spacing-3)',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
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
              backgroundColor: avatar ? 'transparent' : (is_deleted ? 'var(--mac-text-tertiary)' : 'var(--mac-accent-blue)'),
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
              style={{ color: isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-text-primary)' }}
            >
              {name}
            </h3>
            <p
              className="text-sm text-gray-500 truncate"
              style={{ color: isDark ? 'var(--mac-text-tertiary)' : 'var(--mac-text-secondary)' }}
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
              <span style={{ color: isDark ? 'var(--mac-border)' : 'var(--mac-text-primary)' }}>
                {age} {getGenderIcon(gender)}
              </span>
            </div>
          )}

          {lastVisit && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-gray-500">Last visit:</span>
              <span style={{ color: isDark ? 'var(--mac-border)' : 'var(--mac-text-primary)' }}>
                {lastVisit}
              </span>
            </div>
          )}

          {department && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-gray-500">Dept:</span>
              <span style={{ color: isDark ? 'var(--mac-border)' : 'var(--mac-text-primary)' }}>
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

