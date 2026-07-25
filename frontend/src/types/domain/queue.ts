/**
 * Domain types for the queue system.
 * Used by useQueueManager, ModernQueueManager, QueueTable, QueueJoin,
 * QueueIntegration, QueueBoard, and mobile queue components.
 *
 * Consolidation note (Wave 1, Domain Adoption 100%):
 * Previously the queue domain had a parallel set of types in
 * hooks/useQueueManager.ts (QueueSpecialist, QueueData, QrData,
 * QueueActionResponse, etc.). Those have been merged into this file
 * as the SSOT and removed from the hook.
 */

export type QueueEntryStatus = 'waiting' | 'called' | 'in_service' | 'in_cabinet' | 'completed' | 'skipped' | 'cancelled' | string;
export type QueueSource = 'online' | 'desk' | 'qr' | 'morning_assignment' | string;

export interface QueueEntry {
  id?: string | number;
  queue_number?: number | string;
  patient_id?: string | number;
  patient_name?: string;
  phone?: string;
  status?: QueueEntryStatus;
  source?: QueueSource;
  specialty?: string;
  specialist_id?: string | number;
  created_at?: string;
  called_at?: string;
  completed_at?: string;
  people_before?: number;
  estimated_wait_time?: number;
  [key: string]: unknown;
}

export interface QueueState {
  entries: QueueEntry[];
  is_open: boolean;
  opened_at: string | null;
  online_start_time?: string;
  specialist_id?: string | number;
  specialty?: string;
  date?: string;
  [key: string]: unknown;
}

export type QueueAction =
  | { type: 'SET_QUEUE'; payload: QueueState }
  | { type: 'ADD_ENTRY'; payload: QueueEntry }
  | { type: 'UPDATE_ENTRY'; payload: QueueEntry }
  | { type: 'REMOVE_ENTRY'; payload: string | number }
  | { type: 'CALL_NEXT'; payload: { specialist_id: string | number } }
  | { type: 'OPEN_QUEUE'; payload: { specialist_id: string | number; date: string } }
  | { type: 'CLOSE_QUEUE'; payload: { specialist_id: string | number } }
  | { type: 'CLEAR_QUEUE' };

// Stats are partially-typed: backend may return any subset of these
// fields plus extras. All fields optional so consumers can safely
// read what's present without `as any` casts.
export interface QueueStats {
  total_entries?: number;
  total?: number;
  totalEntries?: number;
  waiting?: number;
  waiting_entries?: number;
  waitingCount?: number;
  called?: number;
  in_service?: number;
  in_cabinet?: number;
  completed?: number;
  served?: number;
  served_count?: number;
  skipped?: number;
  cancelled?: number;
  [key: string]: unknown;
}

export interface QueueFilters {
  status?: QueueEntryStatus;
  source?: QueueSource;
  specialty?: string;
  date?: string;
  [key: string]: unknown;
}

// === Specialist (was local in useQueueManager.ts) ===========================

export interface QueueSpecialist {
  id: number | string;
  doctor_name?: string;
  full_name?: string;
  name?: string;
  user?: { full_name?: string; [k: string]: unknown };
  specialty?: string;
  specialty_display?: string;
  cabinet?: string | number;
  department?: string;
  [key: string]: unknown;
}

// === Queue snapshot (was local in useQueueManager.ts) =======================

export interface QueueData {
  id?: number;
  entries?: QueueEntry[];
  stats?: QueueStats | null;
  statistics?: QueueStats | null;
  opened_at?: string | null;
  is_open?: boolean;
  online_start_time?: string;
  specialist_id?: number | string;
  specialty?: string;
  queue_id?: number;
  [key: string]: unknown;
}

export interface QueuePayload {
  queues?: QueueData[];
  [key: string]: unknown;
}

// === QR codes (was local in useQueueManager.ts) =============================

export interface QrData {
  qr_code_base64?: string;
  day?: string;
  specialist_name?: string;
  is_clinic_wide?: boolean;
  department_name?: string;
  department?: string;
  target_date?: string;
  token?: string;
  expires_at?: string;
  [key: string]: unknown;
}

// === Action args / responses (was local in useQueueManager.ts) =============

export interface LoadQueueSnapshotArgs {
  specialistId: string | number;
  targetDate: string;
  doctor?: QueueSpecialist;
}

export interface GenerateDoctorQRCodeArgs {
  specialistId: string | number;
  targetDate: string;
  department?: string;
  specialistName?: string;
  expiresHours?: number;
}

export interface GenerateClinicQRCodeArgs {
  targetDate: string;
  expiresHours?: number;
}

export interface ReceptionSlotArgs {
  specialistId: string | number;
  targetDate: string;
}

export interface QueueActionResponse {
  success?: boolean;
  message?: string;
  patient?: {
    id?: number;
    name?: string;
    number?: number | string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

// === Queue join session (returned by /queue/join/start) =====================
// The public-facing queue join flow returns a session envelope that includes
// the original QR info plus a session token and the list of specialists the
// patient can choose from (for clinic-wide queues).

export interface QueueJoinSessionData {
  session_token: string;
  queue_info?: QueueJoinInfo;
  [key: string]: unknown;
}

export interface QueueJoinInfo {
  selectable_specialists?: QueueSpecialist[];
  is_clinic_wide?: boolean;
  target_date?: string;
  specialist_name?: string;
  department?: string;
  department_name?: string;
  queue_name?: string;
  [key: string]: unknown;
}

// === QR token info (returned by /queue/qr-tokens/{token}/info) ==============
// Public QR token metadata shown on the join page before the user starts.

export interface QrTokenInfo {
  is_clinic_wide?: boolean;
  target_date?: string;
  specialist_name?: string;
  department?: string;
  department_name?: string;
  queue_name?: string;
  valid?: boolean;
  expired?: boolean;
  [key: string]: unknown;
}

// === Queue profiles (returned by /queues/profiles/public) ===================
// Public registry of clinic queue profiles (one per specialty/department).

export interface QueueProfile {
  id?: string | number;
  name?: string;
  specialty?: string;
  department?: string;
  is_active?: boolean;
  [key: string]: unknown;
}

export interface QueueProfilesResponse {
  profiles?: QueueProfile[];
  [key: string]: unknown;
}
