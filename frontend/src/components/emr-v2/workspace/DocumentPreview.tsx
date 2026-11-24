import { useEffect, useRef, useState } from 'react';
import { apiClient } from '@/api/client';
import type { EMRWorkspaceData, FollowUp } from '@/api/emrWorkspace';
import { useTranslation } from '@/i18n/useTranslation';
import { echoAdultTteFacts, echoMeasurementFacts, selectEchoMeasurements } from '@/utils/echoMeasurements';
import { Button, Modal } from '../../ui/macos';
import { emrTextValue, emrTreatmentText } from '../emrCompletion';
import { AdultTteSummary } from './AdultTteSummary';

const noteFields = [
  'complaints', 'anamnesis_morbi', 'anamnesis_vitae', 'examination', 'diagnosis',
  'treatment', 'recommendations', 'notes',
] as const;
const followUpFields = ['changes', 'actual_treatment', 'prior_plan_follow_through', 'new_results'] as const;

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function present(value: unknown): string {
  return typeof value === 'number' || typeof value === 'string' ? String(value).trim() : '';
}

export function DocumentPreview({
  visitId, patientId, patientName, workspace, version, data, signedAt, signedBy, status, dirty, onClose,
}: {
  visitId: string | number; patientId?: string | number | null; patientName?: string;
  workspace?: Pick<EMRWorkspaceData, 'patient' | 'visit'>; version?: number | null; data: Record<string, unknown>;
  signedAt?: string | null; signedBy?: number | null; status?: string; dirty: boolean; onClose: () => void;
}) {
  const { t, language } = useTranslation();
  const [amendment, setAmendment] = useState<{ key: string; summary: string | null }>();
  const [amendmentRetry, setAmendmentRetry] = useState(0);
  const [printFailed, setPrintFailed] = useState(false);
  const previewRef = useRef<HTMLElement>(null);
  const frameRef = useRef<HTMLIFrameElement | null>(null);
  const amended = status === 'amended';
  const signed = status === 'signed' || amended;
  const amendmentKey = amended && version ? `${visitId}:${version}:${amendmentRetry}` : null;
  const currentAmendment = amendment?.key === amendmentKey ? amendment : undefined;
  const canPrint = !amended || Boolean(currentAmendment?.summary);
  const dateFormat = new Intl.DateTimeFormat(language, { dateStyle: 'medium', timeStyle: 'short' });

  useEffect(() => {
    if (!amendmentKey || !version) return;
    const controller = new AbortController();
    void apiClient.get<{ change_summary?: string; change_type: string; version: number }>(`/v2/emr/${visitId}/version/${version}`, {
      signal: controller.signal, silent: true,
    }).then(response => {
      if (controller.signal.aborted) return;
      const revision = response.data;
      const summary = revision.version === version && revision.change_type === 'amended'
        ? revision.change_summary?.trim() || null : null;
      setAmendment({ key: amendmentKey, summary });
    }).catch(() => {
      if (!controller.signal.aborted) setAmendment({ key: amendmentKey, summary: null });
    });
    return () => controller.abort();
  }, [amendmentKey, visitId, version]);
  useEffect(() => () => frameRef.current?.remove(), []);

  function printPreview() {
    if (!canPrint || !previewRef.current) return;
    setPrintFailed(false);
    frameRef.current?.remove();
    const frame = window.document.createElement('iframe');
    frame.className = 'emr-workspace-print-frame';
    frame.title = t('emr_workspace.preview');
    frame.tabIndex = -1;
    frame.setAttribute('aria-hidden', 'true');
    window.document.body.appendChild(frame);
    frameRef.current = frame;
    const printWindow = frame.contentWindow;
    const printDocument = frame.contentDocument;
    if (!printWindow || !printDocument) {
      frame.remove();
      setPrintFailed(true);
      return;
    }

    printDocument.title = t('misc.emr_title');
    printDocument.documentElement.lang = language;
    const styles = printDocument.createElement('style');
    styles.textContent = '@page { margin: 12mm; } body { color: black; background: white; font: 11pt/1.45 system-ui, sans-serif; }'
      + ' h2, h3 { break-after: avoid; } p { white-space: pre-wrap; overflow-wrap: anywhere; }';
    printDocument.head.appendChild(styles);
    printDocument.body.appendChild(printDocument.importNode(previewRef.current, true));
    printWindow.addEventListener('afterprint', () => frame.remove(), { once: true });
    try {
      printWindow.focus();
      printWindow.print();
    } catch {
      frame.remove();
      setPrintFailed(true);
    }
  }

  const vitals = asRecord(data.vitals);
  const bloodPressure = asRecord(vitals.blood_pressure);
  const systolic = present(vitals.systolic ?? bloodPressure.systolic);
  const diastolic = present(vitals.diastolic ?? bloodPressure.diastolic);
  const hasVitals = [systolic, diastolic, vitals.pulse, vitals.spo2, vitals.respiratory_rate, vitals.temperature,
    vitals.height, vitals.weight].some(present);
  const specialty = asRecord(data.specialty_data);
  const echo = selectEchoMeasurements(specialty.echo);
  const echoFacts = echoMeasurementFacts(specialty.echo);
  const adultTteFacts = echoAdultTteFacts(specialty.echo);
  const ecgConclusion = present(asRecord(specialty.ecg).interpretation);
  const followUp = asRecord(data.follow_up) as FollowUp;
  const medicationData = asRecord(data.medications).list ?? data.medications;
  const medications = Array.isArray(medicationData) ? medicationData.map(asRecord) : [];

  return (
    <Modal isOpen onClose={onClose} size="large" title={t('emr_workspace.preview')} actions={<>
      <Button type="button" variant="ghost" onClick={onClose}>{t('misc.cancel')}</Button>
      <Button type="button" disabled={!canPrint} onClick={printPreview}>{t('emr_workspace.print')}</Button>
    </>}>
        <article className="emr-workspace-print" data-emr-print ref={previewRef}>
          <header>
            <h2>{t('misc.emr_title')}</h2>
            <p><strong>{workspace?.patient.full_name || patientName || t('misc.emr_patient', { id: patientId })}</strong></p>
            {workspace?.patient.birth_date && <p>{t('emr_workspace.birth_date')} {workspace.patient.birth_date}</p>}
            <p>{t('emr_workspace.visit_number', { id: visitId })} {workspace?.visit.date}</p>
            {version && !dirty && <p>{t('emr_workspace.version', { version })}</p>}
            {(dirty || !signed) && <p><strong>{t(dirty || status === 'draft'
              ? 'emr_workspace.draft_preview' : 'emr_workspace.unconfirmed_preview')}</strong></p>}
            {signed && signedAt && <p>{t('emr_workspace.signature_time', { date: dateFormat.format(new Date(signedAt)) })}
              {signedBy ? ` · №${signedBy}` : ''}</p>}
            {amended && <p><strong>{t('misc.visit_emr_status_amended')}</strong></p>}
            {currentAmendment?.summary && <p><strong>{t('emr_workspace.amendment_reason')}</strong> {currentAmendment.summary}</p>}
          </header>
          {followUp.mode && <p>{t('emr_workspace.visit_type')}. {t(`emr_workspace.${followUp.mode}`)}</p>}
          {hasVitals && <section>
            <h3>{t('emr_workspace.today_vitals')}</h3>
            {(systolic || diastolic) && <p>{t('emr_workspace.pressure_value', { value: `${systolic || '—'}/${diastolic || '—'}` })}</p>}
            {present(vitals.pulse) && <p>{t('emr_workspace.pulse_value', { value: vitals.pulse })}</p>}
            {present(vitals.spo2) && <p>SpO₂ {String(vitals.spo2)}%</p>}
            {present(vitals.respiratory_rate) && <p>{t('emr_workspace.respiratory_rate_value', { value: vitals.respiratory_rate })}</p>}
            {present(vitals.temperature) && <p>{t('emr_workspace.temperature_value', { value: vitals.temperature })}</p>}
            {present(vitals.weight) && <p>{t('emr_workspace.weight_value', { value: vitals.weight })}</p>}
            {present(vitals.height) && <p>{t('emr_workspace.height_value', { value: vitals.height })}</p>}
          </section>}
          {noteFields.map(field => {
            const content = field === 'treatment' ? emrTreatmentText(data) : emrTextValue(data[field]);
            return content.trim() && <section key={field}>
              <h3>{t(`emr_workspace.${field}`)}</h3>
              <p className="emr-workspace-document-text">{content}</p>
            </section>;
          })}
          {followUpFields.map(field => followUp[field] && <section key={field}>
            <h3>{t(`emr_workspace.${field}`)}</h3>
            <p className="emr-workspace-document-text">{followUp[field]}</p>
          </section>)}
          {!!followUp.transferred_fields?.length && <section>
            <h3>{t('emr_workspace.transferred')}</h3>
            <ul>
              {followUp.transferred_fields.map(item => <li key={`${item.source_visit_id}:${item.source_version}:${item.field}`}>
                <strong>{t(`emr_workspace.${item.field}`)} · {t('emr_workspace.visit_number', { id: item.source_visit_id })} · {t('emr_workspace.version', { version: item.source_version })}</strong>
                <p>{t(item.confirmed_current ? 'emr_workspace.confirmed_today' : 'emr_workspace.historical_only')}</p>
                <p className="emr-workspace-document-text">{item.text}</p>
              </li>)}
            </ul>
          </section>}
          {medications.some(item => present(item.name ?? item.drug)) && <section>
            <h3>{t('emr_workspace.medication')}</h3>
            <ul>{medications.filter(item => present(item.name ?? item.drug)).map((item, index) => (
              <li key={index}>{[
                item.name ?? item.drug, item.dose ?? item.dosage, item.frequency ?? item.freq, item.duration,
                item.instructions ?? item.note,
              ].map(present).filter(Boolean).join(' · ')}</li>
            ))}</ul>
          </section>}
          {(adultTteFacts.length > 0 || echoFacts.length > 0 || echo.conclusion) && <section>
            <h3>{t('misc.cs_tab_echo')}</h3>
            <AdultTteSummary facts={adultTteFacts} />
            {adultTteFacts.length > 0 && echoFacts.length > 0 &&
              <p><strong>{t('emr_workspace.echo_legacy_measurements')}</strong></p>}
            {echoFacts.map(fact => <p key={fact.key}>
              {t(`emr_workspace.echo_${fact.key}`)} {new Intl.NumberFormat(language).format(fact.value)} {fact.unit}
              {fact.method && ` · ${fact.method}`}
            </p>)}
            {echoFacts[0]?.measuredAt && <p>{t('emr_workspace.measurement_date')} {echoFacts[0].measuredAt}</p>}
            {echo.conclusion && <p className="emr-workspace-document-text">{echo.conclusion}</p>}
          </section>}
          {ecgConclusion && <section>
            <h3>{t('misc.cs_tab_ecg')}</h3>
            <p className="emr-workspace-document-text">{ecgConclusion}</p>
          </section>}
        </article>
        {amended && !canPrint && (amendmentKey && !currentAmendment
          ? <p role="status">{t('emr_workspace.loading')}</p>
          : <div role="alert">
            <p>{t('emr_workspace.load_error')}</p>
            {amendmentKey && <Button type="button" variant="outline" onClick={() => setAmendmentRetry(count => count + 1)}>
              {t('emr_workspace.retry')}
            </Button>}
          </div>)}
        {printFailed && <p role="alert">{t('emr_workspace.print_error')}</p>}
    </Modal>
  );
}
