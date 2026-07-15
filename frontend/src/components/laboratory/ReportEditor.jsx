import PropTypes from 'prop-types';
import { Badge, Icon, Input } from '../ui/macos';
import { formatFlagLabel, formatThreshold } from './utils/labReportNormalize';
import { flagVariant } from './utils/labReportActions';
// STRAT#24: t() для i18n — field-level strings.
// STRAT#2: labToast для interactive numeric validation toasts.
import { useLabToast } from './hooks/useLabToast';
import { useTranslation } from '../../i18n/useTranslation';

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
export default function ReportEditor({
  activeInstance,
  draftValues,
  collapsedSections,
  onToggleSection,
  onUpdateField,
  canEditActiveInstance,
  reportHistory,
  notify,
}) {
  const { t } = useTranslation();
  // STRAT#2: labToast for interactive numeric validation toasts.
  const labToast = useLabToast(notify);

  function updateField(fieldKey, value) {
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
              <Icon name={isCollapsed ? 'chevron.right' : 'chevron.down'} size={14} />
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
                    {/* PR-67 / High-9: previous-result trending */}
                    {reportHistory.length > 1 && (() => {
                      const prevReport = reportHistory[1];
                      if (!prevReport?.sections) return null;
                      let prevValue = null;
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
                      const prevDate = prevReport.created_at ? new Date(prevReport.created_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }) : '';
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
                    <Badge variant={flagVariant(field.resolved_flag, field.resolved_flag_severity)}>
                      {formatFlagLabel(field)}
                    </Badge>
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

ReportEditor.propTypes = {
  activeInstance: PropTypes.object.isRequired,
  draftValues: PropTypes.object.isRequired,
  collapsedSections: PropTypes.object.isRequired,
  onToggleSection: PropTypes.func.isRequired,
  onUpdateField: PropTypes.func.isRequired,
  canEditActiveInstance: PropTypes.bool,
  reportHistory: PropTypes.array,
  notify: PropTypes.func,
};
