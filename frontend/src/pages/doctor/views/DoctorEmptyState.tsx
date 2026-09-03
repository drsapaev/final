import type { ReactNode } from 'react';

/**
 * PR-UI-15-2: renderEmptyState helper extracted verbatim from
 * pages/DoctorPanel.tsx as a component (registrar/cashier precedent).
 */
export default function DoctorEmptyState({
  icon: Icon,
  title,
  description,
  tone = 'default',
  action = null,
}: {
  icon: React.ComponentType<{ size?: number | string; className?: string }>;
  title: ReactNode;
  description?: ReactNode;
  tone?: string;
  action?: ReactNode;
}) {
  return (
    <div className="doctor-empty" data-tone={tone}>
      <Icon size={48} className="doctor-empty-icon" />
      <div className="doctor-empty-title">
        {title}
      </div>
      {description &&
      <div className="doctor-empty-text">
          {description}
        </div>
      }
      {action &&
      <div className="doctor-empty-action">
          {action}
        </div>
      }
    </div>
  );
}
