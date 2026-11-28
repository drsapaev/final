import { useState } from 'react';
import type { WorkspaceLabValue } from '@/api/emrWorkspace';
import { useTranslation } from '@/i18n/useTranslation';
import { Button } from '../../ui/macos';

type LabVisit = { id: number; date: string | null; values: WorkspaceLabValue[] };

interface TrendRow {
  visitId: number;
  date: string;
  reportId: number;
  name: string;
  unit: string;
  comparison: NonNullable<WorkspaceLabValue['comparison']>;
}

function getTrends(visits: LabVisit[]) {
  const groups = new Map<string, TrendRow[]>();
  for (const { id, values } of visits) {
    for (const { instance_id, name, unit, comparison } of values) {
      const date = comparison?.observed_on;
      if (!date || !comparison?.key || !comparison.value.trim() || !unit?.trim()) continue;
      const row = { visitId: id, date, reportId: instance_id, name, unit, comparison };
      const group = groups.get(comparison.key);
      if (group) group.push(row);
      else groups.set(comparison.key, [row]);
    }
  }

  return [...groups.entries()]
    .filter(([, rows]) => new Set(rows.map(row => row.visitId)).size >= 2
      && new Set(rows.map(row => row.date)).size === rows.length)
    .map(([key, rows]) => ({ key, rows: rows.sort((first, second) => (
      first.date.localeCompare(second.date) || first.visitId - second.visitId || first.reportId - second.reportId
    )) }));
}

export function LabTrendPanel({ visits, onOpenReport }: {
  visits: LabVisit[];
  onOpenReport: (id: number) => void;
}) {
  const { t } = useTranslation();
  const [choice, setChoice] = useState('');
  const [confirmed, setConfirmed] = useState<string>();
  const trends = getTrends(visits);
  const selected = trends.find(trend => trend.key === choice);
  const selection = selected && JSON.stringify([selected.key, selected.rows]);

  if (trends.length === 0) {
    return visits.some(visit => visit.values.length > 0)
      ? <p role="status">{t('emr_workspace.lab_trend_no_comparable')}</p>
      : null;
  }

  const options = trends.map(({ key, rows: [{ name, unit, comparison }] }) => ({
    key,
    label: `${name} (${unit}) · ${comparison.template_name} · ${t('emr_workspace.version', { version: comparison.template_version })}`,
    fieldKey: comparison.field_key,
  }));
  const labelCounts = new Map<string, number>();
  for (const { label } of options) labelCounts.set(label, (labelCounts.get(label) ?? 0) + 1);

  return (
    <section className="emr-workspace-group" aria-label={t('emr_workspace.lab_trends')}>
      <h4>{t('emr_workspace.lab_trends')}</h4>
      <label className="emr-workspace-field">
        {t('emr_workspace.lab_trend_measurement')}
        <select value={selected?.key ?? ''} onChange={event => {
          setChoice(event.target.value);
          setConfirmed(undefined);
        }}>
          <option value="">{t('emr_workspace.unselected')}</option>
          {options.map(({ key, label, fieldKey }) => (
            <option key={key} value={key}>
              {label}{fieldKey && (labelCounts.get(label) ?? 0) > 1 && ` · ${fieldKey}`}
            </option>
          ))}
        </select>
      </label>
      {selected && <div className="emr-workspace-follow-up">
        <ul className="emr-workspace-list">
          {selected.rows.map(({ visitId, date, reportId, unit, comparison }, index) => (
            <li key={`${visitId}:${reportId}:${index}`} className="emr-workspace-entry">
              <span><time dateTime={date}>{date}</time> · {t('emr_workspace.visit_number', { id: visitId })}</span>
              {confirmed === selection && <strong>{comparison.value} {unit}</strong>}
              <Button type="button" size="small" variant="ghost" onClick={() => onOpenReport(reportId)}>
                {t('emr_workspace.lab_report', { id: reportId })}
              </Button>
            </li>
          ))}
        </ul>
        <label className="emr-workspace-check">
          <input type="checkbox" aria-label={t('emr_workspace.lab_trend_confirm_comparable')} checked={confirmed === selection}
            onChange={event => setConfirmed(event.target.checked ? selection : undefined)} />
          {t('emr_workspace.lab_trend_confirm_comparable')}
        </label>
      </div>}
    </section>
  );
}
