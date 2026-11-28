import { useCallback, useEffect, useState } from 'react';
import { getEMRWorkspace, type EMRWorkspaceData } from '@/api/emrWorkspace';

type WorkspaceState =
  | { scope: string; status: 'loading' | 'error' }
  | { scope: string; status: 'ready'; data: EMRWorkspaceData };

export function useEMRWorkspace(visitId: string | number, patientId: string | number | null) {
  const scope = `${visitId}:${patientId ?? ''}`;
  const [state, setState] = useState<WorkspaceState>();
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision(value => value + 1), []);
  useEffect(() => {
    if (!visitId) return;
    const controller = new AbortController();
    void getEMRWorkspace(visitId, patientId, controller.signal).then(
      data => {
        if (!controller.signal.aborted) setState({ scope, status: 'ready', data });
      },
      () => {
        if (!controller.signal.aborted) setState({ scope, status: 'error' });
      },
    );
    return () => controller.abort();
  }, [visitId, patientId, scope, revision]);

  const current: WorkspaceState = state?.scope === scope ? state : { scope, status: 'loading' };
  return { ...current, reload };
}
