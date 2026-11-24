import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  labOperationsApi,
  type LabCriticalTask,
  type LabImportEntry,
  type LabImportOutcome,
  type LabImportSource,
  type LabMetrics,
} from '../../api/labOperations';
import { useTranslation } from '../../i18n/useTranslation';
import tokenManager from '../../utils/tokenManager';
import { Button } from '../ui/macos';
import { getLabOperationsLabels } from './labOperationsLabels';
import { LAB_IMPORT_CSV_HEADER, parseLabImportCsv } from './utils/labImportCsv';
import './LabOperationsWorkbench.css';

type Labels = ReturnType<typeof getLabOperationsLabels>;
type ManualRow = {
  id: string;
  report: string;
  barcode: string;
  analyte: string;
  unit: string;
  value: string;
};

function emptyRow(reportId: number | null): ManualRow {
  return { id: crypto.randomUUID(), report: String(reportId ?? ''), barcode: '', analyte: '', unit: '', value: '' };
}

function manualEntries(rows: ManualRow[]): LabImportEntry[] {
  const grouped = new Map<string, LabImportEntry>();
  for (const row of rows) {
    const report = Number(row.report);
    if (!Number.isSafeInteger(report) || report <= 0 || !row.barcode.trim() ||
      !row.analyte.trim() || !row.value.trim()) throw new Error('row');
    const key = `${report}/${row.barcode.trim().toUpperCase()}`;
    const entry = grouped.get(key) ?? {
      message_id: row.id,
      report_instance_id: report,
      specimen_barcode: row.barcode.trim().toUpperCase(),
      values: [],
    };
    entry.values.push({ analyte_code: row.analyte.trim(), unit_code: row.unit.trim() || null, value_text: row.value.trim() });
    grouped.set(key, entry);
  }
  return [...grouped.values()];
}

function CriticalDesk({ labels }: { labels: Labels }) {
  const [rows, setRows] = useState<LabCriticalTask[]>([]);
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const request = new AbortController();
    void labOperationsApi.listCritical(undefined, request.signal).then((result) => {
      if (!request.signal.aborted) {
        setRows(result);
        setError(false);
      }
    }).catch(() => {
      if (!request.signal.aborted) setError(true);
    });
    return () => request.abort();
  }, [refresh]);

  async function update(id: number, action: 'assign' | 'escalate') {
    setBusy(true);
    setError(false);
    try {
      const updated = await labOperationsApi.updateCritical(id, action);
      setRows((current) => current.map((row) => row.id === id ? updated : row));
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label={labels.critical}>
      <Button variant="outline" onClick={() => setRefresh((current) => current + 1)}>{labels.refresh}</Button>
      {error && <p role="alert">{labels.requestError}</p>}
      {!error && rows.length === 0 && <p>{labels.emptyCritical}</p>}
      {rows.length > 0 && (
        <ul className="lab-operations__results">
          {rows.map((row) => (
            <li key={row.id}>
              <strong>{labels.report} #{row.report_instance_id}</strong>
              <span>{labels[row.state]}</span>
              <span>{labels.attempts} {row.attempts}</span>
              {row.available_actions.includes('assign') && (
                <Button size="small" variant="outline" disabled={busy} onClick={() => void update(row.id, 'assign')}>
                  {labels.assign}
                </Button>
              )}
              {row.available_actions.includes('escalate') && (
                <Button size="small" variant="outline" disabled={busy} onClick={() => void update(row.id, 'escalate')}>
                  {labels.escalate}
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function MetricsDesk({ labels }: { labels: Labels }) {
  const { t } = useTranslation();
  const [data, setData] = useState<LabMetrics | null>(null);
  const [days, setDays] = useState(7);
  const [error, setError] = useState(false);

  useEffect(() => {
    const request = new AbortController();
    void labOperationsApi.metrics(days, request.signal).then((result) => {
      if (!request.signal.aborted) {
        setData(result);
        setError(false);
      }
    }).catch(() => {
      if (!request.signal.aborted) setError(true);
    });
    return () => request.abort();
  }, [days]);

  const rejectionCounts = Object.entries(data?.rejected_samples_by_reason ?? {});
  return (
    <section aria-label={labels.metrics}>
      <label>
        {labels.period}
        <select value={days} onChange={(event) => {
          setData(null);
          setError(false);
          setDays(Number(event.target.value));
        }}>
          <option value={7}>7</option>
          <option value={30}>30</option>
          <option value={90}>90</option>
        </select>
      </label>
      {error && <p role="alert">{labels.requestError}</p>}
      {data && !error && (
        <>
          <dl className="lab-operations__metrics">
            {(['actionable', 'overdue', 'rejected_samples', 'held_samples', 'turnaround_pairs',
              'average_turnaround_minutes', 'released_corrections', 'communications_open'] as const).map((metric) => (
                <div key={metric}><dt>{labels[metric]}</dt><dd>{data[metric] ?? '—'}</dd></div>
            ))}
          </dl>
          {rejectionCounts.length > 0 && (
            <dl className="lab-operations__metrics" aria-label={labels.rejectionReasons}>
              {rejectionCounts.map(([reason, count]) => (
                <div key={reason}><dt>{t(`labWorkspace.rejection_${reason}`)}</dt><dd>{count}</dd></div>
              ))}
            </dl>
          )}
        </>
      )}
    </section>
  );
}

interface LabOperationsWorkbenchProps {
  orderId: number | null;
  reportId: number | null;
  onQueueChanged: () => Promise<void>;
}

export default function LabOperationsWorkbench({ reportId, onQueueChanged }: LabOperationsWorkbenchProps) {
  const { language } = useTranslation();
  const labels = getLabOperationsLabels(language);
  const [tab, setTab] = useState<LabImportSource | 'critical' | 'metrics'>('manual');
  const modes = tokenManager.getUserData()?.role === 'Admin'
    ? (['manual', 'csv', 'critical', 'metrics'] as const)
    : (['manual', 'csv', 'critical'] as const);
  const [manual, setManual] = useState<ManualRow[]>(() => [emptyRow(reportId)]);
  const [fileRows, setFileRows] = useState<LabImportEntry[]>([]);
  const fileRead = useRef(0);
  const [outcomes, setOutcomes] = useState<LabImportOutcome[]>([]);
  const [prepared, setPrepared] = useState<LabImportEntry[]>([]);
  const [allowReplace, setAllowReplace] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<'formatError' | 'requestError' | null>(null);

  function clearPreview() {
    setPrepared([]);
    setOutcomes([]);
    setAllowReplace(false);
    setError(null);
  }

  function patchRow(id: string, field: keyof Omit<ManualRow, 'id'>, value: string) {
    clearPreview();
    setManual((rows) => rows.map((row) => row.id === id ? { ...row, [field]: value } : row));
  }

  async function chooseFile(file: File | undefined) {
    const read = ++fileRead.current;
    clearPreview();
    setFileRows([]);
    if (!file) return;
    try {
      if (file.size > 1024 * 1024) throw new Error('csv');
      const contents = await file.text();
      if (read === fileRead.current) setFileRows(parseLabImportCsv(contents));
    } catch {
      if (read === fileRead.current) setError('formatError');
    }
  }

  async function preview(event: FormEvent) {
    event.preventDefault();
    if (tab !== 'manual' && tab !== 'csv') return;
    let rows: LabImportEntry[];
    try {
      rows = tab === 'manual' ? manualEntries(manual) : fileRows;
      if (!rows.length) throw new Error('row');
    } catch {
      setError('formatError');
      return;
    }
    clearPreview();
    setBusy(true);
    try {
      const result = await labOperationsApi.importRows(tab, rows, true);
      setOutcomes(result.rows);
      setPrepared(rows);
    } catch {
      setError('requestError');
    } finally {
      setBusy(false);
    }
  }

  async function commit() {
    if (tab !== 'manual' && tab !== 'csv') return;
    const byIndex = new Map(outcomes.map((outcome) => [outcome.row_index, outcome]));
    const entries = prepared.flatMap((row, originalIndex) => {
      const outcome = byIndex.get(originalIndex);
      return outcome?.status === 'ready' && outcome.updated_at && (!outcome.existing_values || allowReplace)
        ? [{ originalIndex, row: { ...row, expected_updated_at: outcome.updated_at, replace_existing: allowReplace } }]
        : [];
    });
    if (!entries.length) return;
    setBusy(true);
    setError(null);
    try {
      const result = await labOperationsApi.importRows(tab, entries.map((entry) => entry.row), false);
      const received = new Map<number, LabImportOutcome>();
      for (const outcome of result.rows) {
        const submittedEntry = entries[outcome.row_index];
        if (submittedEntry) {
          const rowIndex = submittedEntry.originalIndex;
          received.set(rowIndex, { ...outcome, row_index: rowIndex });
        }
      }
      setOutcomes((previous) => previous.map((row) => received.get(row.row_index) ?? row));
      if (result.rows.some((row) => row.status === 'saved')) void onQueueChanged().catch(() => undefined);
    } catch {
      setError('requestError');
    } finally {
      setBusy(false);
    }
  }

  const existingCount = outcomes.reduce((count, row) => count + (row.status === 'ready' ? row.existing_values : 0), 0);

  return (
    <div className="lab-operations">
      <div className="lab-operations__actions">
        {modes.map((mode) => (
          <Button key={mode} variant={tab === mode ? 'primary' : 'outline'} aria-pressed={tab === mode}
            disabled={busy} onClick={() => { clearPreview(); setTab(mode); }}>
            {labels[mode]}
          </Button>
        ))}
      </div>
      {tab === 'critical' && <CriticalDesk labels={labels} />}
      {tab === 'metrics' && <MetricsDesk labels={labels} />}
      {(tab === 'manual' || tab === 'csv') && (
        <form onSubmit={(event) => void preview(event)} aria-busy={busy}>
          {tab === 'manual' ? (
            <>
              {manual.map((row, index) => (
                <fieldset key={row.id} className="lab-operations__row" disabled={busy}>
                  <legend>{index + 1}</legend>
                  {(['report', 'barcode', 'analyte', 'unit', 'value'] as const).map((field) => (
                    <label key={field}>
                      {labels[field]}
                      <input aria-label={`${labels[field]} ${index + 1}`} inputMode={field === 'report' ? 'numeric' : undefined}
                        required={field !== 'unit'} value={row[field]}
                        onChange={(event) => patchRow(row.id, field, event.target.value)} />
                    </label>
                  ))}
                  <Button type="button" variant="outline" disabled={manual.length < 2}
                    onClick={() => { clearPreview(); setManual((rows) => rows.filter(({ id }) => id !== row.id)); }}>
                    {labels.remove}
                  </Button>
                </fieldset>
              ))}
              <Button type="button" variant="outline" disabled={busy || manual.length >= 100}
                onClick={() => { clearPreview(); setManual((rows) => [...rows, emptyRow(reportId)]); }}>
                {labels.add}
              </Button>
            </>
          ) : (
            <div className="lab-operations__file">
              <label>{labels.csv}<input type="file" aria-label={labels.csv} accept=".csv,text/csv" disabled={busy}
                onChange={(event) => void chooseFile(event.target.files?.[0])} /></label>
              <p>{labels.csvFormat} <code>{LAB_IMPORT_CSV_HEADER}</code></p>
            </div>
          )}
          {error && <p role="alert">{labels[error]}</p>}
          {outcomes.length > 0 && (
            <ul className="lab-operations__results" aria-live="polite">
              {outcomes.map((row) => (
                <li key={row.row_index}>
                  <strong>{labels.row} {row.row_index + 1}{row.report_instance_id !== null && ` · ${labels.report} #${row.report_instance_id}`}</strong>
                  <span>{row.error_code ? (labels[row.error_code as keyof Labels] || labels.error) : labels[row.status]}</span>
                  {row.existing_values > 0 && <span>{labels.existing} {row.existing_values}</span>}
                </li>
              ))}
            </ul>
          )}
          {existingCount > 0 && (
            <label>
              <input type="checkbox" aria-label={labels.replace} checked={allowReplace} disabled={busy}
                onChange={(event) => setAllowReplace(event.target.checked)} />
              {labels.replace}
            </label>
          )}
          <div className="lab-operations__actions">
            <Button type="submit" variant="outline" disabled={busy || (tab === 'csv' && !fileRows.length)}>{labels.preview}</Button>
            <Button type="button" disabled={busy || !outcomes.some((row) => row.status === 'ready' && (!row.existing_values || allowReplace))}
              onClick={() => void commit()}>{labels.save}</Button>
          </div>
        </form>
      )}
    </div>
  );
}
