// PR-UI-15-1: types + status presentation + a11y context helpers extracted
// verbatim from pages/DoctorPanel.tsx (registrar/cashier decomposition
// precedent — see docs/UI_REMEDIATION_PLAN.md §4.1.11/§4.1.12).
// Pure presentation mapping: no React, no data fetching, no side effects.
//
// Dead helpers NOT ported (verified definition-only in the panel source,
// count-of-references = 1 at extraction time): hasBackendQueueAction (live
// SSOT copy in components/doctor/DoctorQueuePanel.tsx + hooks/useDoctorQueue.ts
// — guarded by DoctorPanels.contract.test.tsx), callFromDiagnostics,
// formatElapsedTime, getQueuePatientContext, getQueueActionA11yProps,
// getCurrentVisitMeta (all orphaned by the UX Audit Doctor H-30 queue
// extraction to DoctorQueuePanel).

export type TranslateFn = (key: string, params?: Record<string, unknown>) => string;

// Local shape used for queue entries / patient context helpers.
// Mirrors the relevant fields from QueueEntry (domain/queue.ts) without
// importing that type here, to keep the file's dependency surface minimal.
export type QueueEntryLike = {
  id?: string | number;
  number?: string | number;
  patient_name?: string;
  status?: string;
  available_actions?: unknown[];
  [key: string]: unknown;
};

export interface PatientRecord {
  id: string | number;
  name?: string;
  phone?: string;
  gender?: string;
  diagnosis?: string;
  status?: string;
  age?: number | null;
  [key: string]: unknown;
}

export interface AppointmentDto {
  id: string | number;
  patientId?: number | null;
  patientName?: string;
  time?: string;
  type?: string;
  status?: string;
  notes?: string;
  appointmentDate?: string;
  confirmationToken?: string | null;
  confirmationChannel?: string;
  totalAmount?: number | null;
  servicesCount?: number;
  source?: string;
  [key: string]: unknown;
}

export const DOCTOR_PANEL_TABS = new Set<string>(['dashboard', 'patients', 'appointments', 'queue', 'ai', 'reports']);

// PR-UI-15-1: status presentation maps (verbatim from DoctorPanel).
// getDoctorStatusText takes the panel's t() so labels stay i18n-reactive.
export const getDoctorStatusVariant = (status: string | undefined) => {
  const statusMap: Record<string, string> = {
    'active': 'success',
    'recovery': 'warning',
    'critical': 'danger',
    'scheduled': 'primary',
    'in_progress': 'warning',
    'completed': 'success',
    'cancelled': 'danger',
    // Статусы очереди
    'waiting': 'warning',
    'called': 'primary',
    'in_service': 'info',
    'diagnostics': 'info',
    'served': 'success',
    'incomplete': 'danger',
    'no_show': 'danger'
  };
  return statusMap[status ?? ''] || 'default';
};

export const getDoctorStatusText = (status: string | undefined, t: TranslateFn) => {
  const statusMap: Record<string, string> = {
    'active': t('doctor.status_active'),
    'recovery': t('doctor.status_recovery'),
    'critical': t('doctor.status_critical'),
    'scheduled': t('doctor.status_scheduled'),
    'in_progress': t('doctor.status_in_progress'),
    'completed': t('doctor.status_completed'),
    'cancelled': t('doctor.status_cancelled'),
    // Статусы очереди
    'waiting': t('doctor.status_waiting'),
    'called': t('doctor.status_called'),
    'in_service': t('doctor.status_in_service'),
    'diagnostics': t('doctor.status_diagnostics'),
    'served': t('doctor.status_served'),
    'incomplete': t('doctor.status_incomplete'),
    'no_show': t('doctor.status_no_show')
  };
  return statusMap[status ?? ''] || (status ?? '');
};

// PR-UI-15-1: a11y context helpers (verbatim from DoctorPanel).
export const getPatientA11yContext = (patient: PatientRecord | null | undefined) => {
  const patientId = patient?.id || 'unknown';
  const patientName = patient?.name || 'patient';
  return `patient ${patientName} (${patientId})`;
};

export const getAppointmentA11yContext = (appointment: AppointmentDto | null | undefined) => {
  const appointmentId = appointment?.id || 'unknown';
  const patientName = appointment?.patientName || 'patient';
  const appointmentTime = appointment?.time ? ` at ${appointment.time}` : '';
  return `appointment ${appointmentId} for ${patientName}${appointmentTime}`;
};
