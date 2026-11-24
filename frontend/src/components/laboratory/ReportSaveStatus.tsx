import { Button } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import { hasDraftDifference, readReportDraft } from './hooks/useLabReportState';
import type { LabReportInstance, ReportDraftSnapshot } from './hooks/useLabReportState';
import { signerFieldLabels } from './labUiLabels';
import { hasLabReportAction } from './utils/labReportActions';
import './ReportEditor.css';

interface ReportSaveStatusProps {
  language: string;
  saving: boolean;
  isDirty: boolean;
  lastSavedAt: Date | null;
  failure: 'error' | 'conflict' | 'session' | null;
  comparing: boolean;
  baseline: ReportDraftSnapshot;
  current: ReportDraftSnapshot;
  comparison: LabReportInstance | null;
  onRetry: () => void;
  onCompare: () => void;
  onResolve: (keepLocal: boolean) => void;
}

interface ReportDifference {
  key: string;
  label: string;
  local: unknown;
  remote: unknown;
  overlaps: boolean;
}

export default function ReportSaveStatus({
  language, saving, isDirty, lastSavedAt, failure, comparing, baseline, current, comparison,
  onRetry, onCompare, onResolve,
}: ReportSaveStatusProps) {
  const { t } = useTranslation();
  const time = lastSavedAt?.toLocaleTimeString(language, {
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
  const status = saving ? t('workbench.save_saving')
    : failure ? t(`workbench.save_${failure}`)
      : isDirty ? t('workbench.save_changed')
        : time ? t('workbench.save_saved', { time }) : t('workbench.save_clean');

  const differences: ReportDifference[] = [];
  if (comparison) {
    const remote = readReportDraft(comparison);
    function addDifference(key: string, label: string, baseValue: unknown, local: unknown, remoteValue: unknown) {
      const localChanged = hasDraftDifference(baseValue, local);
      const remoteChanged = hasDraftDifference(baseValue, remoteValue);
      if (localChanged || remoteChanged) {
        differences.push({ key, label, local, remote: remoteValue,
          overlaps: localChanged && remoteChanged && hasDraftDifference(local, remoteValue) });
      }
    }
    function compare(key: string, label: string, part: 'values' | 'signer') {
      addDifference(`${part}-${key}`, label, baseline[part][key], current[part][key], remote[part][key]);
    }
    addDifference('study_date', t('workbench.study_date'), baseline.studyDate, current.studyDate, remote.studyDate);
    for (const field of comparison.sections.flatMap((section) => section.fields)) {
      const label = field.label ?? field.field_key;
      compare(field.field_key, label, 'values');
      compare(`${field.field_key}__comment`, `${label} · ${t('workbench.comment_label')}`, 'values');
      compare(`${field.field_key}__absence_reason`, `${label} · ${t('workbench.result_absence')}`, 'values');
    }
    for (const [key, label] of Object.entries(signerFieldLabels)) compare(key, label, 'signer');
  }

  return (
    <div className="lab-save-status" data-failure={failure ?? undefined}>
      <div className="lab-save-status-line">
        <span role="status" aria-live="polite" aria-atomic="true">
          {status}
          {time && (isDirty || saving || failure) && <> · {t('workbench.save_previous', { time })}</>}
        </span>
        {failure && failure !== 'conflict' && (
          <Button size="sm" variant="outline" onClick={onRetry} disabled={saving}>
            {t('workbench.save_retry')}
          </Button>
        )}
        {failure === 'conflict' && !comparison && (
          <Button size="sm" variant="outline" onClick={onCompare} disabled={comparing}>
            {t('workbench.save_compare')}
          </Button>
        )}
      </div>
      {comparison && (
        <div className="lab-save-comparison">
          {differences.length ? (
            <div className="lab-save-comparison-scroll">
              <table className="lab-save-comparison-table">
                <caption>{t('workbench.save_comparison')}</caption>
                <thead><tr>
                  <th scope="col">{t('workbench.save_comparison_field')}</th>
                  <th scope="col">{t('workbench.save_comparison_local')}</th>
                  <th scope="col">{t('workbench.save_comparison_server')}</th>
                </tr></thead>
                <tbody>{differences.map(({ key, label, local, remote, overlaps }) => (
                  <tr key={key}>
                    <th scope="row">{label}{overlaps && <small>{t('workbench.save_comparison_overlap')}</small>}</th>
                    <td>{String(local ?? '') || '—'}</td>
                    <td>{String(remote ?? '') || '—'}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          ) : <p>{t('workbench.save_comparison_equal')}</p>}
          <div className="lab-save-status-line">
            {hasLabReportAction(comparison, 'save_draft') && (
              <Button size="sm" variant="outline" onClick={() => onResolve(true)}>
                {t('workbench.save_keep_draft')}
              </Button>
            )}
            <Button size="sm" variant="outline" onClick={() => onResolve(false)}>
              {t('workbench.save_load_server')}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
