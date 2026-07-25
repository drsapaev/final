/**
 * Domain types for the queue system.
 * Used by useQueueManager, ModernQueueManager, QueueTable, QueueJoin,
 * QueueIntegration, and mobile queue components.
 *
 * Note: some queue types already exist in hooks/useQueueManager.ts
 * (QueueSpecialist, QueueData, QrData, etc.). This file provides
 * additional types for queue state management and actions.
 */

export type QueueEntryStatus = 'waiting' | 'called' | 'in_service' | 'in_cabinet' | 'completed' | 'skipped' | 'cancelled' | string;
export type QueueSource = 'online' | 'desk' | 'qr' | 'morning_assignment' | string;

export interface QueueEntry {
  id: string | number;
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

export interface QueueStats {
  total_entries: number;
  waiting: number;
  called: number;
  in_service: number;
  completed: number;
  skipped: number;
  [key: string]: unknown;
}

export interface QueueFilters {
  status?: QueueEntryStatus;
  source?: QueueSource;
  specialty?: string;
  date?: string;
  [key: string]: unknown;
}
