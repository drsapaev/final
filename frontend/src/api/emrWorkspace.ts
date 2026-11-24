import { apiClient } from './client';

export type ClinicalSource = 'clinician' | 'patient_report' | 'legacy_verified';
export type AllergyState = 'specific' | 'none_reported' | 'unknown' | 'not_checked';

interface ClinicalDates {
  event_on?: string | null;
  ended_on?: string | null;
}

export type ClinicalFact = ClinicalDates & (
  | { kind: 'problem'; name: string; status: 'active' | 'resolved' | 'inactive'; code?: string | null }
  | { kind: 'medication'; name: string; status: 'prescribed' | 'reported' | 'taking' | 'stopped';
      dose?: string | null; regimen?: string | null }
  | { kind: 'allergy'; name: string; status: 'active' | 'inactive'; reaction?: string | null;
      severity?: 'mild' | 'moderate' | 'severe' | null }
  | { kind: 'allergy_check'; status: Exclude<AllergyState, 'specific'> }
);

export interface ClinicalEntry {
  entry_id: string;
  version: number;
  schema_version: number;
  visit_id: number;
  author_id: number;
  source: ClinicalSource;
  clinical_details: ClinicalFact;
  recorded_at: string;
  confirmed_at: string | null;
}

export interface HistorySummary {
  id: number;
  visit_id: number;
  version: number;
  visit_date: string | null;
  signed_at: string | null;
  status: string;
  complaints: string;
  diagnosis: string;
  treatment: string;
  recommendations: string;
  vitals: Record<string, unknown>;
  echo: Record<string, unknown>;
  laboratory: {
    instance_id: number; name: string; value: string; unit: string | null;
    finalized_at: string | null; abnormal: boolean;
  }[];
}

export interface HistoryDocument extends HistorySummary {
  data: Record<string, unknown>;
}

export type TransferField = 'complaints' | 'diagnosis' | 'treatment' | 'recommendations';
export interface TransferSelection {
  source_visit_id: number;
  source_version: number;
  field: TransferField;
  confirmed_current: boolean;
}
export interface TransferredField extends TransferSelection {
  source_patient_id: number;
  source_document_id: number;
  text: string;
  transferred_by?: number;
  transferred_at?: string;
}

export interface FollowUp {
  mode?: 'initial' | 'follow_up' | 'new_complaint' | null;
  changes?: string;
  actual_treatment?: string;
  prior_plan_follow_through?: string;
  new_results?: string;
  transferred_fields?: TransferredField[];
}

export interface EMRWorkspaceData {
  patient: {
    id: number;
    full_name: string;
    birth_date: string | null;
    legacy_allergies: string | null;
    legacy_conditions: string | null;
  };
  visit: { id: number; date: string | null; status: string };
  allergy_state: AllergyState;
  clinical_entries: ClinicalEntry[];
  history: HistorySummary[];
  has_more_history: boolean;
}

export function emrWorkspacePath(visitId: string | number) {
  return `/v2/emr/${visitId}/workspace`;
}

export async function getEMRWorkspace(
  visitId: string | number,
  patientId: string | number | null,
  signal?: AbortSignal,
  offset = 0,
): Promise<EMRWorkspaceData> {
  const { data } = await apiClient.get<EMRWorkspaceData>(emrWorkspacePath(visitId), {
    params: { patient_id: patientId ?? undefined, offset },
    signal,
    silent: true,
  });
  if (String(data?.visit?.id) !== String(visitId) || (patientId != null && String(data.patient?.id) !== String(patientId))) {
    throw new Error('EMR workspace context mismatch');
  }
  return data;
}

export async function saveClinicalEntry(
  visitId: number,
  patientId: number,
  id: string,
  version: number,
  clinical_details: ClinicalFact,
  source: ClinicalSource,
  confirmed: boolean,
) {
  await apiClient.put(`${emrWorkspacePath(visitId)}/entries/${id}`, {
    patient_id: patientId, expected_version: version, clinical_details, source, confirmed,
  }, { silent: true });
}

export async function getClinicalHistory(visitId: number, patientId: number, id: string): Promise<ClinicalEntry[]> {
  const { data } = await apiClient.get<ClinicalEntry[]>(`${emrWorkspacePath(visitId)}/entries/${id}/history`, {
    params: { patient_id: patientId },
    silent: true,
  });
  return data;
}

export async function getWorkspaceHistoryDocument(
  visitId: number, patientId: number, sourceVisit: number, version: number,
): Promise<HistoryDocument> {
  const { data } = await apiClient.get<HistoryDocument>(
    `${emrWorkspacePath(visitId)}/history/${sourceVisit}/${version}`,
    { params: { patient_id: patientId }, silent: true },
  );
  return data;
}

export interface WorkspacePrescription {
  id: number;
  visit_id: number;
  emr_version: number | null;
  is_draft: boolean;
}

export async function getWorkspacePrescription(visitId: number, patientId: number, signal: AbortSignal) {
  const { data } = await apiClient.get<WorkspacePrescription | null>(`${emrWorkspacePath(visitId)}/prescription`, {
    params: { patient_id: patientId }, signal, silent: true,
  });
  return data;
}

export async function issueWorkspacePrescription(visitId: number, patientId: number, rowVersion: number) {
  const { data } = await apiClient.post<WorkspacePrescription>(`${emrWorkspacePath(visitId)}/prescription`, {
    patient_id: patientId, expected_row_version: rowVersion,
  }, { silent: true });
  return data;
}

export interface WorkspaceLabReview {
  reviewer_id: number;
  reviewed_at: string;
  next_action: string | null;
}

export interface WorkspaceLabReport {
  id: number;
  status: string;
  template_name: string;
  supersedes_instance_id: number | null;
  finalized_at: string | null;
  is_current_final: boolean;
  reviews: WorkspaceLabReview[];
}

export interface WorkspaceLabs {
  orders: { id: number; status: string; created_at: string; reports: WorkspaceLabReport[] }[];
  unlinked_reports: WorkspaceLabReport[];
  executions: { id: number; service_name: string; attempt: number; status: string }[];
  invoices: { id: number; status: string }[];
}

export async function getWorkspaceLabs(visitId: string | number, patientId: string | number | null, signal: AbortSignal) {
  const { data } = await apiClient.get<WorkspaceLabs>(`${emrWorkspacePath(visitId)}/labs`, {
    params: { patient_id: patientId ?? undefined }, signal, silent: true,
  });
  if (!Array.isArray(data?.orders) || !Array.isArray(data.unlinked_reports)
    || !Array.isArray(data.executions) || !Array.isArray(data.invoices)) {
    throw new Error('Invalid EMR laboratory workspace response');
  }
  return data;
}

export async function reviewLabVersion(
  visitId: string | number, patientId: string | number, instanceId: number, nextAction: string,
) {
  await apiClient.post(`${emrWorkspacePath(visitId)}/labs/${instanceId}/review`, {
    patient_id: patientId, next_action: nextAction || null,
  }, { silent: true });
}
