/**
 * NURSE-V2 N2-5 — the mandatory-reason dialog (execution / entry level).
 *
 * Mirrors the server contract exactly (§3): the reason is required,
 * trimmed, non-blank, at most 200 chars — the client validates for UX,
 * the backend re-validates fail-closed (the N2-3 round-3 discipline).
 * PHI (§11): the reason is sent to the clinical endpoint only — never
 * logged, never put into analytics.
 */

import { useEffect, useMemo, useRef, useState } from 'react';

import { Button } from '@/components/ui';

import { useTranslation } from '../../i18n/useTranslation';

const REASON_MAX_LENGTH = 200;

export type NurseIncompleteDialogProps = {
  open: boolean;
  /** 'execution' — abort a service attempt; 'entry' — terminal entry exit. */
  mode: 'execution' | 'entry';
  busy: boolean;
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

export function NurseIncompleteDialog({
  open,
  mode,
  busy,
  onCancel,
  onSubmit,
}: NurseIncompleteDialogProps) {
  const { t } = useTranslation();
  const [value, setValue] = useState('');
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (open) {
      setValue('');
      // focus for the tablet soft keyboard without scrolling jumps
      window.setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const errorKey = useMemo(() => validateIncompleteReason(value), [value]);
  const canSubmit = !busy && errorKey === null;

  if (!open) {
    return null;
  }

  return (
    <div
      className="nurse-dialog__backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget && !busy) {
          onCancel();
        }
      }}
    >
      <div
        className="nurse-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="nurse-dialog-title"
      >
        <h2 id="nurse-dialog-title" className="nurse-dialog__title">
          {t(
            mode === 'execution'
              ? 'nurse.reason_title_execution'
              : 'nurse.reason_title_entry',
          )}
        </h2>
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
        <div className="nurse-dialog__actions">
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
        </div>
      </div>
    </div>
  );
}
