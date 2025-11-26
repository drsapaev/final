import React from 'react';
import ModernButton from './ModernButton';
import {
  Heart,
  Stethoscope,
  Pill,
  TestTube,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  UserCheck,
  FileText,
  Activity,
  Zap
} from 'lucide-react';
import './MedicalButton.css';

/**
 * MedicalButton - специализированная кнопка для медицинских задач
 * Предоставляет семантические иконки и состояния для медицинских действий
 */
const MedicalButton = ({
  action, // 'diagnose', 'treat', 'emergency', 'approve', 'reject', etc.
  department, // 'cardiology', 'dermatology', 'dentistry', 'laboratory'
  priority = 'normal', // 'low', 'normal', 'high', 'urgent', 'critical'
  status, // 'active', 'inactive', 'loading', 'success', 'error'
  children,
  className = '',
  ...props
}) => {
  // Получение иконки для действия
  const getActionIcon = () => {
    const iconMap = {
      diagnose: Stethoscope,
      treat: Pill,
      prescribe: FileText,
      emergency: AlertTriangle,
      approve: CheckCircle,
      reject: XCircle,
      monitor: Activity,
      examine: UserCheck,
      test: TestTube,
      schedule: Clock,
      urgent: Zap,
      heart: Heart
    };

    return iconMap[action] || null;
  };

  // Получение варианта кнопки на основе действия
  const getVariantFromAction = () => {
    const variantMap = {
      diagnose: 'diagnose',
      treat: 'treat',
      prescribe: 'treat',
      emergency: 'emergency',
      urgent: 'emergency',
      approve: 'approve',
      reject: 'reject',
      monitor: 'info',
      examine: 'diagnose',
      test: 'laboratory',
      schedule: 'info'
    };

    return variantMap[action] || variantMap[department] || 'primary';
  };

  // Получение варианта на основе отдела
  const getVariantFromDepartment = () => {
    return department || 'primary';
  };

  // Определение варианта кнопки
  const variant = action ? getVariantFromAction() : getVariantFromDepartment();

  // Классы приоритета
  const priorityClasses = {
    low: 'priority-low',
    normal: 'priority-normal',
    high: 'priority-high',
    urgent: 'priority-urgent',
    critical: 'priority-critical'
  };

  // Классы статуса
  const statusClasses = {
    active: 'status-active',
    inactive: 'status-inactive',
    loading: 'status-loading',
    success: 'status-success',
    error: 'status-error'
  };

  // Комбинированные классы
  const combinedClasses = [
    'medical-button',
    priority && `medical-button-${priorityClasses[priority]}`,
    status && `medical-button-${statusClasses[status]}`,
    className
  ].filter(Boolean).join(' ');

  // Автоматическая иконка если не указана
  const autoIcon = props.icon || getActionIcon();

  // Priority-based props
  const getPriorityProps = () => {
    switch (priority) {
      case 'urgent':
      case 'critical':
        return {
          'aria-live': 'assertive',
          'aria-atomic': 'true'
        };
      default:
        return {};
    }
  };

  return (
    <ModernButton
      variant={variant}
      className={combinedClasses}
      icon={autoIcon}
      {...getPriorityProps()}
      {...props}
    >
      {children}
    </ModernButton>
  );
};

/**
 * Быстрые конструкторы для распространенных медицинских действий
 */
export const EmergencyButton = (props) => (
  <MedicalButton action="emergency" priority="critical" {...props} />
);

export const DiagnoseButton = (props) => (
  <MedicalButton action="diagnose" {...props} />
);

export const TreatButton = (props) => (
  <MedicalButton action="treat" {...props} />
);

export const ApproveButton = (props) => (
  <MedicalButton action="approve" {...props} />
);

export const RejectButton = (props) => (
  <MedicalButton action="reject" {...props} />
);

export const CardiologyButton = (props) => (
  <MedicalButton department="cardiology" {...props} />
);

export const LabButton = (props) => (
  <MedicalButton department="laboratory" {...props} />
);

export default MedicalButton;
