import { useRef, useState } from 'react';
import type { ComponentProps, FormEvent } from 'react';
import {
  getClinicalHistory, saveClinicalEntry,
  type ClinicalEntry, type ClinicalFact, type ClinicalSource, type EMRWorkspaceData,
} from '@/api/emrWorkspace';
import { useTranslation } from '@/i18n/useTranslation';
import { Button, Input } from '../../ui/macos';

const states = {
  problem: ['active', 'resolved', 'inactive'],
  medication: ['prescribed', 'reported', 'taking', 'stopped'],
  allergy: ['active', 'inactive'],
  allergy_check: ['none_reported', 'unknown', 'not_checked'],
} as const;

const groups = ['problem', 'medication', 'allergy'] as const;
type FactKind = ClinicalFact['kind'];
type Editor = { id: string; kind: FactKind; current?: ClinicalEntry };
type Conflict =
  | { expectedVersion: number; status: 'detected' | 'loading' | 'error' }
  | { expectedVersion: number; status: 'ready'; latest: ClinicalEntry };

function ClinicalInput({ label, ...props }: ComponentProps<typeof Input> & { label: string }) {
  return <label className="emr-workspace-field">{label}<Input {...props} aria-label={label} /></label>;
}

function optionalText(form: FormData, name: string): string | null {
  return String(form.get(name) ?? '').trim() || null;
}

function readFact(kind: FactKind, form: FormData): ClinicalFact {
  const dates = { event_on: optionalText(form, 'event_on'), ended_on: optionalText(form, 'ended_on') };
  const status = form.get('status');
  const name = String(form.get('name') ?? '').trim();
  switch (kind) {
    case 'problem':
      return { ...dates, kind, name, status: status as 'active' | 'resolved' | 'inactive', code: optionalText(form, 'code') };
    case 'medication':
      return { ...dates, kind, name, status: status as 'prescribed' | 'reported' | 'taking' | 'stopped',
        dose: optionalText(form, 'dose'), regimen: optionalText(form, 'regimen') };
    case 'allergy':
      return { ...dates, kind, name, status: status as 'active' | 'inactive',
        reaction: optionalText(form, 'reaction'), severity: optionalText(form, 'severity') as 'mild' | 'moderate' | 'severe' | null };
    case 'allergy_check':
      return { ...dates, kind, status: status as 'none_reported' | 'unknown' | 'not_checked' };
  }
}

function EntryText({ entry }: { entry: ClinicalEntry }) {
  const { t, language } = useTranslation();
  const fact = entry.clinical_details;
  const details = fact.kind === 'medication' ? [fact.dose, fact.regimen]
    : fact.kind === 'allergy' ? [fact.reaction, fact.severity && t(`emr_workspace.${fact.severity}`)]
    : fact.kind === 'problem' ? [fact.code] : [];
  const dateFormat = new Intl.DateTimeFormat(language, { dateStyle: 'medium' });
  return (
    <>
      <strong>{'name' in fact ? fact.name : t('emr_workspace.allergy_check')}</strong>
      <span>{t(`emr_workspace.${fact.status}`)}</span>
      {details.filter(Boolean).map((text, index) => <span key={index}>{text}</span>)}
      {fact.event_on && <span>{t('emr_workspace.event_on')} {fact.event_on}</span>}
      {fact.ended_on && <span>{t('emr_workspace.ended_on')} {fact.ended_on}</span>}
      <small>{t(`emr_workspace.${entry.source}`)} · {t('emr_workspace.visit_number', { id: entry.visit_id })}</small>
      <small>{t('emr_workspace.entry_recorded', {
        id: entry.author_id, date: dateFormat.format(new Date(entry.recorded_at)),
      })}</small>
      <small>{entry.confirmed_at
        ? t('emr_workspace.confirmed_on', { date: dateFormat.format(new Date(entry.confirmed_at)) })
        : t('emr_workspace.unconfirmed')}</small>
    </>
  );
}

export function ClinicalSummary({
  workspace, readOnly, reload,
}: { workspace: EMRWorkspaceData; readOnly: boolean; reload: () => void }) {
  const { t } = useTranslation();
  const [editor, setEditor] = useState<Editor>();
  const [busy, setBusy] = useState(false);
  const writeInFlight = useRef(false);
  const [saveFailed, setSaveFailed] = useState(false);
  const [conflict, setConflict] = useState<Conflict>();
  const conflictRequest = useRef(0);
  const [history, setHistory] = useState<{ id: string; rows?: ClinicalEntry[]; error?: boolean }>();
  const historyRequest = useRef(0);
  const { visit, patient, clinical_entries: entries } = workspace;
  const priorCheck = entries.find(entry => entry.clinical_details.kind === 'allergy_check');
  const fact = editor?.current?.clinical_details;

  function clearEditor() {
    conflictRequest.current += 1;
    setConflict(undefined);
    setSaveFailed(false);
    setEditor(undefined);
  }

  function edit(kind: FactKind, current?: ClinicalEntry) {
    if (readOnly || writeInFlight.current || conflict) return;
    clearEditor();
    setEditor({ id: current?.entry_id ?? crypto.randomUUID(), kind, current });
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editor || readOnly || writeInFlight.current) return;
    const submitter = (event.nativeEvent as SubmitEvent).submitter;
    const keepLocal = submitter instanceof HTMLButtonElement && submitter.name === 'keep-local';
    if (conflict && (!keepLocal || conflict.status !== 'ready')) return;
    const expectedVersion = conflict?.status === 'ready' ? conflict.latest.version : (editor.current?.version ?? 0);
    const form = new FormData(event.currentTarget);
    setSaveFailed(false);
    setBusy(true);
    writeInFlight.current = true;
    try {
      await saveClinicalEntry(
        visit.id, patient.id, editor.id, expectedVersion,
        readFact(editor.kind, form), form.get('source') as ClinicalSource, form.has('confirmed'),
      );
      clearEditor();
      reload();
    } catch (error) {
      const response = (error as { response?: { status?: number; data?: { detail?: { code?: string } } } })?.response;
      if (editor.current && response?.status === 409 && response.data?.detail?.code === 'CLINICAL_ENTRY_CONFLICT') {
        setConflict({ expectedVersion, status: 'detected' });
      } else {
        setSaveFailed(true);
      }
    } finally {
      writeInFlight.current = false;
      setBusy(false);
    }
  }

  async function loadConflictingRevision() {
    if (!editor || !conflict || conflict.status === 'loading' || writeInFlight.current) return;
    const { expectedVersion } = conflict;
    const sequence = ++conflictRequest.current;
    setSaveFailed(false);
    setConflict({ expectedVersion, status: 'loading' });
    try {
      const rows = await getClinicalHistory(visit.id, patient.id, editor.id);
      const latest = rows.filter(row => row.entry_id === editor.id
        && row.clinical_details.kind === editor.kind && row.version > expectedVersion)
        .sort((first, second) => second.version - first.version)[0];
      if (conflictRequest.current !== sequence) return;
      setConflict(latest ? { expectedVersion, status: 'ready', latest } : { expectedVersion, status: 'error' });
    } catch {
      if (conflictRequest.current === sequence) setConflict({ expectedVersion, status: 'error' });
    }
  }

  async function viewHistory(id: string) {
    const sequence = ++historyRequest.current;
    setHistory({ id });
    try {
      const rows = await getClinicalHistory(visit.id, patient.id, id);
      if (historyRequest.current === sequence) setHistory({ id, rows });
    } catch {
      if (historyRequest.current === sequence) setHistory({ id, error: true });
    }
  }

  function renderEntry(entry: ClinicalEntry) {
    return (
      <li key={entry.entry_id} className="emr-workspace-entry">
        <EntryText entry={entry} />
        <div className="emr-workspace-controls">
          {!readOnly && <Button type="button" size="small" variant="outline" disabled={Boolean(conflict)}
            onClick={() => edit(entry.clinical_details.kind, entry)}>
            {t('emr_workspace.edit')}
          </Button>}
          {entry.version > 1 && <Button type="button" size="small" variant="ghost" onClick={() => void viewHistory(entry.entry_id)}>
            {t('emr_workspace.entry_history')}
          </Button>}
        </div>
        {history?.id === entry.entry_id && (
          <div>
            {history.error && <p role="alert">{t('emr_workspace.load_error')}</p>}
            {!history.error && !history.rows && <p role="status">{t('emr_workspace.loading')}</p>}
            {history.rows && <ol className="emr-workspace-list">
              {history.rows.map(row => <li key={row.version} className="emr-workspace-entry">
                <small>{t('emr_workspace.version', { version: row.version })}</small>
                <EntryText entry={row} />
              </li>)}
            </ol>}
            <Button type="button" size="small" variant="ghost" onClick={() => {
              historyRequest.current += 1;
              setHistory(undefined);
            }}>{t('misc.cancel')}</Button>
          </div>
        )}
      </li>
    );
  }

  return (
    <section aria-label={t('emr_workspace.summary')}>
      <h3>{t('emr_workspace.summary')}</h3>
      <p className="emr-workspace-allergy">{t('emr_workspace.allergy')}. {t(`emr_workspace.${workspace.allergy_state}`)}</p>
      {groups.map(kind => {
        const rows = entries.filter(entry => entry.clinical_details.kind === kind);
        const active = rows.filter(entry => !['resolved', 'inactive', 'stopped'].includes(entry.clinical_details.status));
        const inactive = rows.filter(entry => !active.includes(entry));
        return (
          <section key={kind} className="emr-workspace-group">
            <div className="emr-workspace-line">
              <h4>{t(`emr_workspace.${kind}`)}</h4>
              {!readOnly && <Button type="button" variant="ghost" size="small" disabled={Boolean(conflict)}
                aria-label={t('emr_workspace.add_for', { category: t(`emr_workspace.${kind}`) })}
                onClick={() => edit(kind)}>{t('emr_workspace.add')}</Button>}
            </div>
            {active.length ? <ul className="emr-workspace-list">{active.map(renderEntry)}</ul> : <p>{t('emr_workspace.no_entries')}</p>}
            {inactive.length > 0 && <details>
              <summary>{t('emr_workspace.inactive_history')}</summary>
              <ul className="emr-workspace-list">{inactive.map(renderEntry)}</ul>
            </details>}
            {kind === 'allergy' && (
              <>
                {priorCheck && <ul className="emr-workspace-list">{renderEntry(priorCheck)}</ul>}
                {!readOnly && !priorCheck && <Button type="button" size="small" disabled={Boolean(conflict)}
                  onClick={() => edit('allergy_check')}>
                  {t('emr_workspace.allergy_check')}
                </Button>}
              </>
            )}
          </section>
        );
      })}
      {(patient.legacy_allergies || patient.legacy_conditions) && (
        <details className="emr-workspace-group">
          <summary>{t('emr_workspace.legacy_text')}</summary>
          {patient.legacy_allergies && <p><strong>{t('emr_workspace.allergy')}</strong> {patient.legacy_allergies}</p>}
          {patient.legacy_conditions && <p><strong>{t('emr_workspace.problem')}</strong> {patient.legacy_conditions}</p>}
        </details>
      )}
      {editor && (
        <form key={editor.id} className="emr-workspace-form" onSubmit={event => void save(event)}>
          <h4>{t(`emr_workspace.${editor.kind}`)}</h4>
          <fieldset disabled={readOnly || busy}>
            {editor.kind !== 'allergy_check' && <ClinicalInput autoFocus name="name" label={t('emr_workspace.name')}
              maxLength={240} required defaultValue={fact && 'name' in fact ? fact.name : ''} />}
            <label>{t('emr_workspace.status')}
              <select name="status" defaultValue={fact?.status}>
                {states[editor.kind].map(status => <option key={status} value={status}>{t(`emr_workspace.${status}`)}</option>)}
              </select>
            </label>
            {editor.kind === 'problem' && <ClinicalInput name="code" label={t('emr_workspace.code')}
              maxLength={32} defaultValue={fact?.kind === 'problem' ? fact.code ?? '' : ''} />}
            {editor.kind === 'medication' && <>
              <ClinicalInput name="dose" label={t('emr_workspace.dose')} maxLength={120}
                defaultValue={fact?.kind === 'medication' ? fact.dose ?? '' : ''} />
              <ClinicalInput name="regimen" label={t('emr_workspace.regimen')} maxLength={240}
                defaultValue={fact?.kind === 'medication' ? fact.regimen ?? '' : ''} />
            </>}
            {editor.kind === 'allergy' && <>
              <ClinicalInput name="reaction" label={t('emr_workspace.reaction')} maxLength={240}
                defaultValue={fact?.kind === 'allergy' ? fact.reaction ?? '' : ''} />
              <label>{t('emr_workspace.severity')}
                <select name="severity" defaultValue={fact?.kind === 'allergy' ? fact.severity ?? '' : ''}>
                  <option value="">{t('emr_workspace.unknown')}</option>
                  {['mild', 'moderate', 'severe'].map(severity => <option key={severity} value={severity}>
                    {t(`emr_workspace.${severity}`)}
                  </option>)}
                </select>
              </label>
            </>}
            <ClinicalInput name="event_on" label={t('emr_workspace.event_on')} placeholder="YYYY-MM-DD" maxLength={10}
              defaultValue={fact?.event_on ?? ''} />
            {editor.kind !== 'allergy_check' && <ClinicalInput name="ended_on" label={t('emr_workspace.ended_on')}
              placeholder="YYYY-MM-DD" maxLength={10} defaultValue={fact?.ended_on ?? ''} />}
            <label>{t('emr_workspace.source')}
              <select name="source" defaultValue={editor.current?.source ?? 'clinician'}>
                {['clinician', 'patient_report', 'legacy_verified'].map(source => (
                  <option key={source} value={source}>{t(`emr_workspace.${source}`)}</option>
                ))}
              </select>
            </label>
            <label className="emr-workspace-check">
              <input name="confirmed" type="checkbox" aria-label={t('emr_workspace.confirm_now')} />
              {t('emr_workspace.confirm_now')}
            </label>
            <div className="emr-workspace-controls">
              <Button type="submit" size="small" disabled={Boolean(conflict)}>{t('common.save')}</Button>
              <Button type="button" size="small" variant="ghost" onClick={clearEditor}>{t('misc.cancel')}</Button>
            </div>
          </fieldset>
          {busy && <p role="status">{t('emr_workspace.saving')}</p>}
          {saveFailed && <p role="alert">{t('emr_workspace.save_error')}</p>}
          {conflict && <div className="emr-workspace-group">
            <p role="alert">{t('emr_workspace.clinical_conflict_review')}</p>
            {conflict.status === 'loading' && <p role="status">{t('emr_workspace.loading')}</p>}
            {conflict.status === 'error' && <p role="alert">{t('emr_workspace.load_error')}</p>}
            {conflict.status === 'ready' ? <>
              <div className="emr-workspace-entry">
                <small>{t('emr_workspace.clinical_conflict_current', { version: conflict.latest.version })}</small>
                <EntryText entry={conflict.latest} />
              </div>
              <Button type="submit" name="keep-local" size="small" disabled={readOnly || busy}>
                {t('emr_workspace.clinical_conflict_keep_local')}
              </Button>
            </> : <Button type="button" size="small" variant="outline" disabled={busy || conflict.status === 'loading'}
              onClick={() => void loadConflictingRevision()}>{t('emr_workspace.open_version')}</Button>}
          </div>}
        </form>
      )}
    </section>
  );
}
