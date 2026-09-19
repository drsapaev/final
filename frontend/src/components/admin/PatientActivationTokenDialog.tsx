/**
 * Staff dialog: issue a patient card activation token (Phase 0 PR-A2, PR-B).
 *
 * Consumed from /admin/patients row actions (Admin). The backend endpoint is
 * Admin|Registrar; Registrar issuance UI lands with a registrar patients
 * surface (the registrar panel is appointment-centric today).
 *
 * Two-stage dialog on purpose: reissuing REVOKES the previous token
 * (per-patient revocation index, PR-A2), so an explicit confirmation step
 * guards against accidental clicks that would invalidate a pending SMS.
 *
 * Stage 1 (confirm): patient name + warning → "Issue".
 * Stage 2 (result):   one-time display of the token (copied on click),
 *                     masked phone and TTL. Token is hash-stored server-side
 *                     and cannot be re-read afterwards.
 */
import { useState } from 'react';
import { AlertTriangle, Check, Copy, KeyRound } from 'lucide-react';
import { Alert, Button, Modal } from '../ui/macos';
import { issueActivationToken } from '../../api/patientAccess';
import type { PatientActivationTokenResult } from '../../types/domain/patientAccess';
import { useTranslation } from '../../i18n/useTranslation';
import logger from '../../utils/logger';
import type { HttpApiError } from '../../types/errors';

interface PatientActivationTokenDialogProps {
  isOpen: boolean;
  onClose: () => void;
  patient: Record<string, unknown> | null;
}

type DialogStage = 'confirm' | 'result';

const tokenBoxStyle = {
  marginTop: 12,
  padding: '12px 14px',
  borderRadius: 'var(--mac-radius-md, 10px)',
  border: '1px dashed var(--mac-border, #d2d2d7)',
  background: 'var(--mac-bg-secondary, #f5f5f7)',
  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
  fontSize: 13,
  wordBreak: 'break-all' as const,
  cursor: 'pointer',
  userSelect: 'all' as const,
};

const PatientActivationTokenDialog = ({ isOpen, onClose, patient }: PatientActivationTokenDialogProps) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;

  const [stage, setStage] = useState<DialogStage>('confirm');
  const [issuing, setIssuing] = useState(false);
  const [issued, setIssued] = useState<PatientActivationTokenResult | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');

  const patientId = patient?.id as string | number | undefined;
  const patientName = String(
    patient?.full_name || [patient?.last_name, patient?.first_name, patient?.middle_name].filter(Boolean).join(' ') || ''
  );

  const handleIssue = async () => {
    if (!patientId) {
      return;
    }
    setIssuing(true);
    setError('');
    try {
      const response = await issueActivationToken(patientId);
      setIssued(response);
      setCopied(false);
      setStage('result');
    } catch (err) {
      logger.warn('[PatientActivationTokenDialog] issue failed:', err);
      const apiError = err as HttpApiError;
      if (apiError?.response?.status === 409) {
        setError(t('patientPortal.pi_error_already_linked'));
      } else if (apiError?.response?.status === 404) {
        setError(t('patientPortal.pi_error_not_found'));
      } else if (apiError?.response?.status === 429) {
        setError(t('patientPortal.pa_rate_limited'));
      } else {
        setError(t('patientPortal.pi_error_generic'));
      }
    } finally {
      setIssuing(false);
    }
  };

  const handleCopy = async () => {
    if (!issued || copied) {
      return;
    }
    try {
      await navigator.clipboard.writeText(issued.activation_token);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch (copyError) {
      logger.warn('[PatientActivationTokenDialog] clipboard failed:', copyError);
    }
  };

  const handleClose = () => {
    // Reset transient state so the next open starts at the confirm stage.
    setStage('confirm');
    setIssued(null);
    setCopied(false);
    setError('');
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      closeOnBackdrop={!issuing}
      closeOnEscape={!issuing}
      title={stage === 'confirm' ? t('patientPortal.pi_confirm_title') : t('patientPortal.pi_issued_title')}
      aria-label={t('patientPortal.pi_title')}
    >
        {error ? (
          <Alert variant="danger" style={{ marginBottom: 12 }} role="alert">
            {error}
          </Alert>
        ) : null}

        {stage === 'confirm' ? (
          <>
            <p style={{ margin: '0 0 10px', fontSize: 14 }}>
              {t('patientPortal.pi_confirm_text', { name: patientName || `#${patientId ?? ''}` })}
            </p>
            <Alert variant="warning" style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
              <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: 2 }} aria-hidden="true" />
              <span>{t('patientPortal.pi_confirm_warning')}</span>
            </Alert>
          </>
        ) : (
          <>
            {issued?.phone_masked ? (
              <p style={{ margin: '0 0 8px', fontSize: 14 }}>
                {t('patientPortal.pi_phone', { phone: issued.phone_masked })}
              </p>
            ) : null}
            <p style={{ margin: '0 0 4px', fontSize: 13, color: 'var(--mac-text-secondary, #6e6e73)' }}>
              {t('patientPortal.pi_token_hint')}
            </p>
            <div
              style={tokenBoxStyle}
              role="button"
              tabIndex={0}
              aria-label={t('patientPortal.pi_copy')}
              onClick={handleCopy}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  handleCopy();
                }
              }}
            >
              {issued?.activation_token}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8, fontSize: 13 }}>
              <span style={{ color: 'var(--mac-text-secondary, #6e6e73)' }}>
                {t('patientPortal.pi_expires', { hours: issued?.expires_in_hours ?? '' })}
              </span>
              <Button type="button" variant="ghost" size="small" onClick={handleCopy} aria-label={t('patientPortal.pi_copy')}>
                {copied ? <Check size={14} style={{ marginRight: 6 }} aria-hidden="true" /> : <Copy size={14} style={{ marginRight: 6 }} aria-hidden="true" />}
                {copied ? t('patientPortal.pi_copied') : t('patientPortal.pi_copy')}
              </Button>
            </div>
          </>
        )}

      {stage === 'confirm' ? (
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
          <Button type="button" variant="ghost" onClick={handleClose} disabled={issuing}>
            {t('patientPortal.pi_cancel')}
          </Button>
          <Button type="button" onClick={handleIssue} disabled={issuing || !patientId}>
            {issuing ? t('patientPortal.pi_issuing') : t('patientPortal.pi_issue')}
          </Button>
        </div>
      ) : (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 16 }}>
          <Button type="button" onClick={handleClose}>
            {t('patientPortal.pi_done')}
          </Button>
        </div>
      )}
    </Modal>
  );
};

export default PatientActivationTokenDialog;
