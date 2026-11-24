import { useState } from 'react';
import { Button, Input, Modal } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

export type LabWorkflowPrompt = 'revise' | 'return_to_draft' | 'record_qc';

type QCStatus = 'accepted' | 'rejected' | 'not_applicable';

export interface LabWorkflowDetails {
  status?: QCStatus;
  reason: string;
  method?: string;
  instrument_ref?: string;
  series_ref?: string;
}

export default function ReportWorkflowDialog({
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
