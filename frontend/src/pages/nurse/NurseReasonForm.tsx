/**
 * NURSE-V2 N2-5 — the mandatory-reason dialog (execution / entry level).
 *
 * Mirrors the server contract exactly (§3): the reason is required,
 * trimmed, non-blank, at most 200 chars — the client validates for UX,
 * the backend re-validates fail-closed (the N2-3 round-3 discipline).
 * PHI (§11): the reason is sent to the clinical endpoint only — never
 * logged, never put into analytics. Built on the canonical Modal kit
 * (the regression-audit modal-files ratchet).
 */

import { useEffect, useMemo, useRef, useState } from 'react';

import { Button, Modal } from '@/components/ui';

import { useTranslation } from '../../i18n/useTranslation';

const REASON_MAX_LENGTH = 200;

export type NurseReasonFormProps = {
  open: boolean;
  /** 'execution' — abort a service attempt; 'entry' — terminal entry exit. */
  mode: 'execution' | 'entry';
  busy: boolean;
  /** Passed to the Modal kit (undefined while busy = close locked). */
  onClose?: () => void;
  onCancel: () => void;
  onSubmit: (reason: string) => void;
};

export function validateIncompleteReason(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return 'nurse.reason_blank';
  }
  if (trimmed.length > REASON_MAX_LENGTH) {
    return 'nurse.reason_too_long';
  }
  return null;
}

export function NurseReasonForm({
  open,
  mode,
  busy,
  onClose,
  onCancel,
  onSubmit,
}: NurseReasonFormProps) {
  const { t } = useTranslation();
  const [value, setValue] = useState('');
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (open) {
      setValue('');
      // focus immediately for the tablet soft keyboard — a deferred
      // focus races with in-flight typing and blurs the field mid-type
      inputRef.current?.focus();
    }
  }, [open]);

  const errorKey = useMemo(() => validateIncompleteReason(value), [value]);
  const canSubmit = !busy && errorKey === null;

  return (
    <Modal
      isOpen={open}
      onClose={busy ? undefined : onClose ?? onCancel}
      title={t(
        mode === 'execution'
          ? 'nurse.reason_title_execution'
          : 'nurse.reason_title_entry',
      )}
      actions={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={busy}>
            {t('nurse.action_cancel')}
          </Button>
          <Button
            variant="primary"
            onClick={() => onSubmit(value.trim())}
            disabled={!canSubmit}
          >
            {t('nurse.action_submit')}
          </Button>
        </>
      }
    >
      <label className="nurse-dialog__label" htmlFor="nurse-dialog-reason">
        {t('nurse.reason_label')}
      </label>
      <textarea
        id="nurse-dialog-reason"
        ref={inputRef}
        className="nurse-dialog__input"
        value={value}
        rows={4}
        maxLength={REASON_MAX_LENGTH + 20}
        aria-label={t('nurse.reason_label')}
        aria-invalid={errorKey !== null}
        aria-describedby="nurse-dialog-counter"
        disabled={busy}
        onChange={(event) => setValue(event.target.value)}
      />
      <div className="nurse-dialog__meta">
        <span
          id="nurse-dialog-counter"
          className={
            value.trim().length > REASON_MAX_LENGTH
              ? 'nurse-dialog__counter nurse-dialog__counter--over'
              : 'nurse-dialog__counter'
          }
        >
          {value.trim().length}/{REASON_MAX_LENGTH}
        </span>
        {errorKey !== null && (
          <span className="nurse-dialog__error" role="alert">
            {t(errorKey)}
          </span>
        )}
      </div>
    </Modal>
  );
}
