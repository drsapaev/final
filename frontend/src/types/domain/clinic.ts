/**
 * Domain types for appointments, patients, and doctors.
 * Used by useAppointments, usePatients, useDoctors hooks,
 * EnhancedAppointmentsTable, RegistrarPanel, and other consumers.
 */

import type { PatientId, AppointmentId, DoctorId, ServiceId, VisitId, QueueEntryId, UserId, DepartmentId } from './branded';

export type AppointmentStatus =
  | 'pending'
  | 'confirmed'
  | 'paid'
  | 'in_visit'
  | 'completed'
  | 'cancelled'
  | 'no_show'
  | 'queued'
  | 'waiting'
  | 'called'
  | 'in_progress'
  | 'served'
  | 'paid_pending';

export const APPOINTMENT_STATUSES: AppointmentStatus[] = [
  'pending', 'confirmed', 'paid', 'in_visit', 'completed', 'cancelled', 'no_show',
  'queued', 'waiting', 'called', 'in_progress', 'served', 'paid_pending'
];

export function normalizeAppointmentStatus(raw: string): AppointmentStatus {
  if (APPOINTMENT_STATUSES.includes(raw as AppointmentStatus)) return raw as AppointmentStatus;
  return 'pending';
}

export type AppointmentType =
  | 'paid'
  | 'repeat'
  | 'benefit';

export const APPOINTMENT_TYPES: AppointmentType[] = ['paid', 'repeat', 'benefit'];

export function normalizeAppointmentType(raw: string): AppointmentType {
  if (APPOINTMENT_TYPES.includes(raw as AppointmentType)) return raw as AppointmentType;
  return 'paid';
}


export interface QueueNumberInfo {
  number?: string | number;
  queue_name?: string;
  queue_tag?: string;
  status?: string;
  service_name?: string;
  specialty?: string;
}

export interface Appointment {
  id?: AppointmentId;
  patient_id?: PatientId;
  patient_name?: string;
  patient_fio?: string;
  doctor_id?: DoctorId;
  doctor_name?: string;
  specialist_id?: DoctorId;
  status?: AppointmentStatus | (string & {});
  type?: AppointmentType;
  date?: string;
  time?: string;
  service_id?: ServiceId;
  service_name?: string;
  queue_entry_id?: QueueEntryId;
  queue_number?: number | string;
  department?: string;
  specialty?: string;
  visit_id?: VisitId;
  payment_status?: string;
  amount?: number;
  created_at?: string;
  updated_at?: string;
  // Fields accessed in EnhancedAppointmentsTable and RegistrarPanel
  available_actions?: unknown[];
  services?: Array<{ name?: string; code?: string; [k: string]: unknown }>;
  service_codes?: string[];
  service?: string;
  number?: string | number;
  appointment_date?: string;
  appointment_time?: string;
  queue_number_status?: string;
  queue_numbers?: QueueNumberInfo[];
  payment_type?: string;
  payment_amount?: number;
  discount_mode?: string;
  approval_status?: string;
  cost?: number;
  session_id?: string;
  template_name?: string;
  flagged_findings_count?: number;
  patient_phone?: string;
  patient_birth_year?: number;
  patient_address?: string;
  specialist_name?: string;
  grouped_records?: unknown[];
  grouped_record_refs?: unknown[];
  aggregated_ids?: unknown[];
  address?: unknown;
  all_patient_services?: unknown;
  birth_year?: unknown;
  can_create_direct_payment?: unknown;
  can_create_grouped_payment?: unknown;
  can_incomplete?: unknown;
  can_no_show?: unknown;
  can_notify_diagnostics_return?: unknown;
  can_restore_next?: unknown;
  can_send_to_diagnostics?: unknown;
  canonical_status?: unknown;
  cost_display?: unknown;
  doctor?: unknown;
  doctorCabinet?: unknown;
  doctorSpecialization?: unknown;
  doctor_cabinet?: unknown;
  doctor_specialization?: unknown;
  effectiveCabinet?: unknown;
  effective_cabinet?: unknown;
  entity_type?: unknown;
  hasIntegrityWarnings?: unknown;
  has_integrity_warnings?: unknown;
  has_shared_invoice?: unknown;
  integrityWarnings?: unknown;
  integrity_warnings?: unknown;
  invoice_amount?: unknown;
  latest_lab_report?: unknown;
  name?: unknown;
  notes?: unknown;
  patient?: unknown;
  payment_contract?: unknown;
  payment_visit_id?: unknown;
  payment_visit_ids?: unknown;
  phone?: unknown;
  queueCabinet?: unknown;
  queue_cabinet?: unknown;
  queue_id?: unknown;
  queue_status?: unknown;
  queue_tag?: unknown;
  queue_time?: unknown;
  reason?: unknown;
  record_type?: unknown;
  remaining_amount?: unknown;
  source?: unknown;
  source_type?: unknown;
  specialization?: unknown;
  start_time?: unknown;
  total_amount?: unknown;
  appointmentDate?: unknown;
  appointmentTime?: unknown;
  appointment_id?: unknown;
  createdAt?: unknown;
  department_id?: unknown;
  doctorId?: unknown;
  doctorName?: unknown;
  patientId?: unknown;
  patientName?: unknown;
  patient_first_name?: unknown;
  patient_last_name?: unknown;
  payment_id?: unknown;
  service_details?: unknown;
  services_names?: unknown;
  updatedAt?: unknown;
  visit_ids?: unknown;
  visit_time?: unknown;
}

export interface Patient {
  id: PatientId;
  full_name?: string;
  name?: string;
  first_name?: string;
  last_name?: string;
  middle_name?: string;
  phone?: string;
  email?: string;
  birth_date?: string;
  sex?: string;
  gender?: string;
  doc_type?: string;
  doc_number?: string;
  address?: string;
  created_at?: string;
  birthDate?: unknown;
}

export interface DoctorScheduleSlot {
  start_time?: string;
  end_time?: string;
  day_of_week?: number;
  is_available?: boolean;
}

export interface DoctorAvailability {
  date?: string;
  is_available?: boolean;
  slots?: DoctorScheduleSlot[];
  reason?: string;
}

export interface Doctor {
  id: DoctorId;
  full_name?: string;
  name?: string;
  specialty?: string;
  specialty_display?: string;
  department?: string;
  department_id?: DepartmentId;
  email?: string;
  phone?: string;
  cabinet?: string | number;
  is_active?: boolean;
  price_default?: number;
  start_number_online?: number;
  user_id?: UserId;
  user?: { full_name?: string; [k: string]: unknown };
  schedule?: DoctorScheduleSlot[];
  availability?: DoctorAvailability[];
  active?: unknown;
  experience?: unknown;
  patientsCount?: unknown;
  specialization?: unknown;
  schedules?: unknown;
}

export interface Transaction {
  id: string | number;
  patient_id?: PatientId;
  patient_name?: string;
  amount?: number;
  status?: string;
  method?: string;
  date?: string;
}

export interface ReportConfig {
  type?: string;
  dateRange?: string;
  filters?: unknown;
  format?: unknown;
}

export interface DepartmentStats {
  total_doctors?: number;
  total_appointments?: number;
  total_patients?: number;
  active_queues?: number;
}

export interface Department {
  id?: AppointmentId;
  name?: string;
  code?: string;
  description?: string;
  is_active?: boolean;
  doctor_count?: number;
  stats?: DepartmentStats;
}

export interface ServiceCategory {
  id?: AppointmentId;
  name?: string;
  code?: string;
}

export interface ServiceFilter {
  category?: string;
  specialty?: string;
  department?: string;
  search?: string;
}

export interface Service {
  id: ServiceId;
  name?: string;
  code?: string;
  category?: string;
  category_code?: string;
  price?: number;
  duration?: number;
  specialty?: string;
  department?: string;
  is_active?: boolean;
  is_consultation?: boolean;
  requires_doctor?: boolean;
  description?: string;
}
