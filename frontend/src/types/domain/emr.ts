/**
 * Domain types for EMR (Electronic Medical Records).
 *
 * These describe the template structure used by useEMRTemplateLibrary
 * and the record structure used by useEMR.
 */

export interface EMRTemplateField {
  id?: string;
  label?: string;
  name?: string;
  type?: string;
  value?: unknown;
  [key: string]: unknown;
}

export interface EMRTemplateSection {
  id?: string;
  section_title?: string;
  section_name?: string;
  fields?: EMRTemplateField[];
  [key: string]: unknown;
}

export interface EMRTemplateStructure {
  template_name?: string;
  sections?: EMRTemplateSection[];
  [key: string]: unknown;
}

export interface EMRTemplate {
  id?: string | number;
  name?: string;
  description?: string;
  specialty?: string;
  template_structure?: EMRTemplateStructure;
  [key: string]: unknown;
}

export interface EMRTemplateSuggestion {
  text: string;
  source: string;
  template?: EMRTemplate;
  [key: string]: unknown;
}

export interface EMRRecord {
  id?: string | number;
  visit_id?: string | number;
  specialty_data?: Record<string, unknown>;
  row_version?: number;
  is_draft?: boolean;
  [key: string]: unknown;
}

// audit/phase-5a, BS-9: renamed from `EMRStatus` to `EMRHttpStatus` to avoid
// case-only confusion with `EmrStatus` in `types/features/emr.ts` (which
// models UI state machine: 'idle' | 'loading' | 'saving' | 'error' | 'conflict').
// This type models HTTP status codes returned by the EMR API (401, 403, etc).
// The two types have completely different semantics; the case-only naming
// difference was a review hazard.
export type EMRHttpStatus = number | string;
// Backward-compat alias — old code may still import `EMRStatus`.
/** @deprecated Use `EMRHttpStatus` instead. */
export type EMRStatus = EMRHttpStatus;

export interface EMRApiError {
  response?: {
    status?: number;
    data?: {
      detail?: string;
      message?: string;
      [key: string]: unknown;
    };
    [key: string]: unknown;
  };
  message?: string;
  [key: string]: unknown;
}

// === EMR Clinical Content Types ===
// Used by EMR sections (complaints, anamnesis, examination, diagnosis,
// prescriptions) and AI suggestion validation.

export interface EMRDiagnosis {
  id?: string | number;
  code?: string;
  description?: string;
  icd10?: string;
  confidence?: number;
  source?: string;
  [key: string]: unknown;
}

export interface EMRPrescription {
  id?: string | number;
  name?: string;
  drug?: string;
  dose?: string;
  dosage?: string;
  frequency?: string;
  freq?: string;
  duration?: string;
  note?: string;
  [key: string]: unknown;
}

export interface EMRSection {
  id?: string;
  title?: string;
  name?: string;
  label?: string;
  value?: string;
  isEditable?: boolean;
  isDraft?: boolean;
  error?: string;
  [key: string]: unknown;
}

export interface EMRLabResult {
  id?: string | number;
  test_name?: string;
  value?: string | number;
  unit?: string;
  reference_range?: string;
  status?: string;
  date?: string;
  abnormal?: boolean;
  [key: string]: unknown;
}

export interface EMRAISuggestion {
  id?: string | number;
  content?: string;
  text?: string;
  source?: string;
  confidence?: number;
  [key: string]: unknown;
}

export type EMRVisitType = 'paid' | 'repeat' | 'benefit';

export interface EMRVisitData {
  visit_id?: string | number;
  patient_id?: string | number;
  patient_name?: string;
  doctor_id?: string | number;
  doctor_name?: string;
  specialty?: string;
  visit_type?: EMRVisitType;
  date?: string;
  status?: string;
  [key: string]: unknown;
}


// === EMR Conflict & Amendment Types ===

export interface EMRConflict {
  type?: 'row_version_mismatch' | 'concurrent_edit' | 'deleted' | string;
  message?: string;
  server_data?: EMRRecord;
  client_data?: EMRRecord;
  server_row_version?: number;
  client_row_version?: number;
  [key: string]: unknown;
}

export interface EMRAmendRequest {
  reason: string;
  data?: Record<string, unknown>;
  row_version?: number;
  [key: string]: unknown;
}

export interface EMRSaveResult {
  success: boolean;
  data?: EMRRecord;
  error?: string;
  conflict?: EMRConflict;
  [key: string]: unknown;
}

export interface EMRSectionConfig {
  id: string;
  label: string;
  fieldName: string;
  aiEnabled?: boolean;
  isEditable?: boolean;
  multiline?: boolean;
  rows?: number;
  placeholder?: string;
  required?: boolean;
  [key: string]: unknown;
}
