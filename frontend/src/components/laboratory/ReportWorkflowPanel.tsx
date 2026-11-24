import { Alert, Button } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import type { LabWorkflowPrompt } from './ReportWorkflowDialog';
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
  return (
    <div className="lab-workflow-panel">
      {holds.length > 0 && <Alert severity="warning">
        <strong>{t('workbench.workflow_holds')}</strong>
        <ul>{holds.map((hold) => <li key={hold}>{t(`workbench.workflow_hold_${hold}`, { defaultValue: t('workbench.workflow_hold_unknown') })}</li>)}</ul>
      </Alert>}
      {qc && <p>{t('workbench.workflow_qc_outcome')} · {t(`workbench.workflow_qc_${qc.status}`)}</p>}
      <div className="lab-save-status-line">
        {hasLabReportAction(report, 'submit_review') && (
          <Button disabled={disabled || !canSubmit} onClick={() => onReview('submit_review')}>{t('workbench.workflow_submit_review')}</Button>
        )}
        {hasLabReportAction(report, 'review') && (
          <Button disabled={disabled || holds.length > 0} onClick={() => onReview('review')}>{t('workbench.workflow_review')}</Button>
        )}
        {hasLabReportAction(report, 'return_to_draft') && (
          <Button variant="outline" disabled={disabled} onClick={() => onPrompt('return_to_draft')}>{t('workbench.workflow_return_to_draft')}</Button>
        )}
        {hasLabReportAction(report, 'record_qc') && (
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
