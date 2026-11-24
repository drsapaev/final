
import { Badge, Input } from '../ui/macos';
import { extractFieldValue, formatThreshold, getEvaluationLabelKey } from './utils/labReportNormalize';
import { flagVariant } from './utils/labReportActions';
// STRAT#24: t() для i18n — field-level strings.
// ADR-0015: lab reporting API accessed via hook (LABEDIT-FE-001 details read).
import { useLabReporting } from '../../hooks/useLabReporting';
import { useTranslation } from '../../i18n/useTranslation';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useEffect, useId, useMemo, useState } from 'react';
import type { KeyboardEvent } from 'react';
import './ReportEditor.css';

const NUMERIC_INPUT_FORMAT = /^(?:[<>]=?|[≤≥])?\s*[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[Ee][+-]?\d{1,3})?$/;

/**
 * STRAT#24: ReportEditor — extracted from LabReportWorkbench.
 *
 * Renders the sections/fields editor for an active lab report instance.
 * Previously this ~210-line JSX block was inline in LabReportWorkbench,
 * making the god-component even harder to maintain. Now it's isolated
 * with a clear prop contract.
 *
 * Props:
 *   - activeInstance: the LabReportInstance being edited
 *   - draftValues: current field values (field_key → value)
 *   - collapsedSections: Set of collapsed section keys
 *   - onToggleSection: (sectionKey) => void
 *   - onUpdateField: (fieldKey, value) => void
 *   - canEditActiveInstance: boolean — whether fields are editable
 *   - reportHistory: array — for previous-result trending
 */
interface LabReportField {
  [key: string]: unknown;
  field_key: string;
  label: string;
  value_type?: string;
  reference_text?: string;
  resolved_flag_meta?: {
    matched_threshold?: { value: string; operator: string };
    direction?: string;
  };
  resolved_flag_source?: string;
  resolved_flag?: string;
  resolved_flag_severity?: number | null;
  required?: boolean;
  unit?: string;
  choice_options?: string[];
  choice_option_codes?: Array<'negative' | 'positive' | 'indeterminate' | null> | null;
  value_text?: string;
  value_numeric?: number | null;
  value_display?: string;
  unit_code?: string;
  analyte_code?: string;
  result_kind?: string | null;
  method_code?: string | null;
  evaluation_status?: string | null;
  interpretation?: string | null;
  instrument_flags?: string[];
  absence_reason?: string | null;
  evaluation_snapshot?: { method?: string | null; method_code?: string | null };
}

interface LabReportSection {
  key: string;
  title?: string;
  fields: LabReportField[];
}

interface LabReportInstance {
  status?: string;
  version_no?: number;
  sections: LabReportSection[];
}

interface LabReportHistoryEntry {
  status?: string;
  id?: string | number;
  patient_id?: string | number;
  template_id?: string | number;
  created_at?: string;
}

interface ReportEditorProps {
  activeInstance: LabReportInstance;
  draftValues: Record<string, string>;
  acceptedValues?: Record<string, unknown>;
  collapsedSections: Set<unknown>;
  onToggleSection: (sectionKey: string) => void;
  onUpdateField: (fieldKey: string, value: string) => void;
  canEditActiveInstance?: boolean;
  reportHistory?: LabReportHistoryEntry[];
}

const assessmentBadgeStyle = { whiteSpace: 'normal' };

export default function ReportEditor({
  activeInstance,
  draftValues,
  acceptedValues,
  collapsedSections,
  onToggleSection,
  onUpdateField,
  canEditActiveInstance,
  reportHistory = [],
}: ReportEditorProps) {
  const { t, language } = useTranslation();
  const editorId = useId();

  // LABEDIT-FE-001 (audit 3886) + LABEDIT-FE-003/004 (post-merge review of
  // PR 3916): the list API returns summary DTOs WITHOUT `sections` (backend
  // LabReportInstanceSummaryOut), so the previous-value trend can never come
  // from a history row. The trend reads the authorized DETAILS of the actual
  // preceding SAME-TEMPLATE, SAME-PATIENT instance — fetched once per
  // predecessor id (fail-closed: a failed/unshaped/mismatched read simply
  // renders no trend, never a fabricated value).
  //
  // LABEDIT-FE-003 (P1): the fetched details are bound to the predecessor +
  // patient identity they were fetched for and dropped SYNCHRONOUSLY when
  // that identity changes — a report/patient switch must never render the
  // previous report's (potentially another patient's) clinical values
  // beside the new report's fields, not even while the new GET is pending.
  //
  // LABEDIT-FE-004 (P2): the predecessor must be chronologically OLDER than
  // the active instance (created_at, deterministic id tie-break) — a newer
  // entry (the operator opened an older report) is a FUTURE result and is
  // never presented as the «previous» value; the nearest preceding entry is
  // chosen without relying on the history list order.
  const labReportingApi = useLabReporting();
  const [previousInstanceDetails, setPreviousInstanceDetails] = useState<{
    predecessorId: string;
    patientId: string;
    details: LabReportInstance;
  } | null>(null);
  const activeIdentity = useMemo(() => {
    const inst = activeInstance as {
      id?: string | number;
      patient_id?: string | number;
      template_id?: string | number;
      created_at?: string;
    };
    return {
      id: inst.id ?? null,
      patientId: inst.patient_id ?? null,
      templateId: inst.template_id ?? null,
      createdAt: inst.created_at ?? null,
    };
  }, [activeInstance]);
  const previousSameTemplateEntry = useMemo(() => {
    const { id: activeId, patientId, templateId, createdAt } = activeIdentity;
    if (!Array.isArray(reportHistory) || activeId == null || templateId == null) return null;
    // LABEDIT-FE-003: enforce same-patient scope — the trend compares values
    // of the SAME patient's longitudinal history only; without a known
    // patient scope there is no honest trend (fail-closed: none rendered).
    if (patientId == null) return null;
    // LABEDIT-FE-004: the chronology must be establishable.
    const activeTs = createdAt != null ? Date.parse(createdAt) : NaN;
    if (!Number.isFinite(activeTs)) return null;
    const compareIds = (a: string | number, b: string | number): number => {
      const na = typeof a === 'number' ? a : Number(a);
      const nb = typeof b === 'number' ? b : Number(b);
      if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb;
      return String(a) < String(b) ? -1 : String(a) > String(b) ? 1 : 0;
    };
    let best: { entry: LabReportHistoryEntry; ts: number } | null = null;
    for (const entry of reportHistory) {
      if (entry?.id == null || String(entry.id) === String(activeId)) continue;
      if (entry.status && !['FINALIZED', 'PRINTED'].includes(entry.status)) continue;
      if (entry.template_id == null || String(entry.template_id) !== String(templateId)) continue;
      if (entry.patient_id == null || String(entry.patient_id) !== String(patientId)) continue;
      const ts = entry.created_at != null ? Date.parse(entry.created_at) : NaN;
      if (!Number.isFinite(ts)) continue;
      // LABEDIT-FE-004: only chronologically older entries qualify — a newer
      // same-template entry is a FUTURE result. Deterministic id tie-break
      // for an equal created_at: the smaller id precedes the active report.
      const older = ts < activeTs || (ts === activeTs && compareIds(entry.id, activeId) < 0);
      if (!older) continue;
      // Nearest preceding entry wins (max created_at, then max id) —
      // independent of the list order.
      if (
        best == null
        || ts > best.ts
        || (ts === best.ts && compareIds(entry.id, best.entry.id as string | number) > 0)
      ) {
        best = { entry, ts };
      }
    }
    return best?.entry ?? null;
  }, [reportHistory, activeIdentity]);
  const previousEntryId = previousSameTemplateEntry?.id ?? null;
  useEffect(() => {
    const predecessorKey = previousEntryId != null ? String(previousEntryId) : null;
    const patientKey = activeIdentity.patientId != null ? String(activeIdentity.patientId) : null;
    const boundNow = previousInstanceDetails;
    const boundIsCurrent = boundNow != null
      && predecessorKey != null
      && patientKey != null
      && boundNow.predecessorId === predecessorKey
      && boundNow.patientId === patientKey;
    // The bound details already describe the CURRENT (patient, predecessor)
    // identity — effect re-runs for the SAME identity (e.g. a hook object
    // recreated between renders) must not drop them or refetch. This also
    // keeps the fetch StrictMode-safe: a simulated remount re-runs the
    // effect, the cancelled first fetch is simply repeated.
    if (boundIsCurrent) return;
    // LABEDIT-FE-003 (P1): drop the previous report's trend details
    // SYNCHRONOUSLY the moment the predecessor/active identity changes —
    // A's analytes must never render beside B's fields while B's detail
    // GET is pending (or stuck).
    setPreviousInstanceDetails(null);
    if (previousEntryId == null || patientKey == null) return;
    let cancelled = false;
    labReportingApi
      .getInstance(previousEntryId)
      .then((details: unknown) => {
        if (cancelled) return;
        const shaped = details as (LabReportInstance & { id?: string | number; patient_id?: string | number }) | null;
        // Fail-closed: only a well-shaped details DTO renders a trend.
        if (!shaped || !Array.isArray(shaped.sections)) return;
        // LABEDIT-FE-003: the details must belong to the same patient as
        // the active report — a mismatched DTO is suppressed entirely.
        if (String(shaped.id) !== predecessorKey || String(shaped.patient_id) !== patientKey) return;
        if (!['FINALIZED', 'PRINTED'].includes(String(shaped.status))) return;
        setPreviousInstanceDetails({ predecessorId: String(previousEntryId), patientId: patientKey, details: shaped });
      })
      .catch(() => {
        if (!cancelled) setPreviousInstanceDetails(null);
      });
    return () => { cancelled = true; };
  }, [previousEntryId, activeIdentity.patientId, labReportingApi, previousInstanceDetails]);
  // LABEDIT-FE-003 (P1): render the trend ONLY when the fetched details are
  // bound to the CURRENT predecessor + patient — during a report/patient
  // switch the stale bound record fails this guard and nothing renders
  // (even before the clearing effect flushes).
  const previousTrendDetails = useMemo(() => {
    const bound = previousInstanceDetails;
    if (!bound) return null;
    if (previousSameTemplateEntry?.id == null) return null;
    if (String(previousSameTemplateEntry.id) !== bound.predecessorId) return null;
    if (activeIdentity.patientId == null || String(activeIdentity.patientId) !== bound.patientId) return null;
    return bound.details;
  }, [previousInstanceDetails, previousSameTemplateEntry, activeIdentity.patientId]);

  const previousFields = useMemo(() => new Map(
    previousTrendDetails?.sections.flatMap((section) => section.fields.map((field) => [field.field_key, field])) ?? [],
  ), [previousTrendDetails]);
  const previousDate = previousSameTemplateEntry?.created_at
    ? new Date(previousSameTemplateEntry.created_at).toLocaleDateString(language, { day: 'numeric', month: 'short' })
    : null;

  function focusAdjacentResult(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== 'Enter' || event.nativeEvent.isComposing || event.ctrlKey || event.metaKey || event.altKey) return;
    event.preventDefault();
    event.stopPropagation();
    const editor = event.currentTarget.closest('.lab-result-editor');
    const editableResults = Array.from(editor?.querySelectorAll<HTMLElement>('[data-lab-result-input]:not(:disabled)') ?? []);
    const index = editableResults.indexOf(event.currentTarget);
    editableResults[index + (event.shiftKey ? -1 : 1)]?.focus();
  }

  return (
    <div className="lab-result-editor">
      {activeInstance.sections.map((section, sectionIndex) => {
        const isCollapsed = collapsedSections.has(section.key);
        const sectionId = `${editorId}-${sectionIndex}`;
        return (
          <div key={section.key} className="lab-result-section">
            <button
              type="button"
              className="lab-result-section-toggle"
              onClick={() => onToggleSection(section.key)}
              aria-expanded={!isCollapsed}
              aria-controls={sectionId}
            >
              {section.title || section.key}
              {isCollapsed ? <ChevronRight size={14} aria-hidden="true" /> : <ChevronDown size={14} aria-hidden="true" />}
            </button>
            <div id={sectionId} hidden={isCollapsed} className="lab-result-fields">
              {!isCollapsed && section.fields.map((field, fieldIndex) => {
                const inputId = `${sectionId}-${fieldIndex}`;
                const currentValue = draftValues[field.field_key] ?? '';
                const commentKey = `${field.field_key}__comment`;
                const absenceKey = `${field.field_key}__absence_reason`;
                const currentComment = draftValues[commentKey] ?? '';
                const absenceReason = draftValues[absenceKey] ?? '';
                const hasDetails = Boolean(currentComment || absenceReason);
                const choiceOptions = field.choice_options || [];
                const hasNumericInput = field.value_type === 'numeric';
                const numericFormatInvalid = hasNumericInput && currentValue.trim() !== ''
                  && !NUMERIC_INPUT_FORMAT.test(currentValue.trim());
                const canRecordAbsence = field.evaluation_status != null;
                const isValueDirty = currentValue !== (acceptedValues?.[field.field_key] ?? extractFieldValue(field))
                  || absenceReason !== (field.absence_reason ?? '');
                const instrumentFlags = field.instrument_flags ?? [];
                const showInstrumentFlags = !isValueDirty && instrumentFlags.length > 0;
                const threshold = formatThreshold(field.resolved_flag_meta);
                const previous = previousFields.get(field.field_key);
                const previousValue = previous?.value_display || (previous ? extractFieldValue(previous) : '');
                const previousMethod = previous?.method_code || previous?.evaluation_snapshot?.method_code;
                const currentMethod = field.method_code || field.evaluation_snapshot?.method_code;
                const previousUnit = previous?.unit_code || previous?.unit;
                const currentUnit = field.unit_code || field.unit;
                const comparable = (previousUnit ?? '') === (currentUnit ?? '')
                  && (previousMethod ?? '') === (currentMethod ?? '')
                  && (!previous?.analyte_code || !field.analyte_code || previous.analyte_code === field.analyte_code);
                const descriptionIds = [
                  field.required && `${inputId}-required`,
                  `${inputId}-reference`,
                  `${inputId}-assessment`,
                  showInstrumentFlags && `${inputId}-instrument-flags`,
                  numericFormatInvalid && `${inputId}-error`,
                ].filter(Boolean).join(' ');
                const inputProps = {
                  id: inputId,
                  className: 'macos-input',
                  'aria-label': `${t('workbench.result_label')}: ${field.label}`,
                  'aria-describedby': descriptionIds,
                  'data-lab-result-input': '',
                  value: currentValue,
                  onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
                    onUpdateField(field.field_key, event.target.value);
                    if (absenceReason && event.target.value) onUpdateField(absenceKey, '');
                  },
                  disabled: !canEditActiveInstance,
                };
                return (
                  <div key={field.field_key} className="lab-result-row">
                    <div className="lab-result-name">
                      <label htmlFor={inputId}>{field.label}</label>
                      {field.required && <span id={`${inputId}-required`} className="lab-result-required">{t('content.field_required')}</span>}
                    </div>
                    <div className="lab-result-input">
                      {field.value_type === 'choice' && choiceOptions.length > 0 ? (
                        <select {...inputProps}>
                          <option value="">{t('workbench.select_value')}</option>
                          {currentValue && !choiceOptions.includes(currentValue) && <option value={currentValue}>{currentValue}</option>}
                          {choiceOptions.map((option, index) => {
                            const code = field.choice_option_codes?.[index];
                            return <option key={option} value={option}>{code ? t(`workbench.result_${code}`) : option}</option>;
                          })}
                        </select>
                      ) : field.value_type === 'multiline' ? (
                        <textarea {...inputProps} rows={3} />
                      ) : (
                        <Input
                          {...inputProps}
                          type="text"
                          autoComplete="off"
                          error={numericFormatInvalid}
                          title={hasNumericInput ? t('workbench.numeric_example') : undefined}
                          onKeyDown={focusAdjacentResult}
                        />
                      )}
                      {numericFormatInvalid && (
                        <span id={`${inputId}-error`} className="lab-result-error">{t('workbench.numeric_example')}</span>
                      )}
                    </div>
                    <div className="lab-result-unit">{field.unit || '—'}</div>
                    <div id={`${inputId}-reference`} className="lab-result-reference">
                      <span>{field.reference_text || t('workbench.norm_not_set')}</span>
                      {threshold && <span>{t('workbench.threshold_label')} {threshold}</span>}
                    </div>
                    <div className="lab-result-assessment">
                      {isValueDirty ? (
                        <Badge id={`${inputId}-assessment`} variant="outline" style={assessmentBadgeStyle} title={t('workbench.flag_unsaved_title')}>
                          {t('workbench.flag_unsaved')}
                        </Badge>
                      ) : (
                        <Badge id={`${inputId}-assessment`} style={assessmentBadgeStyle} variant={flagVariant(field.interpretation || field.resolved_flag || '', field.resolved_flag_severity ?? null)}>
                          {t(getEvaluationLabelKey(field))}
                        </Badge>
                      )}
                      {showInstrumentFlags && (
                        <p id={`${inputId}-instrument-flags`} className="lab-result-instrument-flags">
                          {t('workbench.instrument_flags', { codes: instrumentFlags.join(', ') })}
                        </p>
                      )}
                    </div>
                    <div className="lab-result-previous">
                      {previousValue && comparable ? (
                        <span title={t('workbench.previous_result')}>
                          {t('workbench.previous_result')} {previousValue}{previous?.unit ? ` ${previous.unit}` : ''}{previousDate ? ` (${previousDate})` : ''}
                        </span>
                      ) : previousValue ? t('workbench.previous_not_comparable') : '—'}
                    </div>
                    {(canEditActiveInstance || hasDetails) && (
                      <details className="lab-result-details">
                        <summary
                          aria-label={`${t('workbench.comment_label')}: ${field.label}`}
                          aria-describedby={hasDetails ? `${inputId}-details-state` : undefined}
                        >
                          {t('workbench.comment_label')}
                          {hasDetails && <>
                            <span aria-hidden="true"> •</span>
                            <span id={`${inputId}-details-state`} className="sr-only">{t('workbench.result_details_available')}</span>
                          </>}
                        </summary>
                        <label>
                          {t('workbench.comment_label')}
                          <Input
                            type="text"
                            value={currentComment}
                            onChange={(event) => onUpdateField(commentKey, event.target.value)}
                            disabled={!canEditActiveInstance}
                            aria-label={`${t('workbench.comment_label')}: ${field.label}`}
                          />
                        </label>
                        {canRecordAbsence && (
                          <label>
                            {t('workbench.result_absence')}
                            <Input
                              type="text"
                              value={absenceReason}
                              maxLength={500}
                              onChange={(event) => {
                                onUpdateField(absenceKey, event.target.value);
                                if (currentValue && event.target.value) onUpdateField(field.field_key, '');
                              }}
                              disabled={!canEditActiveInstance}
                              aria-label={`${t('workbench.result_absence')}: ${field.label}`}
                            />
                          </label>
                        )}
                      </details>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
