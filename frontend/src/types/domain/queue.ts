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

// audit/phase-5a, BS-3: added 'served' — backend (backend/app/crud/queue.py +
// backend/app/api/v1/endpoints/doctor_integration/_queue_ops.py) uses this
// status when a patient has been fully served. Was missing from the TS union,
// which caused `e.status === 'served'` comparisons to be flagged as
// unintentional after `| string` widening was removed.
export type QueueEntryStatus = 'waiting' | 'called' | 'in_service' | 'in_cabinet' | 'completed' | 'served' | 'skipped' | 'cancelled';
export type QueueSource = 'online' | 'desk' | 'qr' | 'morning_assignment';

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
  available_actions?: unknown;
}

export interface QueueState {
  entries: QueueEntry[];
  is_open: boolean;
  opened_at: string | null;
  online_start_time?: string;
  specialist_id?: string | number;
  specialty?: string;
  date?: string;
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
}

export interface QueueFilters {
  status?: QueueEntryStatus;
  source?: QueueSource;
  specialty?: string;
  date?: string;
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
  color?: unknown;
  icon?: unknown;
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
}

export interface QueuePayload {
  queues?: QueueData[];
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
    };
}

// === Queue join session (returned by /queue/join/start) =====================
// The public-facing queue join flow returns a session envelope that includes
// the original QR info plus a session token and the list of specialists the
// patient can choose from (for clinic-wide queues).

export interface QueueJoinSessionData {
  session_token: string;
  queue_info?: QueueJoinInfo;
}

export interface QueueJoinInfo {
  selectable_specialists?: QueueSpecialist[];
  is_clinic_wide?: boolean;
  target_date?: string;
  specialist_name?: string;
  department?: string;
  department_name?: string;
  queue_name?: string;
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
}

// === Queue profiles (returned by /queues/profiles/public) ===================
// Public registry of clinic queue profiles (one per specialty/department).

export interface QueueProfile {
  id?: string | number;
  name?: string;
  specialty?: string;
  department?: string;
  is_active?: boolean;
}

export interface QueueProfilesResponse {
  profiles?: QueueProfile[];
}
