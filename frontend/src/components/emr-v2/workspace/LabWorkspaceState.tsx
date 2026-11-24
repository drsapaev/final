import { useRef, useState } from 'react';
import { reviewLabVersion, type WorkspaceLabReport, type WorkspaceLabs } from '@/api/emrWorkspace';
import { useTranslation } from '@/i18n/useTranslation';
import { Button, Input } from '../../ui/macos';

function useLabLabels() {
  const { t } = useTranslation();
  return {
    t,
    status: (value: string) => t(`emr_workspace.lab_${value}`, { defaultValue: value }),
  };
}

export function LabWorkspaceState({
  labs, error, retry,
}: { labs?: WorkspaceLabs; error: boolean; retry: () => void }) {
  const { t, status } = useLabLabels();
  if (error && !labs) return <div role="alert">
    <p>{t('emr_workspace.load_error')}</p>
    <Button type="button" size="small" variant="outline" onClick={retry}>{t('emr_workspace.retry')}</Button>
  </div>;
  if (!labs) return <p role="status">{t('emr_workspace.loading')}</p>;
  const pendingOrders = labs.orders.filter(order =>
    order.status === 'ordered' || order.status === 'in_progress'
    || order.reports.some(report => !report.finalized_at));
  const pendingUnlinked = labs.unlinked_reports.filter(report => !report.finalized_at);
  const renderReport = (report: WorkspaceLabReport) => (
    <li key={report.id}>
      {report.template_name} · {t('emr_workspace.lab_report', { id: report.id })} · {status(report.status)}
      {report.supersedes_instance_id && <> · {t('emr_workspace.lab_supersedes', { id: report.supersedes_instance_id })}</>}
    </li>
  );
  return (
    <section className="emr-workspace-visit-section" aria-label={t('emr_workspace.pending_labs')}>
      <h3>{t('emr_workspace.pending_labs')}</h3>
      {error && <div role="alert">
        <p>{t('emr_workspace.load_error')}</p>
        <Button type="button" size="small" variant="outline" onClick={retry}>{t('emr_workspace.retry')}</Button>
      </div>}
      {pendingOrders.length === 0 && pendingUnlinked.length === 0 && <p>{t('emr_workspace.no_entries')}</p>}
      <ul className="emr-workspace-list">
        {pendingOrders.map(order => <li key={order.id} className="emr-workspace-entry">
          <strong>{t('emr_workspace.lab_order', { id: order.id })} · {status(order.status)}</strong>
          <ul>{order.reports.filter(report => !report.finalized_at).map(renderReport)}</ul>
        </li>)}
        {pendingUnlinked.map(renderReport)}
      </ul>
      {labs.executions.length > 0 && <details className="emr-workspace-group">
        <summary>{t('emr_workspace.service_executions')}</summary>
        <ul>
          {labs.executions.map(execution => <li key={execution.id}>
            {execution.service_name} · {t('emr_workspace.service_attempt', { number: execution.attempt })} · {status(execution.status)}
          </li>)}
        </ul>
      </details>}
      {labs.invoices.length > 0 && <details className="emr-workspace-group">
        <summary>{t('emr_workspace.invoice_status')}</summary>
        <ul>{labs.invoices.map(invoice => <li key={invoice.id}>№{invoice.id} · {status(invoice.status)}</li>)}</ul>
      </details>}
    </section>
  );
}

export function LabVersionReview({
  report, visitId, patientId, reviewerId, retry,
}: {
  report: WorkspaceLabReport; visitId: string | number; patientId: string | number;
  reviewerId?: string | number | null; retry: () => void;
}) {
  const { t, language } = useTranslation();
  const [nextAction, setNextAction] = useState('');
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState(false);
  const inFlight = useRef(false);
  const date = new Intl.DateTimeFormat(language, { dateStyle: 'medium', timeStyle: 'short' });
  const alreadyReviewed = report.reviews.some(review => String(review.reviewer_id) === String(reviewerId));

  async function submitReview() {
    if (inFlight.current || alreadyReviewed || !reviewerId || !report.is_current_final) return;
    inFlight.current = true;
    setFailure(false);
    setBusy(true);
    try {
      await reviewLabVersion(visitId, patientId, report.id, nextAction.trim());
      setNextAction('');
      retry();
    } catch {
      setFailure(true);
    } finally {
      setBusy(false);
      inFlight.current = false;
    }
  }

  return (
    <div className="emr-workspace-group">
      {report.supersedes_instance_id && <p>{t('emr_workspace.lab_supersedes', { id: report.supersedes_instance_id })}</p>}
      {!report.is_current_final && <p>{t('emr_workspace.lab_previous_version')}</p>}
      {report.reviews.map(review => <div key={review.reviewer_id}>
        <p>{t('emr_workspace.lab_reviewed', { id: review.reviewer_id, date: date.format(new Date(review.reviewed_at)) })}</p>
        {review.next_action && <p className="emr-workspace-document-text">{review.next_action}</p>}
      </div>)}
      {report.is_current_final && report.reviews.length === 0 && <p>{t('emr_workspace.lab_unreviewed')}</p>}
      {report.is_current_final && !alreadyReviewed && reviewerId && (
        <form onSubmit={event => { event.preventDefault(); void submitReview(); }}>
          <Input label={t('emr_workspace.lab_next_action')} value={nextAction} disabled={busy}
            maxLength={500} onChange={event => setNextAction(event.target.value)} />
          <Button type="submit" size="small" variant="outline" disabled={busy}>
            {t(busy ? 'emr_workspace.saving' : 'emr_workspace.lab_review')}
          </Button>
        </form>
      )}
      {failure && <p role="alert">{t('emr_workspace.save_error')}</p>}
    </div>
  );
}
