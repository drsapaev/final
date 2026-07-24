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

export type EMRStatus = number | string;

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
