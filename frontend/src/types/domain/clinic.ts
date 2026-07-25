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

export interface Appointment {
  id: string | number;
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
  [key: string]: unknown;
}

export interface Patient {
  id: string | number;
  full_name?: string;
  name?: string;
  phone?: string;
  email?: string;
  birth_date?: string;
  gender?: string;
  address?: string;
  [key: string]: unknown;
}

export interface Doctor {
  id: string | number;
  full_name?: string;
  name?: string;
  specialty?: string;
  department?: string;
  email?: string;
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

export interface Department {
  id?: string | number;
  name?: string;
  code?: string;
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
  [key: string]: unknown;
}
