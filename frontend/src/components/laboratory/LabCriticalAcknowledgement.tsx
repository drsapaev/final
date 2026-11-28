import { useEffect, useRef, useState } from 'react';
import { labOperationsApi, type LabCriticalTask } from '../../api/labOperations';
import { Button } from '../ui/macos';
import type { getLabOperationsLabels } from './labOperationsLabels';

interface LabCriticalAcknowledgementProps {
  visitId: number;
  refresh: number;
  reportsReady: boolean;
  reportIds: number[];
  labels: ReturnType<typeof getLabOperationsLabels>;
}

export default function LabCriticalAcknowledgement({
  visitId, refresh, reportsReady, reportIds, labels,
}: LabCriticalAcknowledgementProps) {
  const [inbox, setInbox] = useState<{ refresh: number; tasks: LabCriticalTask[]; error: boolean }>();
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [failedId, setFailedId] = useState<number | null>(null);
  const acknowledgementsDuringRead = useRef<Map<number, LabCriticalTask> | null>(null);

  useEffect(() => {
    const request = new AbortController();
    const concurrentAcknowledgements = new Map<number, LabCriticalTask>();
    acknowledgementsDuringRead.current = concurrentAcknowledgements;
    void labOperationsApi.listCritical(visitId, request.signal).then((rows) => {
      if (request.signal.aborted) return;
      // The inbox snapshot may predate an acknowledgement that has already succeeded.
      const tasks = rows.map((task) => concurrentAcknowledgements.get(task.id) ?? task);
      setInbox({ refresh, tasks, error: false });
    }).catch(() => {
      if (!request.signal.aborted) setInbox({ refresh, tasks: [], error: true });
    });
    return () => {
      request.abort();
      acknowledgementsDuringRead.current = null;
    };
  }, [visitId, refresh]);

  async function acknowledge(id: number) {
    setPendingId(id);
    setFailedId(null);
    try {
      const updated = await labOperationsApi.updateCritical(id, 'acknowledge');
      acknowledgementsDuringRead.current?.set(id, updated);
      setInbox((current) => current && {
        ...current, tasks: current.tasks.map((task) => task.id === id ? updated : task),
      });
    } catch {
      setFailedId(id);
    } finally {
      setPendingId(null);
    }
  }

  const currentInbox = inbox?.refresh === refresh ? inbox : undefined;
  if (!reportsReady || !currentInbox) return null;
  const visible = currentInbox.tasks.filter(({ report_instance_id }) => reportIds.includes(report_instance_id));
  const error = currentInbox.error || visible.some((task) => task.id === failedId);
  if (!visible.length && !error) return null;

  return (
    <section aria-label={labels.critical}>
      {error && <p role="alert">{labels.requestError}</p>}
      <ul>
        {visible.map((task) => (
          <li key={task.id}>
            {labels.report} #{task.report_instance_id} · <span role="status">{labels[task.state]}</span>
            {task.available_actions.includes('acknowledge') && (
              <Button size="small" variant="outline" disabled={pendingId !== null}
                onClick={() => void acknowledge(task.id)}>{labels.acknowledge}</Button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
