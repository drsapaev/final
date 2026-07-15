import PropTypes from 'prop-types';
import { Icon } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

/**
 * L-H-4 fix: PanelEmptyState выделен в отдельный файл.
 *
 * L-L-1 fix (bonus): lucide-direct заменён на macos <Icon> для консистентности.
 *
 * Empty-state renderer для PatientPanel. Используется когда:
 *   - initData отсутствует (Mini App не открыт)
 *   - данные грузятся
 *   - данные не найдены
 *   - ошибка загрузки
 *
 * L-H-5 fix: добавлен optional `variant` prop — 'empty' | 'loading' | 'error'.
 * 'loading' добавляет aria-busy + skeleton-подобный shimmer.
 */
function PanelEmptyState({ icon, title, description, variant = 'empty' }) {
  const { t } = useTranslation();
  const iconSize = 24;
  return (
    <div
      className={`pp-empty-state pp-empty-state--${variant}`}
      role={variant === 'error' ? 'alert' : 'status'}
      aria-live={variant === 'loading' ? 'polite' : undefined}
      aria-busy={variant === 'loading' ? 'true' : undefined}
    >
      <Icon name={icon} size={iconSize} className="pp-empty-state-icon" />
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

PanelEmptyState.propTypes = {
  icon: PropTypes.string.isRequired,
  title: PropTypes.string.isRequired,
  description: PropTypes.string,
  variant: PropTypes.oneOf(['empty', 'loading', 'error']),
};

export default PanelEmptyState;
