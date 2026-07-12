/**
 * EditModeBanner — extracted from AppointmentWizardV2.jsx (PR-45 / High-15).
 *
 * Shows a banner when the wizard is in edit mode, with a QR/Desk source badge.
 * Previously inline in AppointmentWizardV2.jsx (lines 2617-2643).
 */
import PropTypes from 'prop-types';

const EditModeBanner = ({ editMode, initialData }) => {
  if (!editMode) return null;

  const isOnlineSource =
    initialData?.source_kind === 'online' || initialData?.source === 'online';

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
      padding: '4px 10px',
      borderRadius: 'var(--mac-radius-sm)',
      background: 'rgba(59, 130, 246, 0.12)',
      color: '#2563eb',
      fontSize: '12px',
      fontWeight: 600,
      marginBottom: '4px'
    }}>
      ✏️ Редактирование записи
      {isOnlineSource ? (
        <span style={{
          padding: '1px 6px', borderRadius: '4px', fontSize: '10px',
          background: 'rgba(139, 92, 246, 0.15)', color: '#7c3aed'
        }}>QR</span>
      ) : (
        <span style={{
          padding: '1px 6px', borderRadius: '4px', fontSize: '10px',
          background: 'rgba(100, 116, 139, 0.15)', color: '#475569'
        }}>Desk</span>
      )}
    </div>
  );
};

EditModeBanner.propTypes = {
  editMode: PropTypes.bool,
  initialData: PropTypes.object,
};

export default EditModeBanner;
