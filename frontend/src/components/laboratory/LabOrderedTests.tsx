import { useRef, useState } from 'react';
import { labReportingApi } from '../../api/labReporting';
import { useTranslation } from '../../i18n/useTranslation';
import { Alert, Badge, Button, Input } from '../ui/macos';

export interface LabOrderedTest {
  id: number;
  label: string;
  canceled: boolean;
  canCancel: boolean;
}

interface Props {
  visitId: number;
  orderId: number | null;
  tests: LabOrderedTest[];
  disabled: boolean;
  onPendingChange: (pending: boolean) => void;
  onChanged: (id?: number) => void;
}

export default function LabOrderedTests({ visitId, orderId, tests, disabled, onPendingChange, onChanged }: Props) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState<number | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const trigger = useRef<HTMLElement | null>(null);
  const pending = useRef(false);

  async function cancelTest(id: number) {
    if (disabled || pending.current || !reason.trim() || !tests.some((test) => test.id === id && test.canCancel)) return;
    pending.current = true;
    setBusy(true);
    onPendingChange(true);
    setError(false);
    try {
      await labReportingApi.cancelOrderedTest(visitId, id, orderId, reason.trim());
      setEditing(null);
      onChanged(id);
    } catch (failure) {
      setError(true);
      if ((failure as { status?: number } | null)?.status === 409) onChanged();
    } finally {
      pending.current = false;
      setBusy(false);
      onPendingChange(false);
    }
  }

  return (
    <details className="lab-ordered-tests">
      <summary>{t('labWorkspace.orderedTests')}</summary>
      {error && <Alert severity="error">{t('labWorkspace.cancelTestError')}</Alert>}
      <ul className="lab-specimen-list">
        {tests.map((test) => (
          <li key={test.id}>
            <div className="lab-worklist-toolbar">
              <span>{test.label} · #{test.id}</span>
              {test.canceled && <Badge variant="default">{t('labWorkspace.work_canceled')}</Badge>}
              {test.canCancel && editing !== test.id && (
                <Button type="button" variant="outline" disabled={disabled || busy} onClick={(event) => {
                  trigger.current = event.currentTarget;
                  setEditing(test.id);
                  setReason('');
                  setError(false);
                }}>{t('labWorkspace.cancelTest')}</Button>
              )}
            </div>
            {test.canCancel && editing === test.id && (
              <form className="lab-specimen-form" onSubmit={(event) => { event.preventDefault(); void cancelTest(test.id); }}>
                <label>{t('labWorkspace.reason')}
                  <Input autoFocus value={reason} maxLength={300} required disabled={disabled || busy}
                    onChange={(event) => setReason(event.target.value)} />
                </label>
                <div className="lab-worklist-toolbar">
                  <Button type="submit" variant="danger" disabled={!reason.trim() || disabled || busy}>
                    {t('labWorkspace.cancelTest')}
                  </Button>
                  <Button type="button" variant="ghost" disabled={busy} onClick={() => {
                    setEditing(null);
                    window.requestAnimationFrame(() => trigger.current?.focus());
                  }}>{t('common.back')}</Button>
                </div>
              </form>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}
