/**
 * Domain types for appointments, patients, and doctors.
 * Used by useAppointments, usePatients, useDoctors hooks.
 */

export interface Appointment {
  id: string | number;
  patient_id?: string | number;
  patient_name?: string;
  doctor_id?: string | number;
  doctor_name?: string;
  status?: string;
  date?: string;
  time?: string;
  service_id?: string | number;
  queue_entry_id?: string | number;
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
