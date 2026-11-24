import { useRef, useState } from 'react';
import {
  getEMRWorkspace, getWorkspaceHistoryDocument,
  type EMRWorkspaceData, type FollowUp, type HistoryDocument, type HistorySummary, type TransferField,
} from '@/api/emrWorkspace';
import { useTranslation } from '@/i18n/useTranslation';
import { selectEchoMeasurements } from '@/utils/echoMeasurements';
import { Button, Input, Textarea } from '../../ui/macos';
import { ClinicalSummary } from './ClinicalSummary';

const copyFields: TransferField[] = ['complaints', 'diagnosis', 'treatment', 'recommendations'];
const followUpNotes = ['changes', 'actual_treatment', 'prior_plan_follow_through', 'new_results'] as const;

export function FollowUpEditor({
  value, disabled, onChange,
}: { value: FollowUp; disabled: boolean; onChange: (value: FollowUp) => void }) {
  const { t } = useTranslation();
  return (
    <section className="emr-workspace-visit-section" aria-label={t('emr_workspace.visit_type')}>
      <label>{t('emr_workspace.visit_type')}
        <select value={value.mode ?? ''} disabled={disabled} onChange={event => {
          onChange({ ...value, mode: (event.target.value || null) as FollowUp['mode'] });
        }}>
          <option value="">{t('emr_workspace.unselected')}</option>
          {['initial', 'follow_up', 'new_complaint'].map(mode => (
            <option key={mode} value={mode}>{t(`emr_workspace.${mode}`)}</option>
          ))}
        </select>
      </label>
      {(value.mode === 'follow_up' || followUpNotes.some(field => value[field])) && (
        <div className="emr-workspace-follow-up">
          {followUpNotes.map(field => <Textarea key={field} label={t(`emr_workspace.${field}`)}
            value={value[field] ?? ''} rows={2} maxLength={5000} disabled={disabled}
            onChange={event => onChange({ ...value, [field]: event.target.value })} />)}
        </div>
      )}
      {!!value.transferred_fields?.length && (
        <details open className="emr-workspace-group">
          <summary>{t('emr_workspace.transferred')}</summary>
          <ul className="emr-workspace-list">
            {value.transferred_fields.map((field, index) => (
              <li key={`${field.source_visit_id}:${field.source_version}:${field.field}`} className="emr-workspace-entry">
                <strong>{t(`emr_workspace.${field.field}`)}</strong>
                <span className="emr-workspace-document-text">{field.text}</span>
                <small>{t('emr_workspace.visit_number', { id: field.source_visit_id })} · {t('emr_workspace.version', { version: field.source_version })}</small>
                <small>{t(field.confirmed_current ? 'emr_workspace.confirmed_today' : 'emr_workspace.historical_only')}</small>
                {field.transferred_at && <small>{t('emr_workspace.entry_recorded', {
                  id: field.transferred_by, date: new Date(field.transferred_at).toLocaleString(),
                })}</small>}
                {!disabled && <Button type="button" size="small" variant="ghost" onClick={() => onChange({
                  ...value, transferred_fields: value.transferred_fields?.filter((_, item) => item !== index),
                })}>{t('emr_workspace.remove_transfer')}</Button>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

function measurement(raw: unknown): string {
  const candidate = typeof raw === 'string' || typeof raw === 'number' ? String(raw).trim() : '';
  return candidate !== '' && Number.isFinite(Number(candidate.replace(',', '.'))) ? candidate : '';
}

function measurements(item: HistorySummary) {
  const vitals = item.vitals;
  const pressure = vitals.blood_pressure && typeof vitals.blood_pressure === 'object'
    ? vitals.blood_pressure as Record<string, unknown> : {};
  const echo = selectEchoMeasurements(item.echo);
  const measurements = item.echo.measurement_metadata;
  const metadata = measurements && typeof measurements === 'object' ? measurements as Record<string, unknown> : {};
  const systolic = measurement(vitals.systolic ?? pressure.systolic);
  const diastolic = measurement(vitals.diastolic ?? pressure.diastolic);
  return {
    pressure: systolic || diastolic ? `${systolic || '—'}/${diastolic || '—'}` : '',
    pulse: measurement(vitals.pulse),
    weight: measurement(vitals.weight),
    ef: measurement(echo.ef),
    method: typeof metadata.ef_method === 'string' ? metadata.ef_method : '',
  };
}

function HistoryDetails({
  document, disabled, accept,
}: { document: HistoryDocument; disabled: boolean; accept: (fields: TransferField[], confirmed: boolean) => void }) {
  const { t } = useTranslation();
  const [chosen, setChosen] = useState<TransferField[]>([]);
  const [confirmed, setConfirmed] = useState(false);
  return (
    <div className="emr-workspace-history-document">
      <p>{t('emr_workspace.visit_number', { id: document.visit_id })} · {t('emr_workspace.version', { version: document.version })}</p>
      {copyFields.filter(field => document[field].trim()).map(field => (
        <section key={field} className="emr-workspace-group">
          <h4>{t(`emr_workspace.${field}`)}</h4>
          <p className="emr-workspace-document-text">{document[field]}</p>
          {!disabled && <label className="emr-workspace-check">
            <input type="checkbox" checked={chosen.includes(field)} onChange={event => {
              setChosen(event.target.checked ? [...chosen, field] : chosen.filter(item => item !== field));
            }} />
            {t('emr_workspace.choose_field', { field: t(`emr_workspace.${field}`) })}
          </label>}
        </section>
      ))}
      {!disabled && <>
        <label className="emr-workspace-check">
          <input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />
          {t('emr_workspace.confirm_today')}
        </label>
        <Button type="button" size="small" disabled={chosen.length === 0}
          onClick={() => { accept(chosen, confirmed); setChosen([]); }}>
          {t('emr_workspace.transfer')}
        </Button>
      </>}
    </div>
  );
}

export function WorkspaceSidePanel({
  workspace, status, readOnly, reload, followUp, onFollowUpChange,
}: {
  workspace?: EMRWorkspaceData | undefined;
  status: 'loading' | 'ready' | 'error';
  readOnly: boolean;
  reload: () => void;
  followUp: FollowUp;
  onFollowUpChange: (value: FollowUp) => void;
}) {
  const { t } = useTranslation();
  const [extra, setExtra] = useState<HistorySummary[]>([]);
  const [hasExtra, setHasExtra] = useState<boolean>();
  const [pagination, setPagination] = useState<'loading' | 'error'>();
  const [source, setSource] = useState<HistorySummary>();
  const [version, setVersion] = useState('');
  const [document, setDocument] = useState<HistoryDocument>();
  const [historyStatus, setHistoryStatus] = useState<'loading' | 'error'>();
  const [transferLimit, setTransferLimit] = useState(false);
  const selectionRequest = useRef(0);
  const headingRef = useRef<HTMLHeadingElement>(null);

  async function openHistory(item: HistorySummary, selectedVersion = item.version) {
    if (!workspace) return;
    const sequence = ++selectionRequest.current;
    setSource(item);
    setVersion(String(selectedVersion));
    setDocument(undefined);
    setHistoryStatus('loading');
    setTransferLimit(false);
    try {
      const next = await getWorkspaceHistoryDocument(workspace.visit.id, workspace.patient.id, item.visit_id, selectedVersion);
      if (selectionRequest.current !== sequence) return;
      if (next.visit_id !== item.visit_id || next.version !== selectedVersion) throw new Error('Mismatched history');
      setDocument(next);
      setHistoryStatus(undefined);
      headingRef.current?.focus();
    } catch {
      if (selectionRequest.current === sequence) setHistoryStatus('error');
    }
  }

  async function loadMore() {
    if (!workspace || pagination === 'loading') return;
    setPagination('loading');
    try {
      const page = await getEMRWorkspace(workspace.visit.id, workspace.patient.id, undefined, workspace.history.length + extra.length);
      setExtra([...extra, ...page.history]);
      setHasExtra(page.has_more_history);
      setPagination(undefined);
    } catch {
      setPagination('error');
    }
  }

  function transfer(fields: TransferField[], confirmed: boolean) {
    if (readOnly || !workspace || !document) return;
    const keep = (followUp.transferred_fields ?? []).filter(
      item => item.source_visit_id !== document.visit_id || item.source_version !== document.version || !fields.includes(item.field),
    );
    const selected = fields.map(field => ({
      field,
      source_visit_id: document.visit_id,
      source_version: document.version,
      source_patient_id: workspace.patient.id,
      source_document_id: document.id,
      text: document[field],
      confirmed_current: confirmed,
    }));
    if (keep.length + selected.length > 24) {
      setTransferLimit(true);
      return;
    }
    setTransferLimit(false);
    onFollowUpChange({ ...followUp, transferred_fields: [...keep, ...selected] });
  }

  return (
    <aside className="emr-workspace-sidebar" aria-label={t('emr_workspace.summary')}>
      {status === 'loading' && <p role="status">{t('emr_workspace.loading')}</p>}
      {status === 'error' && <div role="alert">
        <p>{t('emr_workspace.load_error')}</p>
        <Button type="button" size="small" variant="outline" onClick={reload}>{t('emr_workspace.retry')}</Button>
      </div>}
      {workspace && (
        <>
          <ClinicalSummary workspace={workspace} readOnly={readOnly} reload={reload} />
          <section className="emr-workspace-group">
            <h3>{t('emr_workspace.patient_history')}</h3>
            {workspace.history.length === 0 && <p>{t('emr_workspace.no_history')}</p>}
            <ol className="emr-workspace-list">
              {[...new Map([...workspace.history, ...extra].map(item => [item.id, item])).values()].map((item, index) => (
                <li key={item.id} className="emr-workspace-entry">
                  <Button type="button" variant="ghost" size="small" onClick={() => void openHistory(item)}>
                    {item.visit_date ?? t('emr_workspace.visit_number', { id: item.visit_id })}
                  </Button>
                  {item.complaints && <span>{item.complaints}</span>}
                  {item.diagnosis && <strong>{item.diagnosis}</strong>}
                  {index === 0 && (item.treatment || item.recommendations) && <details open>
                    <summary>{t('emr_workspace.previous_plan')}</summary>
                    {item.treatment && <p className="emr-workspace-document-text">{item.treatment}</p>}
                    {item.recommendations && <p className="emr-workspace-document-text">{item.recommendations}</p>}
                  </details>}
                </li>
              ))}
            </ol>
            {(hasExtra ?? workspace.has_more_history) && <Button type="button" size="small" variant="outline"
              disabled={pagination === 'loading'} onClick={() => void loadMore()}>
              {t(pagination === 'loading' ? 'emr_workspace.loading' : 'emr_workspace.more_history')}
            </Button>}
            {pagination === 'error' && <p role="alert">{t('emr_workspace.load_error')}</p>}
            {source && (
              <div className="emr-workspace-group">
                <h4 tabIndex={-1} ref={headingRef}>{t('emr_workspace.source_document')}</h4>
                <form onSubmit={event => { event.preventDefault(); void openHistory(source, Number(version)); }}>
                  <Input type="number" label={t('emr_workspace.document_version')} min={1} max={source.version} required
                    value={version} onChange={event => setVersion(event.target.value)} />
                  <Button type="submit" size="small" variant="outline">{t('emr_workspace.open_version')}</Button>
                  <Button type="button" size="small" variant="ghost" onClick={() => {
                    selectionRequest.current += 1;
                    setSource(undefined);
                    setDocument(undefined);
                  }}>{t('misc.cancel')}</Button>
                </form>
                {historyStatus === 'loading' && <p role="status">{t('emr_workspace.loading')}</p>}
                {historyStatus === 'error' && <p role="alert">{t('emr_workspace.history_error')}</p>}
                {transferLimit && <p role="alert">{t('emr_workspace.transfer_limit')}</p>}
                {document && <HistoryDetails key={`${document.id}:${document.version}`} document={document}
                  disabled={readOnly} accept={transfer} />}
              </div>
            )}
            <details className="emr-workspace-group">
              <summary>{t('emr_workspace.measurement_history')}</summary>
              {!workspace.history.some(item => Object.values(measurements(item)).some(Boolean)) && <p>{t('emr_workspace.no_entries')}</p>}
              <ol className="emr-workspace-list">
                {[...workspace.history, ...extra].map(item => {
                  const values = measurements(item);
                  if (!values.pressure && !values.pulse && !values.weight && !values.ef) return null;
                  return <li key={item.id} className="emr-workspace-entry">
                    <Button type="button" variant="ghost" size="small" onClick={() => void openHistory(item)}>
                      {item.visit_date ?? t('emr_workspace.visit_number', { id: item.visit_id })}
                    </Button>
                    {values.pressure && <span>{t('emr_workspace.pressure_value', { value: values.pressure })}</span>}
                    {values.pulse && <span>{t('emr_workspace.pulse_value', { value: values.pulse })}</span>}
                    {values.weight && <span>{t('emr_workspace.weight_value', { value: values.weight })}</span>}
                    {values.ef && <span>{t('emr_workspace.ef_value', { value: values.ef, method: values.method || t('emr_workspace.unknown_method') })}</span>}
                  </li>;
                })}
              </ol>
            </details>
          </section>
        </>
      )}
    </aside>
  );
}
