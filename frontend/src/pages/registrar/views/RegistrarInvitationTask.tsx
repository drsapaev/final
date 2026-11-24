import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { api } from '../../../api/client';
import { Button, Modal } from '../../../components/ui/macos';
import { useTranslation } from '../../../i18n/useTranslation';
import type { components } from '../../../types/api';
import { formatRegistrarDate } from '../../../utils/dateUtils';

type Task = components['schemas']['VisitInvitationTaskResponse'];
type TaskResult = { kind: 'ready'; task: Task } | { kind: 'unavailable' | 'error' };

const HANDLE = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/;

function InvitationDialog({ handle, onClose }: { handle: string | null; onClose: () => void }) {
  const { t, language } = useTranslation();
  const [result, setResult] = useState<TaskResult | null>(null);
  const [attempt, setAttempt] = useState(0);
  const task = result?.kind === 'ready' ? result.task : null;
  const unavailable = handle === null || result?.kind === 'unavailable';

  useEffect(() => {
    if (handle === null) return;
    const controller = new AbortController();

    void api.get<Task>(`/notifications/visit-invitation-tasks/${handle}`, { signal: controller.signal })
      .then(({ data }) => {
        if (!controller.signal.aborted) setResult({ kind: 'ready', task: data });
      })
      .catch((error: { response?: { status?: number } }) => {
        if (controller.signal.aborted) return;
        const status = error?.response?.status;
        setResult({ kind: status === 401 || status === 403 || status === 404 ? 'unavailable' : 'error' });
      });
    return () => controller.abort();
  }, [handle, attempt]);

  return (
    <Modal
      isOpen
      title={t('registrarPanel.invitation_task_title')}
      onClose={onClose}
      actions={(
        <>
          {result?.kind === 'error' && (
            <Button onClick={() => { setResult(null); setAttempt((previous) => previous + 1); }}>
              {t('common.refresh')}
            </Button>
          )}
          <Button variant="outline" onClick={onClose}>{t('common.close')}</Button>
        </>
      )}
    >
      {unavailable && <p role="alert">{t('registrarPanel.invitation_task_unavailable')}</p>}
      {!unavailable && result === null && <p role="status">{t('common.loading')}</p>}
      {result?.kind === 'error' && <p role="alert">{t('registrarPanel.invitation_task_load_error')}</p>}
      {task && (
        <dl className="grid gap-2">
          <div>
            <dt>{t('registrarPanel.invitation_task_patient')}</dt>
            <dd>{task.patient_name}</dd>
          </div>
          <div>
            <dt>{t('registrarPanel.invitation_task_date')}</dt>
            <dd>{formatRegistrarDate(task.visit_date, language)} {task.visit_time}</dd>
          </div>
          <div>
            <dt>{t('registrarPanel.invitation_task_phone')}</dt>
            <dd>{task.patient_phone || '—'}</dd>
          </div>
        </dl>
      )}
    </Modal>
  );
}

export default function RegistrarInvitationTask() {
  const [query, setQuery] = useSearchParams();
  if (!query.has('invitation')) return null;
  const candidates = query.getAll('invitation');
  const handle = candidates.length === 1 && HANDLE.test(candidates[0]) ? candidates[0] : null;
  const close = () => setQuery((current) => {
    const next = new URLSearchParams(current);
    next.delete('invitation');
    return next;
  }, { replace: true });

  return <InvitationDialog key={handle ?? 'invalid'} handle={handle} onClose={close} />;
}
