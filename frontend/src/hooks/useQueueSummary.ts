/**
 * useQueueSummary — clinic-wide queue summary hook.
 *
 * PR-UI-11-1 (dashboard data-first).
 *
 * ## Purpose
 *
 * Fetches the list of active departments via `/doctor/departments?active_only=true`,
 * then fans out parallel per-department `/queues/stats?department=<name>&d=<YYYY-MM-DD>`
 * calls via `Promise.all`. Failures per department are tolerated (skipped); the
 * returned summary reflects only the departments that returned data.
 *
 * ## Boundary
 *
 * ADR-0015: hooks are the canonical layer to import from `api/*`. Components
 * must not import `api/client` directly; they call this hook instead.
 *
 * ## API shape
 *
 *   const {
 *     summary,           // { waiting, serving, done, departmentCount, openDepartments }
 *     loading,            // true during the departments fetch + the per-dept fan-out
 *     error,              // string | null — surfaces only if the departments fetch itself fails
 *     refresh,            // () => void — re-fetches departments (which retriggers the fan-out)
 *   } = useQueueSummary({ enabled: true, date: '2026-08-28' });
 *
 * Per-department fetch failures do NOT set `error`; they are silently skipped.
 * The summary is reset to all-zeros on a hard failure of the departments list.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { api } from '../api/client';
import useAdminData from './useAdminData';

export interface QueueSummaryDepartment {
  id: number;
  name: string;
  is_active: boolean;
}

export interface QueueSummaryDepartmentsPayload {
  departments: QueueSummaryDepartment[];
  total_count: number;
}

export interface QueueStatsPayload {
  department: string;
  date_str: string;
  is_open: boolean;
  start_number: number | null;
  last_ticket: number;
  waiting: number;
  serving: number;
  done: number;
  [key: string]: unknown;
}

export interface QueueSummaryAggregate {
  waiting: number;
  serving: number;
  done: number;
  departmentCount: number;
  openDepartments: number;
}

export interface UseQueueSummaryOptions {
  enabled?: boolean;
  date?: string; // YYYY-MM-DD
}

export interface UseQueueSummaryReturn {
  summary: QueueSummaryAggregate;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

const emptySummary: QueueSummaryAggregate = {
  waiting: 0,
  serving: 0,
  done: 0,
  departmentCount: 0,
  openDepartments: 0,
};

function aggregate(stats: Array<QueueStatsPayload | null | undefined>, departmentCount: number): QueueSummaryAggregate {
  return stats.reduce<QueueSummaryAggregate>(
    (acc, s) => {
      if (!s) return acc;
      const waiting = Number.isFinite(s.waiting) ? Number(s.waiting) : 0;
      const serving = Number.isFinite(s.serving) ? Number(s.serving) : 0;
      const done = Number.isFinite(s.done) ? Number(s.done) : 0;
      return {
        waiting: acc.waiting + waiting,
        serving: acc.serving + serving,
        done: acc.done + done,
        departmentCount,
        openDepartments: acc.openDepartments + (s.is_open ? 1 : 0),
      };
    },
    { ...emptySummary, departmentCount },
  );
}

function todayIso(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

const useQueueSummary = (options: UseQueueSummaryOptions = {}): UseQueueSummaryReturn => {
  const { enabled = true, date = todayIso() } = options;

  const {
    data: departmentsDataRaw,
    loading: departmentsLoading,
    error: departmentsError,
    refresh: refreshDepartments,
  } = useAdminData('/doctor/departments?active_only=true', {
    refreshInterval: 0,
    enabled,
    initialData: { departments: [], total_count: 0 },
  });

  const departments = useRef<QueueSummaryDepartment[]>([]);
  if (departmentsDataRaw && Array.isArray((departmentsDataRaw as QueueSummaryDepartmentsPayload).departments)) {
    departments.current = (departmentsDataRaw as QueueSummaryDepartmentsPayload).departments;
  } else if (!departmentsLoading) {
    departments.current = [];
  }

  const [summary, setSummary] = useState<QueueSummaryAggregate>(emptySummary);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef<boolean>(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!enabled) return;
    if (departmentsLoading) return;

    if (departmentsError) {
      setError(String(departmentsError));
      setSummary(emptySummary);
      setLoading(false);
      return;
    }

    const deptList = departments.current;
    if (deptList.length === 0) {
      setError(null);
      setSummary(emptySummary);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    const statsPromises = deptList.map((dept) =>
      api
        .get<QueueStatsPayload>(`/queues/stats?department=${encodeURIComponent(dept.name)}&d=${date}`)
        .then((response) => response.data as QueueStatsPayload)
        .catch(() => null),
    );

    Promise.all(statsPromises).then((results) => {
      if (cancelled || !mountedRef.current) return;
      setSummary(aggregate(results, deptList.length));
      setLoading(false);
    }).catch((err: unknown) => {
      if (cancelled || !mountedRef.current) return;
      setError(String(err));
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [departmentsDataRaw, departmentsLoading, departmentsError, enabled, date]);

  const refresh = useCallback((): void => {
    refreshDepartments();
  }, [refreshDepartments]);

  return {
    summary,
    loading: loading || departmentsLoading,
    error,
    refresh,
  };
};

export default useQueueSummary;
