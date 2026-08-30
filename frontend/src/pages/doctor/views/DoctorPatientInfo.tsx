import { X } from 'lucide-react';

import type { PatientRecord, TranslateFn } from '../doctorStatus';

/**
 * PR-UI-15-2: the patient info modal extracted verbatim from
 * pages/DoctorPanel.tsx (registrar/cashier decomposition precedent).
 * UX Audit Doctor H-07: a11y — role=dialog, aria-modal, Esc, overlay click.
 * UX Audit Doctor L-26: X → X (не XCircle, который выглядит как error).
 */
export default function DoctorPatientInfo({
  patient,
  onClose,
  t,
}: {
  patient: PatientRecord | null;
  onClose: () => void;
  t: TranslateFn;
}) {
  if (!patient) {
    return null;
  }

  return (
    <div
      className="doctor-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={t("doctor.aria_patient_info")}
      onClick={(e: React.MouseEvent<HTMLElement>) => { if (e.target === e.currentTarget) onClose(); }}
      onKeyDown={(e: React.KeyboardEvent<HTMLElement>) => { if (e.key === 'Escape') onClose(); }}
      tabIndex={-1}>
      <div className="doctor-modal-card">
        <div className="doctor-modal-header">
          <h3 className="doctor-modal-title">
            Информация о пациенте
          </h3>
          <button
            aria-label={t("doctor.aria_close_patient_info")}
            onClick={onClose}
            className="doctor-modal-close">

            {/* UX Audit Doctor L-26: X → X (не XCircle, который выглядит как error). */}
            <X size={24} />
          </button>
        </div>

        <div className="doctor-modal-body">
          <div className="doctor-flex-gap-12">
            <div className="doctor-text-sm doctor-modal-avatar">
              {patient.name?.charAt(0) || t('doctor.patient_initial')}
            </div>
            <div>
              <h4 className="doctor-modal-patient-name">
                {patient.name || t('doctor.unknown')}
              </h4>
              <p className="doctor-modal-patient-meta">
                {patient.phone || t('doctor.phone_not_set')}
              </p>
            </div>
          </div>

          <div className="doctor-modal-info-grid">
            <div>
              <p className="doctor-modal-info-label">
                Возраст
              </p>
              <p className="doctor-modal-info-value">
                {patient.age || t('doctor.age_not_set')}
              </p>
            </div>
            <div>
              <p className="doctor-modal-info-label">
                Статус
              </p>
              <p className="doctor-modal-info-value">
                {patient.status === 'active' ? t('doctor.status_active_label') :
              patient.status === 'waiting' ? t('doctor.status_waiting_label') :
              patient.status || t('doctor.unknown')}
              </p>
            </div>
          </div>
        </div>

        <div className="doctor-modal-footer">
          <button
            onClick={onClose}
            className="doctor-text-sm doctor-modal-btn-primary">

            Закрыть
          </button>
          <button
            className="doctor-text-sm doctor-modal-btn-accent"
            disabled
            title={t("doctor.feature_in_development")}>

            Редактировать
          </button>
        </div>
      </div>
    </div>
  );
}
