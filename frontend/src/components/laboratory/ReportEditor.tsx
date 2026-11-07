
import { Badge, Input } from '../ui/macos';
import { formatFlagLabel, formatThreshold } from './utils/labReportNormalize';
import { flagVariant } from './utils/labReportActions';
// STRAT#24: t() для i18n — field-level strings.
// STRAT#2: labToast для interactive numeric validation toasts.
import { useLabToast } from './hooks/useLabToast';
// ADR-0015: lab reporting API accessed via hook (LABEDIT-FE-001 details read).
import { useLabReporting } from '../../hooks/useLabReporting';
import { useTranslation } from '../../i18n/useTranslation';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

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
 *   - notify: parent notify callback (for labToast)
 */
interface LabReportField {
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
  value_text?: string;
}

interface LabReportSection {
  key: string;
  title?: string;
  fields: LabReportField[];
}

interface LabReportInstance {
  sections: LabReportSection[];
}

interface LabReportHistoryEntry {
  id?: string | number;
  patient_id?: string | number;
  template_id?: string | number;
  created_at?: string;
}

interface ReportEditorProps {
  activeInstance: LabReportInstance;
  draftValues: Record<string, string>;
  collapsedSections: Set<unknown>;
  onToggleSection: (sectionKey: string) => void;
  onUpdateField: (fieldKey: string, value: string) => void;
  canEditActiveInstance?: boolean;
  reportHistory?: LabReportHistoryEntry[];
  notify?: (type: string, message: string) => void;
}

export default function ReportEditor({
  activeInstance,
  draftValues,
  collapsedSections,
  onToggleSection,
  onUpdateField,
  canEditActiveInstance,
  reportHistory = [],
  notify,
}: ReportEditorProps) {
  const { t: rawT } = useTranslation(); const t = rawT;
  // STRAT#2: labToast for interactive numeric validation toasts.
  // Fallback no-op preserves runtime behavior: ReportEditor only uses the
  // interactive* methods (which call toast directly, not the notify callback).
  const labToast = useLabToast(notify ?? ((_type: string, _message: string) => {}));

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
        const shaped = details as (LabReportInstance & { patient_id?: string | number }) | null;
        // Fail-closed: only a well-shaped details DTO renders a trend.
        if (!shaped || !Array.isArray(shaped.sections)) return;
        // LABEDIT-FE-003: the details must belong to the same patient as
        // the active report — a mismatched DTO is suppressed entirely.
        if (shaped.patient_id != null && String(shaped.patient_id) !== patientKey) return;
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

  function updateField(fieldKey: string, value: string) {
    onUpdateField(fieldKey, value);
  }

  return (
    <div style={{ display: 'grid', gap: 'var(--mac-spacing-4)' }}>
      {activeInstance.sections.map((section) => {
        const isCollapsed = collapsedSections.has(section.key);
        return (
          <div key={section.key} style={{ border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-xl)', overflow: 'hidden', background: 'var(--mac-bg-primary)' }}>
            {/* PR-64 / Medium-16: collapsible section header */}
            <div
              style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', background: 'var(--mac-bg-tertiary)', fontWeight: 'var(--mac-font-weight-semibold)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', userSelect: 'none' }}
              onClick={() => onToggleSection(section.key)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.currentTarget.click(); } }}
              aria-expanded={!isCollapsed}
            >
              {section.title || section.key}
              {/* L-M-11 fix: заменены ▶/▼ (CJK punctuation) на lucide chevron icons */}
              {isCollapsed  ? <ChevronRight size={14} aria-hidden="true" /> : <ChevronDown size={14} aria-hidden="true" />}
            </div>
            {!isCollapsed && (
            <div style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', display: 'grid', gap: '10px' }}>
              {section.fields.map((field) => {
                const choiceOptions = field.choice_options || [];
                const currentValue = draftValues[field.field_key] ?? '';
                // PR-65 / Medium-15: per-field comment
                const commentKey = `${field.field_key}__comment`;
                const currentComment = draftValues[commentKey] ?? '';

                return (
                  <div
                    key={field.field_key}
                    className="lrw-field-row"
                  >
                    <div className="lrw-field-label">
                      <strong className="lrw-field-label-name">{field.label}</strong>
                      <div className="lrw-field-meta">
                        <span>{t('workbench.norm_label')}: {field.reference_text || t('workbench.norm_not_set')}</span>
                        {field.resolved_flag_meta?.matched_threshold && (
                          <span>
                            {t('workbench.threshold_label')}: {formatThreshold(field.resolved_flag_meta)}
                            {field.resolved_flag_source ? ` • ${field.resolved_flag_source}` : ''}
                          </span>
                        )}
                      </div>
                    </div>
                    {/* PR-67 / High-9 + LABEDIT-FE-001/003/004 (audit 3886 +
                        post-merge review of PR 3916): previous-result trending —
                        rendered ONLY from the identity-bound DETAILS of the
                        actual chronologically older, same-template,
                        same-patient preceding instance (the list API returns
                        summary DTOs without `sections`, so a history row can
                        never provide the previous value; the details are
                        dropped synchronously when the active report changes). */}
                    {previousTrendDetails && (() => {
                      const prevReport = previousTrendDetails;
                      const prevEntryCreatedAt = previousSameTemplateEntry?.created_at;
                      let prevValue: string | null = null;
                      for (const sec of prevReport.sections) {
                        for (const f of (sec.fields || [])) {
                          if (f.field_key === field.field_key && f.value_text) {
                            prevValue = f.value_text;
                            break;
                          }
                        }
                        if (prevValue) break;
                      }
                      if (!prevValue) return null;
                      const prevDate = prevEntryCreatedAt ? new Date(prevEntryCreatedAt).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }) : '';
                      return (
                        <span style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', whiteSpace: 'nowrap' }}>
                          ↗ {prevValue} {prevDate && `(${prevDate})`}
                        </span>
                      );
                    })()}
                    {field.value_type === 'choice' && choiceOptions.length > 0 ? (
                      <select
                        className="macos-input"
                        value={currentValue}
                        onChange={(event) => updateField(field.field_key, event.target.value)}
                        disabled={!canEditActiveInstance}
                      >
                        <option value="">{t('workbench.select_value')}</option>
                        {currentValue && !choiceOptions.includes(currentValue) && (
                          <option value={currentValue}>{currentValue}</option>
                        )}
                        {choiceOptions.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    ) : field.value_type === 'multiline' ? (
                      <textarea
                        className="macos-input"
                        aria-label={`${t('workbench.result_label')}: ${field.label}`}
                        rows={3}
                        value={currentValue}
                        onChange={(event) => updateField(field.field_key, event.target.value)}
                        disabled={!canEditActiveInstance}
                      />
                    ) : (
                      <Input
                        className="macos-input"
                        aria-label={`${t('workbench.result_label')}: ${field.label}`}
                        value={currentValue}
                        onChange={(event) => updateField(field.field_key, event.target.value)}
                        disabled={!canEditActiveInstance}
                        type={field.value_type === 'numeric' ? 'number' : 'text'}
                        inputMode={field.value_type === 'numeric' ? 'decimal' : undefined}
                        step={field.value_type === 'numeric' ? 'any' : undefined}
                        onBlur={(event) => {
                          if (field.value_type !== 'numeric') return;
                          const val = event.target.value;
                          if (val === '' || val === null || val === undefined) return;
                          const parsed = parseFloat(val);
                          if (isNaN(parsed)) {
                            const previousValue = draftValues[field.field_key] || '';
                            labToast.interactiveError(
                              `${t('errors.invalid_numeric')}: "${val}". ${t('errors.field_restored')}`,
                              {
                                autoClose: 6000,
                                onClick: () => {
                                  updateField(field.field_key, previousValue);
                                },
                              }
                            );
                            updateField(field.field_key, previousValue);
                            return;
                          }
                          // PR-56: out-of-range confirmation
                          const threshold = field.resolved_flag_meta?.matched_threshold;
                          if (threshold && threshold.value) {
                            const thresholdVal = parseFloat(threshold.value);
                            if (!isNaN(thresholdVal)) {
                              const op = threshold.operator;
                              let isCritical = false;
                              if (op === 'gt' && parsed > thresholdVal) isCritical = true;
                              else if (op === 'gte' && parsed >= thresholdVal) isCritical = true;
                              else if (op === 'lt' && parsed < thresholdVal) isCritical = true;
                              else if (op === 'lte' && parsed <= thresholdVal) isCritical = true;
                              if (isCritical) {
                                labToast.interactiveWarning(
                                  `⚠ ${t('workbench.critical_value')}: ${field.label} = ${parsed} ${field.unit || ''} ` +
                                  `(${t('workbench.threshold_label')}: ${op} ${thresholdVal}). ${t('workbench.check_input')}.`,
                                  { autoClose: 8000 }
                                );
                              }
                            }
                          }
                          // Check if value is outside reference_text range
                          const refText = field.reference_text || '';
                          const rangeMatch = refText.match(/(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)/);
                          if (rangeMatch) {
                            const low = parseFloat(rangeMatch[1]);
                            const high = parseFloat(rangeMatch[2]);
                            if (!isNaN(low) && !isNaN(high) && (parsed < low || parsed > high)) {
                              labToast.interactiveInfo(
                                `${t('workbench.value')} ${parsed} ${t('workbench.out_of_range')} (${low}–${high}) «${field.label}».`,
                                { autoClose: 5000 }
                              );
                            }
                          }
                        }}
                      />
                    )}
                    <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
                      {field.unit || '—'}
                    </div>
                    {(() => {
                      // LABEDIT-FE-002 (audit 3886): the persisted clinical flag
                      // describes the LAST SAVED value. While the unsaved draft
                      // differs from the persisted value, the badge must not
                      // present that flag as if it described the draft input —
                      // render an explicit unsaved marker instead (the
                      // authoritative flag returns after the backend
                      // save/refresh re-evaluates the stored report).
                      const persistedValue = field.value_text ?? '';
                      const draftValue = draftValues[field.field_key] ?? '';
                      if (draftValue !== persistedValue) {
                        return (
                          <Badge
                            variant="outline"
                            title={t('workbench.flag_unsaved_title')}
                            aria-label={t('workbench.flag_unsaved_title')}
                          >
                            {t('workbench.flag_unsaved')}
                          </Badge>
                        );
                      }
                      return (
                        <Badge variant={flagVariant(field.resolved_flag ?? '', field.resolved_flag_severity ?? null)}>
                          {formatFlagLabel(field)}
                        </Badge>
                      );
                    })()}
                    {field.required ? <Badge variant="warning">{t('content.field_required')}</Badge> : <span aria-hidden="true" />}
                    <input
                      type="text"
                      className="macos-input"
                      placeholder={t('workbench.comment_placeholder')}
                      value={currentComment}
                      onChange={(e) => updateField(commentKey, e.target.value)}
                      disabled={!canEditActiveInstance}
                      aria-label={`${t('workbench.comment_label')}: ${field.label}`}
                      style={{
                        fontSize: 'var(--mac-font-size-xs)',
                        padding: '4px 8px',
                        minWidth: '100px',
                        color: 'var(--mac-text-secondary)',
                        fontStyle: currentComment ? 'normal' : 'italic',
                      }}
                    />
                  </div>
                );
              })}
            </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

