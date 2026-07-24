/**
 * Domain types for appointments, patients, and doctors.
 * Used by useAppointments, usePatients, useDoctors hooks,
 * EnhancedAppointmentsTable, RegistrarPanel, and other consumers.
 */

export type AppointmentStatus =
  | 'pending'
  | 'confirmed'
  | 'paid'
  | 'in_visit'
  | 'completed'
  | 'cancelled'
  | 'no_show'
  | 'queued'
  | string;

export type AppointmentType =
  | 'paid'
  | 'repeat'
  | 'benefit'
  | string;


export interface QueueNumberInfo {
  number?: string | number;
  queue_name?: string;
  queue_tag?: string;
  status?: string;
  service_name?: string;
  specialty?: string;
  [key: string]: unknown;
}

export interface Appointment {
  id?: string | number;
  patient_id?: string | number;
  patient_name?: string;
  patient_fio?: string;
  doctor_id?: string | number;
  doctor_name?: string;
  specialist_id?: string | number;
  status?: AppointmentStatus;
  type?: AppointmentType;
  date?: string;
  time?: string;
  service_id?: string | number;
  service_name?: string;
  queue_entry_id?: string | number;
  queue_number?: number | string;
  department?: string;
  specialty?: string;
  visit_id?: string | number;
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
  [key: string]: unknown;
}

export interface Patient {
  id: string | number;
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
  [key: string]: unknown;
}

export interface DoctorScheduleSlot {
  start_time?: string;
  end_time?: string;
  day_of_week?: number;
  is_available?: boolean;
  [key: string]: unknown;
}

export interface DoctorAvailability {
  date?: string;
  is_available?: boolean;
  slots?: DoctorScheduleSlot[];
  reason?: string;
  [key: string]: unknown;
}

export interface Doctor {
  id: string | number;
  full_name?: string;
  name?: string;
  specialty?: string;
  specialty_display?: string;
  department?: string;
  department_id?: string | number;
  email?: string;
  phone?: string;
  cabinet?: string | number;
  is_active?: boolean;
  price_default?: number;
  start_number_online?: number;
  user_id?: string | number;
  user?: { full_name?: string; [k: string]: unknown };
  schedule?: DoctorScheduleSlot[];
  availability?: DoctorAvailability[];
  [key: string]: unknown;
}

export interface Transaction {
  id: string | number;
  patient_id?: string | number;
  patient_name?: string;
  amount?: number;
  status?: string;
  method?: string;
  date?: string;
  [key: string]: unknown;
}

export interface ReportConfig {
  type?: string;
  dateRange?: string;
  [key: string]: unknown;
}

export interface DepartmentStats {
  total_doctors?: number;
  total_appointments?: number;
  total_patients?: number;
  active_queues?: number;
  [key: string]: unknown;
}

export interface Department {
  id?: string | number;
  name?: string;
  code?: string;
  description?: string;
  is_active?: boolean;
  doctor_count?: number;
  stats?: DepartmentStats;
  [key: string]: unknown;
}

export interface ServiceCategory {
  id?: string | number;
  name?: string;
  code?: string;
  [key: string]: unknown;
}

export interface ServiceFilter {
  category?: string;
  specialty?: string;
  department?: string;
  search?: string;
  [key: string]: unknown;
}

export interface Service {
  id: string | number;
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
  [key: string]: unknown;
}
