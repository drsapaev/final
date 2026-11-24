import { useState } from 'react';
import { Alert, Button, Input, Modal } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import { hasLabReportAction } from './utils/labReportActions';

interface LabWorkflowEvent {
  id: number;
  kind: string;
  actor_name: string;
  occurred_at: string;
  reason?: string | null;
  evidence?: { qc?: { status: string; method?: string; series_ref?: string; instrument_ref?: string } };
}

export default function ReportWorkflowPanel({
  report, canSubmit, disabled, onReview, onPrompt,
}: {
  report: Record<string, unknown>;
  canSubmit: boolean;
  disabled: boolean;
  onReview: (action: 'submit_review' | 'review') => void;
  onPrompt: (action: LabWorkflowPrompt) => void;
}) {
  const { t, language } = useTranslation();
  if (!report.managed_release) return null;
  const holds = (report.release_holds as string[] | undefined) || [];
  const events = (report.workflow_events as LabWorkflowEvent[] | undefined) || [];
  const qc = events.filter((event) => event.kind === 'qc_recorded').at(-1)?.evidence?.qc;
  const canReturnToDraft = hasLabReportAction(report, 'return_to_draft');
  const canRecordQc = hasLabReportAction(report, 'record_qc');
  const canEdit = hasLabReportAction(report, 'edit');
  const inReview = report.status === 'IN_REVIEW' || report.status === 'REVIEWED';
  const returnStep = canReturnToDraft ? 'return_to_draft' : 'request_return_to_draft';
  const nextSteps = [...new Set(holds.map((hold) => {
    switch (hold) {
      case 'published_template_required':
        return 'check_template';
      case 'specimen_required':
        return inReview ? returnStep : 'check_specimen_link';
      case 'specimen_not_accepted':
        return 'check_specimen_status';
      case 'specimen_context_ambiguous':
        return 'check_specimen_material';
      case 'specimen_result_mismatch':
        if (inReview) return returnStep;
        return canEdit ? 'match_measurement' : 'request_measurement_check';
      case 'qc_missing':
      case 'qc_rejected':
        if (inReview) return returnStep;
        if (!canRecordQc) return 'request_qc';
        return hold === 'qc_missing' ? 'record_qc' : 'review_qc';
      case 'review_evidence_changed':
        return returnStep;
      default:
        return null;
    }
  }))].filter((step) => step !== null);
  const guidanceLabels = {
    specimens: t('labWorkspace.specimens'),
    recordQc: t('workbench.workflow_record_qc'),
    returnToDraft: t('workbench.workflow_return_to_draft'),
  };

  return (
    <div className="lab-workflow-panel">
      {holds.length > 0 && <Alert severity="warning">
        <strong>{t('workbench.workflow_holds')}</strong>
        <ul>{holds.map((hold) => <li key={hold}>{t(`workbench.workflow_hold_${hold}`, { defaultValue: t('workbench.workflow_hold_unknown') })}</li>)}</ul>
        {nextSteps.length > 0 && <>
          <strong>{t('workbench.workflow_next_steps')}</strong>
          <ul>{nextSteps.map((step) => <li key={step}>{t(`workbench.workflow_next_${step}`, guidanceLabels)}</li>)}</ul>
        </>}
      </Alert>}
      {qc && <p>{t('workbench.workflow_qc_outcome')} · {t(`workbench.workflow_qc_${qc.status}`)}</p>}
      <div className="lab-save-status-line">
        {hasLabReportAction(report, 'submit_review') && (
          <Button disabled={disabled || !canSubmit} onClick={() => onReview('submit_review')}>{t('workbench.workflow_submit_review')}</Button>
        )}
        {hasLabReportAction(report, 'review') && (
          <Button disabled={disabled || holds.length > 0} onClick={() => onReview('review')}>{t('workbench.workflow_review')}</Button>
        )}
        {canReturnToDraft && (
          <Button variant="outline" disabled={disabled} onClick={() => onPrompt('return_to_draft')}>{t('workbench.workflow_return_to_draft')}</Button>
        )}
        {canRecordQc && (
          <Button variant="outline" disabled={disabled} onClick={() => onPrompt('record_qc')}>{t('workbench.workflow_record_qc')}</Button>
        )}
      </div>
      {events.length > 0 && <details>
        <summary>{t('workbench.workflow_history')}</summary>
        <ol>{events.map((event) => (
          <li key={event.id}>
            {t(`workbench.workflow_event_${event.kind}`)} · {event.actor_name} · {new Date(event.occurred_at).toLocaleString(language)}
            {event.reason && <p>{event.reason}</p>}
          </li>
        ))}</ol>
      </details>}
    </div>
  );
}

export type LabWorkflowPrompt = 'revise' | 'return_to_draft' | 'record_qc';

type QCStatus = 'accepted' | 'rejected' | 'not_applicable';

export interface LabWorkflowDetails {
  status?: QCStatus;
  reason: string;
  method?: string;
  instrument_ref?: string;
  series_ref?: string;
}

export function ReportWorkflowDialog({
  action, saving, onClose, onSubmit,
}: {
  action: LabWorkflowPrompt;
  saving: boolean;
  onClose: () => void;
  onSubmit: (details: LabWorkflowDetails) => void;
}) {
  const { t } = useTranslation();
  const [reason, setReason] = useState('');
  const [status, setStatus] = useState<QCStatus | ''>('');
  const [method, setMethod] = useState('');
  const [series, setSeries] = useState('');
  const [instrument, setInstrument] = useState('');
  const isQC = action === 'record_qc';
  const requiresReason = !isQC || status === 'not_applicable' || status === 'rejected';
  const requiresSeries = isQC && status !== '' && status !== 'not_applicable';
  const canSubmit = (!isQC || status !== '') && (!requiresReason || Boolean(reason.trim()))
    && (!requiresSeries || Boolean(method.trim() && series.trim()));
  const title = action === 'revise' ? t('confirm.revise_title') : t(`workbench.workflow_${action}`);

  return (
    <Modal isOpen title={title} onClose={saving ? undefined : onClose} size="small" closeOnEscape={!saving} closeOnBackdrop={!saving}>
      <form className="lab-workflow-form" onSubmit={(event) => {
        event.preventDefault();
        if (!canSubmit || saving) return;
        onSubmit({
          reason: reason.trim(),
          ...(status ? { status } : {}),
          ...(requiresSeries ? { method: method.trim(), series_ref: series.trim(), instrument_ref: instrument.trim() || undefined } : {}),
        });
      }}>
        {action === 'revise' && <p>{t('confirm.revise_message')} {t('confirm.revise_description')}</p>}
        {isQC && (
          <label>
            {t('workbench.workflow_qc_outcome')}
            <select className="macos-input" value={status} required disabled={saving} onChange={(event) => setStatus(event.target.value as QCStatus | '')}>
              <option value="">{t('workbench.select_value')}</option>
              <option value="accepted">{t('workbench.workflow_qc_accepted')}</option>
              <option value="rejected">{t('workbench.workflow_qc_rejected')}</option>
              <option value="not_applicable">{t('workbench.workflow_qc_not_applicable')}</option>
            </select>
          </label>
        )}
        {requiresSeries && (
          <>
            <label>{t('workbench.workflow_qc_method')}<Input value={method} disabled={saving} required maxLength={100} onChange={(event) => setMethod(event.target.value)} /></label>
            <label>{t('workbench.workflow_qc_series')}<Input value={series} disabled={saving} required maxLength={100} onChange={(event) => setSeries(event.target.value)} /></label>
            <label>{t('workbench.workflow_qc_instrument')}<Input value={instrument} disabled={saving} maxLength={100} onChange={(event) => setInstrument(event.target.value)} /></label>
          </>
        )}
        <label>
          {t('workbench.workflow_reason')}
          <textarea className="macos-input" aria-label={t('workbench.workflow_reason')} value={reason} maxLength={1000} required={requiresReason} disabled={saving} onChange={(event) => setReason(event.target.value)} />
        </label>
        <div className="lab-save-status-line">
          <Button type="button" variant="outline" disabled={saving} onClick={onClose}>{t('confirm.cancel')}</Button>
          <Button type="submit" variant="primary" disabled={saving || !canSubmit}>
            {action === 'revise' ? t('confirm.revise_confirm') : title}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
