/**
 * P-04 fix: выделенные helper-функции нормализации лабораторных бланков.
 *
 * Раньше эти функции жили внутри LabReportWorkbench.jsx (969 строк).
 * Теперь вынесены в отдельный модуль для:
 *   - возможности unit-тестирования каждой функции независимо
 *   - переиспользования в других компонентах (EMR-интеграция, печать)
 *   - снижения когнитивной нагрузки при чтении основного компонента
 */

interface LabFieldInput {
  field_key?: string | number;
  key?: string | number;
  id?: string | number;
  label?: string | number;
  name?: string;
  value_numeric?: number | null;
  value_text?: string;
  reference_text?: string;
  unit?: string;
  resolved_flag?: string | null;
  resolved_flag_severity?: number | null;
  required?: boolean;
  [key: string]: unknown;
}

interface LabSectionInput {
  key?: string | number;
  section_key?: string;
  id?: string | number;
  title?: string | number;
  name?: string;
  fields?: LabFieldInput[];
  [key: string]: unknown;
}

interface NormalizedLabField {
  field_key: string | number;
  label: string | number;
  value_numeric: number | null;
  value_text: string;
  reference_text: string;
  unit: string;
  resolved_flag: string | null;
  resolved_flag_severity: number | null;
  [key: string]: unknown;
}

interface NormalizedLabSection {
  key: string | number;
  title: string | number;
  fields: NormalizedLabField[];
  [key: string]: unknown;
}

export function extractFieldValue(field: LabFieldInput): string {
  if (field.value_numeric !== null && field.value_numeric !== undefined) {
    return formatDecimalInputValue(field.value_numeric);
  }
  return field.value_text || '';
}

export function formatDecimalInputValue(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === '') {
    return '';
  }
  const text = String(value);
  if (!text.includes('.')) {
    return text;
  }
  const [integerPart, decimalPart = ''] = text.split('.');
  const trimmedDecimal = decimalPart.replace(/0+$/, '');
  return trimmedDecimal ? `${integerPart}.${trimmedDecimal}` : integerPart;
}

export function formatFlagLabel(field: {
  resolved_flag?: string | null;
  resolved_flag_meta?: { direction?: string } | null;
}): string {
  if (!field?.resolved_flag) {
    return 'норма';
  }
  const label = {
    high: 'выше нормы',
    low: 'ниже нормы',
    warning: 'предупреждение',
    abnormal: 'отклонение',
    critical: 'критично'
  }[field.resolved_flag] || field.resolved_flag;
  const direction = field?.resolved_flag_meta?.direction;
  return direction ? `${label} ${direction}` : label;
}

export function formatThreshold(meta?: {
  matched_threshold?: { value?: number | string | null; operator?: string } | null;
} | null): string {
  const matchedThreshold = meta?.matched_threshold;
  if (!matchedThreshold?.value) {
    return '';
  }
  const operator = {
    lt: '<',
    lte: '<=',
    gt: '>',
    gte: '>='
  }[matchedThreshold.operator || ''] || matchedThreshold.operator || '';
  return `${operator} ${formatDecimalInputValue(matchedThreshold.value)}`.trim();
}

export function historySeverityState(item: {
  critical_findings_count?: number | null;
  max_flag_severity?: number | null;
}): { label: string; variant: string; order: number } {
  if ((item.critical_findings_count || 0) > 0) {
    return { label: 'critical', variant: 'danger', order: 300 };
  }
  if ((item.max_flag_severity || 0) >= 200) {
    return { label: 'flagged', variant: 'warning', order: 200 };
  }
  if ((item.max_flag_severity || 0) >= 100) {
    return { label: 'warning', variant: 'warning', order: 100 };
  }
  return { label: 'clean', variant: 'success', order: 0 };
}

export function matchesHistoryFilter(
  item: { critical_findings_count?: number | null; max_flag_severity?: number | null },
  filter: string
): boolean {
  const severity = historySeverityState(item);
  if (filter === 'critical') {
    return severity.label === 'critical';
  }
  if (filter === 'flagged') {
    return severity.order >= 100;
  }
  if (filter === 'clean') {
    return severity.order === 0;
  }
  return true;
}

export function getServiceContextItems(appointment?: {
  service_details?: Array<{ id?: string; code?: string; name?: string }>;
  service_codes?: string[];
} | null): Array<{ key: string; label: string; code: string }> {
  const serviceDetails = appointment?.service_details || [];
  if (serviceDetails.length > 0) {
    return serviceDetails
      .map((item) => ({
        key: item.id || item.code || item.name || '',
        label: item.name || item.code || 'Услуга',
        code: item.code || ''
      }))
      .filter((item) => item.key);
  }
  const serviceCodes = appointment?.service_codes || [];
  return serviceCodes.map((code) => ({
    key: code,
    label: code,
    code
  }));
}

export function normalizeLabSections(sections: LabSectionInput[] = []): NormalizedLabSection[] {
  return sections.map((section, sectionIndex) => ({
    key: section.key || section.section_key || section.id || `section-${sectionIndex}`,
    title: section.title || section.name || section.key || `Раздел ${sectionIndex + 1}`,
    fields: (section.fields || []).map((field, fieldIndex) => ({
      field_key: field.field_key || field.key || field.id || `${section.key || `section-${sectionIndex}`}-field-${fieldIndex}`,
      label: field.label || field.name || field.field_key || `Показатель ${fieldIndex + 1}`,
      value_numeric: field.value_numeric ?? null,
      value_text: field.value_text ?? '',
      reference_text: field.reference_text ?? '',
      unit: field.unit ?? '',
      resolved_flag: field.resolved_flag ?? null,
      resolved_flag_severity: field.resolved_flag_severity ?? null
    }))
  }));
}

export function flattenLabResults(sections: LabSectionInput[] = []): Array<{
  section_key: string | number | undefined;
  section_title: string | number | undefined;
  field_key: string | number | undefined;
  label: string | number | undefined;
  value_numeric: number | null | undefined;
  value_text: string | undefined;
  reference_text: string | undefined;
  unit: string | undefined;
  resolved_flag: string | null | undefined;
  resolved_flag_severity: number | null | undefined;
}> {
  return sections.flatMap((section) =>
    (section.fields || []).map((field) => ({
      section_key: section.key,
      section_title: section.title,
      field_key: field.field_key,
      label: field.label,
      value_numeric: field.value_numeric,
      value_text: field.value_text,
      reference_text: field.reference_text,
      unit: field.unit,
      resolved_flag: field.resolved_flag,
      resolved_flag_severity: field.resolved_flag_severity
    }))
  );
}

/**
 * LABPRINT-FE-001 (audit 3886, round 14): клиентский сбор печатного
 * бланка удалён. Печать отправляет ТОЛЬКО report_instance_id — сервер
 * материализует значения из БД тем же пайплайном, что канонический PDF
 * (backend/app/api/v1/endpoints/print_api.py). Клиентские значения
 * больше не собираются и не отправляются.
 */

