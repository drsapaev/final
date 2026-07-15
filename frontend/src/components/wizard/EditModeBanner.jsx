/**
 * EditModeBanner — extracted from AppointmentWizardV2.jsx (PR-45 / High-15).
 *
 * Shows a banner when the wizard is in edit mode, with a QR/Desk source badge.
 * Previously inline in AppointmentWizardV2.jsx (lines 2617-2643).
 *
 * UX Audit R-3.3: inline-стили перенесены в EditModeBanner.css.
 * Раньше: 3 объекта style={{...}} с hardcoded rgba() colors.
 * Теперь: CSS-классы с var(--mac-*) tokens.
 */
import PropTypes from 'prop-types';
import './EditModeBanner.css';
import { useTranslation } from '../../i18n/adapter';

const EditModeBanner = ({ editMode, initialData }) => {
  const { t } = useTranslation();
  if (!editMode) return null;

  const isOnlineSource =
    initialData?.source_kind === 'online' || initialData?.source === 'online';

  return (
    <div className="edit-mode-banner">
      ✏️ Редактирование записи
      {isOnlineSource ? (
        <span className="edit-mode-badge edit-mode-badge--online">QR</span>
      ) : (
        <span className="edit-mode-badge edit-mode-badge--desk">Desk</span>
      )}
    </div>
  );
};

EditModeBanner.propTypes = {
  editMode: PropTypes.bool,
  initialData: PropTypes.object,
};

export default EditModeBanner;
