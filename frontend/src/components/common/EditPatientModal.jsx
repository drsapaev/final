// QW-02 (UX audit): EditPatientModal — functional wrapper around AppointmentWizardV2.
//
// Background (P-002 Critical): this component was previously a stub that
// rendered "This legacy modal has been replaced by AppointmentWizardV2"
// and a Close button. The cardiologist/dermatologist/dentist panels still
// call `setEditPatientModal({ open: true, ... })` from their action
// handlers, so doctors ended up in a functional dead-end: clicking
// "Edit patient" opened a stub modal instead of an actual edit form.
//
// Fix: render AppointmentWizardV2 in editMode with the row data passed
// through `patient`. The wizard already supports editMode + initialData
// (used by RegistrarPanel), enforces RBAC via useRoleAccess, and emits
// onComplete when the edit succeeds. We delegate to that path instead
// of duplicating the form.
import PropTypes from 'prop-types';
import AppointmentWizardV2 from '../wizard/AppointmentWizardV2';
import logger from '../../utils/logger';

const EditPatientModal = ({ isOpen, onClose, patient, onSave, loading = false }) => {
  if (!isOpen) {
    return null;
  }

  // Translate the legacy `patient` shape (partial row from the appointments
  // table) into the initialData contract expected by AppointmentWizardV2
  // in edit mode. The wizard is tolerant of missing fields — it normalizes
  // internally — but we at least make sure the queue entry id and patient
  // identity are passed through when available.
  const initialData = patient
    ? {
        id: patient?.id ?? patient?.appointment_id ?? patient?.queue_entry_id ?? null,
        queue_entry_id:
          patient?.queue_entry_id ?? patient?.queueEntryId ?? patient?.id ?? null,
        patient: {
          id: patient?.patient_id ?? patient?.id ?? null,
          fio: patient?.patient_fio ?? patient?.fio ?? patient?.fullName ?? '',
          birth_date: patient?.birth_date ?? patient?.birthday ?? '',
          phone: patient?.phone ?? '',
          address: patient?.address ?? '',
          gender: patient?.gender ?? ''
        },
        // Carry over the original row so the wizard can read services /
        // doctor / discount if present.
        __raw: patient
      }
    : null;

  const handleComplete = (wizardData) => {
    logger.info('[EditPatientModal] AppointmentWizardV2 completed (edit mode)', wizardData);
    if (typeof onSave === 'function') {
      // Fire-and-forget: parent decides whether to await.
      Promise.resolve(onSave(wizardData)).catch((err) => {
        logger.warn('[EditPatientModal] onSave rejected', err);
      });
    }
    if (typeof onClose === 'function') {
      onClose();
    }
  };

  return (
    <AppointmentWizardV2
      isOpen={isOpen}
      editMode={true}
      initialData={initialData}
      isProcessing={loading}
      setIsProcessing={() => { /* no-op: parent does not track processing state */ }}
      onClose={onClose}
      onComplete={handleComplete}
    />
  );
};

EditPatientModal.propTypes = {
  ...(EditPatientModal.propTypes || {}),
  isOpen: PropTypes.any,
  onClose: PropTypes.any,
  patient: PropTypes.any,
  onSave: PropTypes.any,
  loading: PropTypes.any,
  // Theme is accepted for backwards compat with cardio/derma/dentist callers
  // but is no longer used — AppointmentWizardV2 has its own theming.
  theme: PropTypes.any
};

export default EditPatientModal;
