// Stub component for EditPatientModal
// This component has been replaced by AppointmentWizardV2
// Keeping this stub to prevent build errors in legacy panel files

import React from 'react';

const EditPatientModal = ({ isOpen, onClose, patient, onSave, theme }) => {
    // This is a stub - the actual functionality is now in AppointmentWizardV2
    console.warn('EditPatientModal is deprecated. Use AppointmentWizardV2 instead.');

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
                background: 'white',
                padding: '20px',
                borderRadius: '8px',
                maxWidth: '400px'
            }}>
                <h3>Edit Patient Modal (Deprecated)</h3>
                <p>This component has been replaced. Please use AppointmentWizardV2.</p>
                <button onClick={onClose}>Close</button>
            </div>
        </div>
    );
};

export default EditPatientModal;
