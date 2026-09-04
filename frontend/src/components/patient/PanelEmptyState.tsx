import { useTranslation } from '../../i18n/useTranslation';
import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

interface PanelEmptyStateProps {
  icon?: LucideIcon;
  title: ReactNode;
  description?: ReactNode;
  variant?: 'empty' | 'loading' | 'error';
}

function PanelEmptyState({ icon: EmptyIcon, title, description, variant = 'empty' }: PanelEmptyStateProps) {
  const { t } = useTranslation();
  void t;
  const iconSize = 24;
  return (
    <div
      className={`pp-empty-state pp-empty-state--${variant}`}
      role={variant === 'error' ? 'alert' : 'status'}
      aria-live={variant === 'loading' ? 'polite' : undefined}
      aria-busy={variant === 'loading' ? 'true' : undefined}
    >
      {EmptyIcon && <EmptyIcon size={iconSize} className="pp-empty-state-icon" aria-hidden="true" />}
      <div className="pp-empty-state-title">{title}</div>
      {description && <p className="pp-empty-state-description">{description}</p>}
      {variant === 'loading' && (
        <div className="pp-empty-state-skeleton" aria-hidden="true">
          <div className="pp-skeleton-line pp-skeleton-line--w60" />
          <div className="pp-skeleton-line pp-skeleton-line--w80" />
          <div className="pp-skeleton-line pp-skeleton-line--w40" />
        </div>
      )}
    </div>
  );
}


export default PanelEmptyState;
