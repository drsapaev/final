export interface CartItem {
  id?: string | number;
  service_id?: string | number;
  service_name?: string;
  service_price?: number;
  doctor_id?: string | number | null;
  doctor_name?: string;
  notes?: string;
  _temp_name?: string;
  _temp_price?: number;
  quantity?: number;
  visit_date?: string;
  visit_time?: string | null;
  original_queue_id?: string | number;
  service_code?: string;
  name?: string;
  _source?: string;
  code?: string;
  [k: string]: unknown;
}

export interface PatientRecord {
  id?: string | number;
  phone?: string;
  fio?: string;
  last_name?: string;
  first_name?: string;
  middle_name?: string;
  gender?: string;
  birth_date?: string;
  [k: string]: unknown;
}

export interface DoctorData {
  id?: string | number;
  name?: string;
  full_name?: string;
  specialty?: string;
  department?: string;
  [k: string]: unknown;
}

export interface VisitServiceItem {
  service_id?: string | number;
  service_name?: string;
  service_price?: number;
  quantity?: number | string;
  original_queue_id?: string | number;
  service_code?: string;
  name?: string;
  _source?: string;
  [k: string]: unknown;
}

export interface VisitGroup {
  doctor_id?: string | number | null;
  services: VisitServiceItem[];
  visit_date?: string;
  visit_time?: string | null;
  department?: string;
  notes?: string | null;
  [k: string]: unknown;
}

export interface RepeatCandidate {
  candidate_key: string;
  doctor_id?: string | number;
  service_id?: string | number;
  visit_date: string;
}
