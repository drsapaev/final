import { useEffect, useRef, useState } from 'react';
import {
  getWorkspacePrescription, issueWorkspacePrescription, type WorkspacePrescription,
} from '@/api/emrWorkspace';
import { useTranslation } from '@/i18n/useTranslation';
import { Button } from '../../ui/macos';

export function PrescriptionAction({
  visitId, patientId, rowVersion, hasMedications, isCurrentSaved, readOnly,
}: {
  visitId: number; patientId: number; rowVersion: number;
  hasMedications: boolean; isCurrentSaved: boolean; readOnly: boolean;
}) {
  const { t } = useTranslation();
  const [prescription, setPrescription] = useState<WorkspacePrescription | null>();
  const [error, setError] = useState<'load_error' | 'prescription_not_issued' | 'prescription_incomplete'>();
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState(false);
  const issuing = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    void getWorkspacePrescription(visitId, patientId, controller.signal).then(
      data => {
        if (controller.signal.aborted) return;
        if (data && data.visit_id !== visitId) {
          setError('load_error');
        } else {
          setPrescription(data);
        }
        setLoading(false);
      },
      () => {
        if (!controller.signal.aborted) {
          setError('load_error');
          setLoading(false);
        }
      },
    );
    return () => controller.abort();
  }, [visitId, patientId, reload]);

  async function issue() {
    if (issuing.current || readOnly || !isCurrentSaved) return;
    issuing.current = true;
    setBusy(true);
    setError(undefined);
    try {
      const result = await issueWorkspacePrescription(visitId, patientId, rowVersion);
      if (result.visit_id !== visitId || result.is_draft) throw new Error('Unconfirmed prescription');
      setPrescription(result);
    } catch (failure) {
      const status = (failure as { response?: { status?: number } })?.response?.status;
      setError(status === 422 ? 'prescription_incomplete' : 'prescription_not_issued');
    } finally {
      setBusy(false);
      issuing.current = false;
    }
  }

  if (!hasMedications && !prescription && !error) return null;
  return (
    <section className="emr-workspace-visit-section" aria-label={t('emr_workspace.prescription')}>
      <h3>{t('emr_workspace.prescription')}</h3>
      {loading && <p role="status">{t('emr_workspace.loading')}</p>}
      {prescription && <p role="status">{t(
        prescription.is_draft ? 'emr_workspace.prescription_draft'
          : prescription.emr_version != null ? 'emr_workspace.prescription_saved' : 'emr_workspace.prescription_legacy',
        { id: prescription.id, version: prescription.emr_version },
      )}</p>}
      {!readOnly && hasMedications && (
        <>
          {!isCurrentSaved && <p>{t('emr_workspace.prescription_save_first')}</p>}
          <Button type="button" size="small" variant="outline" disabled={!isCurrentSaved || busy || loading}
            onClick={() => void issue()}>{t(busy ? 'emr_workspace.saving' : 'emr_workspace.issue_prescription')}</Button>
        </>
      )}
      {error && <p role="alert">{t(`emr_workspace.${error}`)}</p>}
      {error === 'load_error' && <Button type="button" size="small" variant="ghost" onClick={() => {
        setError(undefined);
        setLoading(true);
        setReload(value => value + 1);
      }}>{t('emr_workspace.retry')}</Button>}
    </section>
  );
}
