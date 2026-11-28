import { useEffect, useRef, useState } from 'react';
import {
  getWorkspacePrescription, issueWorkspacePrescription, type ReviewedPrescriptionText, type WorkspacePrescription,
} from '@/api/emrWorkspace';
import { useTranslation } from '@/i18n/useTranslation';
import { Button, Modal, Textarea } from '../../ui/macos';

interface PrescriptionReview {
  rowVersion: number;
  text: ReviewedPrescriptionText;
}

export function PrescriptionAction({
  visitId, patientId, rowVersion, hasMedications, isCurrentSaved, readOnly,
}: {
  visitId: number; patientId: number; rowVersion: number;
  hasMedications: boolean; isCurrentSaved: boolean; readOnly: boolean;
}) {
  const { t } = useTranslation();
  const [prescription, setPrescription] = useState<WorkspacePrescription | null>();
  const [review, setReview] = useState<PrescriptionReview | null>(null);
  const [error, setError] = useState<
    'load_error' | 'prescription_not_issued' | 'prescription_incomplete' | 'prescription_text_review_required'
  >();
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState(false);
  const issuing = useRef(false);
  const canIssue = !readOnly && isCurrentSaved && !busy && !loading && prescription !== undefined;
  const reviewVersionChanged = review !== null && review.rowVersion !== rowVersion;

  useEffect(() => {
    const controller = new AbortController();
    void getWorkspacePrescription(visitId, patientId, controller.signal).then(
      data => {
        if (controller.signal.aborted) return;
        if (data && (data.visit_id !== visitId || data.review_token === undefined)) {
          setPrescription(undefined);
          setError('load_error');
        } else {
          setPrescription(data);
        }
        setLoading(false);
      },
      () => {
        if (!controller.signal.aborted) {
          setPrescription(undefined);
          setError('load_error');
          setLoading(false);
        }
      },
    );
    return () => controller.abort();
  }, [visitId, patientId, reload]);

  async function issue(reviewedText?: ReviewedPrescriptionText) {
    if (issuing.current || !canIssue || reviewVersionChanged) return;
    issuing.current = true;
    setBusy(true);
    setError(undefined);
    try {
      const result = reviewedText
        ? await issueWorkspacePrescription(visitId, patientId, rowVersion, reviewedText)
        : await issueWorkspacePrescription(visitId, patientId, rowVersion);
      if (result.visit_id !== visitId || result.is_draft) throw new Error('Unconfirmed prescription');
      setPrescription(result);
      setReview(null);
    } catch (failure) {
      const response = (failure as {
        response?: { status?: number; data?: { detail?: { code?: string } } };
      })?.response;
      if (response?.status === 409 && response.data?.detail?.code === 'PRESCRIPTION_TEXT_REVIEW_REQUIRED') {
        setReview(null);
        setError('prescription_text_review_required');
        setLoading(true);
        setReload(value => value + 1);
      } else {
        setError(response?.status === 422 ? 'prescription_incomplete' : 'prescription_not_issued');
      }
    } finally {
      setBusy(false);
      issuing.current = false;
    }
  }

  function beginIssue() {
    if (!canIssue) return;
    if (!prescription?.review_token) {
      void issue();
      return;
    }
    setError(undefined);
    setReview({
      rowVersion,
      text: {
        expected_token: prescription.review_token,
        instructions: prescription.instructions ?? null,
        doctor_notes: prescription.doctor_notes ?? null,
      },
    });
  }

  function editReview(field: 'instructions' | 'doctor_notes', value: string) {
    setReview(previous => previous && { ...previous, text: { ...previous.text, [field]: value || null } });
  }

  function closeReview() {
    if (!issuing.current) setReview(null);
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
          <Button type="button" size="small" variant="outline" disabled={!canIssue}
            onClick={beginIssue}>{t(busy ? 'emr_workspace.saving' : 'emr_workspace.issue_prescription')}</Button>
        </>
      )}
      {error && (!review || readOnly) && <p role="alert">{t(`emr_workspace.${error}`)}</p>}
      {error === 'load_error' && <Button type="button" size="small" variant="ghost" onClick={() => {
        setError(undefined);
        setLoading(true);
        setReload(value => value + 1);
      }}>{t('emr_workspace.retry')}</Button>}
      {review && !readOnly && (
        <Modal
          isOpen
          title={t('emr_workspace.prescription_text_review')}
          onClose={closeReview}
          closeOnBackdrop={!busy}
          closeOnEscape={!busy}
          onKeyDown={event => { if (event.ctrlKey || event.metaKey) event.stopPropagation(); }}
          actions={<>
            <Button type="button" variant="ghost" disabled={busy} onClick={closeReview}>{t('misc.cancel')}</Button>
            <Button type="button" disabled={!canIssue || reviewVersionChanged} onClick={() => void issue(review.text)}>
              {t(busy ? 'emr_workspace.saving' : 'emr_workspace.prescription_review_confirm')}
            </Button>
          </>}
        >
          <p>{t('emr_workspace.prescription_text_review_hint')}</p>
          <label className="emr-workspace-field">
            {t('emr_workspace.prescription_instructions')}
            <Textarea rows={3} maxLength={2000} value={review.text.instructions ?? ''} readOnly={busy}
              onChange={event => editReview('instructions', event.target.value)} />
          </label>
          <label className="emr-workspace-field">
            {t('emr_workspace.prescription_doctor_notes')}
            <Textarea rows={3} maxLength={1000} value={review.text.doctor_notes ?? ''} readOnly={busy}
              onChange={event => editReview('doctor_notes', event.target.value)} />
          </label>
          {reviewVersionChanged && <p role="alert">{t('emr_workspace.prescription_review_emr_changed')}</p>}
          {error && <p role="alert">{t(`emr_workspace.${error}`)}</p>}
        </Modal>
      )}
    </section>
  );
}
