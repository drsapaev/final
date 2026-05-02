// Stub component for EditPatientModal
// This component has been replaced by AppointmentWizardV2
// Keeping this stub to prevent build errors in legacy panel files
import PropTypes from 'prop-types';

const EditPatientModal = ({ isOpen, onClose }) => {
    if (!isOpen) return null;

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999
        }}>
            <div style={{
                background: 'var(--mac-card-bg, white)',
                padding: '20px',
                borderRadius: '8px',
                maxWidth: '400px',
                border: '1px solid var(--mac-card-border, #d8dde8)'
            }}>
                <h3 style={{ marginTop: 0 }}>Edit Patient Modal</h3>
                <p>This legacy modal has been replaced by AppointmentWizardV2.</p>
                <button onClick={onClose}>Close</button>
            </div>
        </div>
    );
};

EditPatientModal.propTypes = {
  ...(EditPatientModal.propTypes || {}),
  isOpen: PropTypes.any,
  onClose: PropTypes.any,
};

export default EditPatientModal;
