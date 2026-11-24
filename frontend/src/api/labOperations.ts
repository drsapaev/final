import { requestLab } from './labReporting';
import type { LabSpecimenRejectionReasonCode } from '../types/features/labWorkspace';

export type LabImportSource = 'manual' | 'csv';
export interface LabImportEntry {
  message_id: string;
  report_instance_id: number;
  specimen_barcode: string;
  expected_updated_at?: string;
  observed_at?: string;
  method_code?: string;
  replace_existing?: boolean;
  values: {
    analyte_code: string;
    unit_code: string | null;
    value_text: string;
  }[];
}

export interface LabImportOutcome {
  row_index: number;
  message_id: string | null;
  report_instance_id: number | null;
  status: 'ready' | 'saved' | 'duplicate' | 'error';
  updated_at: string | null;
  existing_values: number;
  error_code: string | null;
}

export interface LabCriticalTask {
  id: number;
  report_instance_id: number;
  state: 'needs_assignment' | 'pending' | 'inbox_recorded' | 'escalated' | 'acknowledged' | 'superseded';
  attempts: number;
  created_at: string;
  acknowledged_at: string | null;
  available_actions: ('assign' | 'escalate' | 'acknowledge')[];
}

export interface LabMetrics {
  from_at: string;
  until_at: string;
  actionable: number;
  overdue: number;
  rejected_samples: number;
  rejected_samples_by_reason?: Partial<Record<LabSpecimenRejectionReasonCode | 'unknown', number>>;
  held_samples: number;
  turnaround_pairs: number;
  average_turnaround_minutes: number | null;
  released_corrections: number;
  communications_open: number;
}

export const labOperationsApi = {
  metrics(days: number, signal: AbortSignal) {
    return requestLab(`/lab/metrics?days=${days}`, { signal }) as Promise<LabMetrics>;
  },
  importRows(source: LabImportSource, rows: LabImportEntry[], preview: boolean) {
    return requestLab(preview ? '/lab/imports/preview' : '/lab/imports', {
      method: 'POST',
      body: JSON.stringify({ source, rows }),
    }) as Promise<{ rows: LabImportOutcome[] }>;
  },
  listCritical(visitId?: number, signal?: AbortSignal) {
    const query = visitId ? `?visit_id=${visitId}` : '';
    return requestLab(`/lab/critical-communications${query}`, { signal }) as Promise<LabCriticalTask[]>;
  },
  updateCritical(id: number, action: 'acknowledge' | 'assign' | 'escalate') {
    return requestLab(`/lab/critical-communications/${id}/${action}`, { method: 'POST' }) as Promise<LabCriticalTask>;
  },
};
