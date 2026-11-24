import { useEffect, useState } from 'react';
import { labOperationsApi, type LabCriticalTask } from '../../api/labOperations';
import { Button } from '../ui/macos';
import type { getLabOperationsLabels } from './labOperationsLabels';

interface LabCriticalAcknowledgementProps {
  visitId: number;
  reportIds: number[];
  labels: ReturnType<typeof getLabOperationsLabels>;
}

export default function LabCriticalAcknowledgement({ visitId, reportIds, labels }: LabCriticalAcknowledgementProps) {
  const [tasks, setTasks] = useState<LabCriticalTask[]>([]);
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const request = new AbortController();
    void labOperationsApi.listCritical(visitId, request.signal).then((rows) => {
      if (!request.signal.aborted) setTasks(rows);
    }).catch(() => {
      if (!request.signal.aborted) setError(true);
    });
    return () => request.abort();
  }, [visitId]);

  async function acknowledge(id: number) {
    setPendingId(id);
    setError(false);
    try {
      const updated = await labOperationsApi.updateCritical(id, 'acknowledge');
      setTasks((current) => current.map((task) => task.id === id ? updated : task));
    } catch {
      setError(true);
    } finally {
      setPendingId(null);
    }
  }

  const visible = tasks.filter(({ report_instance_id }) => reportIds.includes(report_instance_id));
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
