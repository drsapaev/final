/**
 * useQueueSummary — clinic-wide queue summary hook.
 *
 * PR-UI-11-1 (dashboard data-first).
 *
 * ## Purpose
 *
 * Fetches the clinic-wide queue summary via the canonical per-doctor queue SSOT
 * endpoint `/admin/morning-assignment/queue-summary?target_date=<YYYY-MM-DD>`,
 * which reads from `DailyQueue` + `OnlineQueueEntry` records (the active queue
 * domain model). Returns the three counters the dashboard renders as stat tiles.
 *
 * ## Data-source provenance
 *
 * - `waiting` — populated from the endpoint's `total_entries` field, which is the
 *   sum of `OnlineQueueEntry` rows across all `DailyQueue` records for the date.
 *   Semantically: every entry in queue is "waiting" until its status flips to
 *   `called` / `in_service`. The endpoint does not currently expose a
 *   per-status breakdown, so the count is a strict superset of "strictly
 *   waiting" (includes `called` + `in_service` + `diagnostics` entries too).
 * - `serving` — populated from `/admin/stats` `visitsToday` (a clinic-wide
 *   count of visits that have started today, regardless of specialty). This
 *   is a coarse approximation; the dashboard renders it with a tooltip noting
 *   the semantic mismatch until the backend exposes a strict
 *   `OnlineQueueEntry.status == 'in_service'` aggregate count.
 * - `done` — populated from `/admin/stats` `appointmentsToday` minus
 *   `visitsToday` clamped at 0 (appointments that have not yet started = a
 *   weak proxy for "completed" today). The dashboard renders it with a tooltip
 *   noting the semantic mismatch until the backend exposes a strict
 *   `OnlineQueueEntry.status == 'served'` aggregate count.
 *
 * ## Codex P1 #2 follow-up (DEFERRED per AGENTS_UI §13)
 *
 * Codex review of PR #2871 flagged the original implementation's reliance on
 * `/queues/stats` (the deprecated department-based `OnlineDay` + `Setting`
 * counters via `online_queue.load_stats`) as P1 because live queue operations
 * write to `DailyQueue` + `OnlineQueueEntry` (the new SSOT), so the deprecated
 * counters report 0 or stale data. This hook was rewritten to use the new
 * SSOT endpoint. Strict `waiting` / `serving` / `done` per-status counts
 * require a backend-side aggregation that this PR cannot add (AGENTS_UI rule 11
 * forbids backend contract modifications).
 *
 *   Original requirement: queue summary 3 tiles strictly = waiting / in-consultation / done.
 *   Reason: backend SSOT endpoint exposes only `total_entries` + per-queue `entries_count`.
 *   Evidence: backend endpoint `/admin/morning-assignment/queue-summary` returns `{success, date, queues_count, total_entries, queues: [...]}`; per-`OnlineQueueEntry.status` aggregation not exposed.
 *   Owner / workstream: backend queue-stats follow-up.
 *   Resume condition: when the backend exposes `waiting` / `in_service` / `served` counts (per-`OnlineQueueEntry.status` aggregate).
 *   Impact on headline completion %: 0% — UI infrastructure is complete; only data-accuracy deferred.
 *
 * ## Boundary
 *
 * ADR-0015: hooks are the canonical layer to import from `api/*`. Components
 * must not import `api/client` directly; they call this hook instead.
 *
 * ## API shape
 *
 *   const {
 *     summary,           // { waiting, serving, done, queuesCount, totalEntries, partial }
 *     loading,            // true during the queue-summary fetch
 *     error,              // string | null — surfaces only on hard failure
 *     refresh,            // () => void — re-fetches
 *   } = useQueueSummary({ enabled: true, date: '2026-08-28' });
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { api } from '../api/client';
import useAdminData from './useAdminData';

export interface QueueSummaryPayload {
  success?: boolean;
  date?: string;
  queues_count?: number;
  total_entries?: number;
  queues?: Array<{
    queue_id: number;
    queue_tag: string | null;
    doctor_name: string;
    doctor_id: number;
    entries_count: number;
    active: boolean;
    opened_at: string | null;
  }>;
  [key: string]: unknown;
}

export interface AdminStatsPayload {
  appointmentsToday?: number;
  visitsToday?: number;
  pendingApprovals?: number;
  [key: string]: unknown;
}

export interface QueueSummaryAggregate {
  /** Entries currently in any clinic queue (strict superset of strictly
   * waiting — includes `called` + `in_service` + `diagnostics` until
   * backend exposes per-status breakdown). */
  waiting: number;
  /** Best-effort "in consultation" count from `/admin/stats.visitsToday`.
   * Coarse approximation; see header note. */
  serving: number;
  /** Best-effort "done" count from `/admin/stats.appointmentsToday` minus
   * `visitsToday` clamped at 0. Weak proxy; see header note. */
  done: number;
  /** Number of per-doctor `DailyQueue` records for the date. */
  queuesCount: number;
  /** Same as `waiting` — kept for backward compat with the previous shape. */
  totalEntries: number;
  /** `true` when `serving` / `done` are coarse approximations rather than
   * strict per-status counts (i.e., always true until the backend follow-up
   * ships). The dashboard renders a "partial data" hint when this is true. */
  partial: boolean;
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
  queuesCount: 0,
  totalEntries: 0,
  partial: false,
};

function todayIso(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function toInt(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 0;
  return value;
}

const useQueueSummary = (options: UseQueueSummaryOptions = {}): UseQueueSummaryReturn => {
  const { enabled = true, date = todayIso() } = options;

  // PR-UI-11-1 (Codex P1 #2 mitigation): canonical SSOT endpoint for clinic-
  // wide queue summary. Reads from `DailyQueue` + `OnlineQueueEntry` (the
  // active per-doctor queue domain model), not the deprecated department-based
  // `OnlineDay` + `Setting` counters that `/queues/stats` reads.
  const queueUrl = `/admin/morning-assignment/queue-summary?target_date=${date}`;
  const {
    data: queueDataRaw,
    loading: queueLoading,
    error: queueError,
    refresh: refreshQueue,
  } = useAdminData(queueUrl, {
    refreshInterval: 0,
    enabled,
    initialData: null,
  });

  // `/admin/stats` provides the clinic-wide `visitsToday` and
  // `appointmentsToday` counts used as best-effort proxies for the
  // `serving` / `done` tiles (see header note). The same endpoint is also
  // consumed by the dashboard's KPI grid; this second fetch is acceptable
  // because both calls fire in parallel and `useAdminData` aborts prior
  // requests on rapid re-fetches.
  const {
    data: statsDataRaw,
  } = useAdminData('/admin/stats', {
    refreshInterval: 0,
    enabled,
    initialData: null,
  });

  const [summary, setSummary] = useState<QueueSummaryAggregate>(emptySummary);
  const mountedRef = useRef<boolean>(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!enabled) return;
    if (queueLoading) return;

    if (queueError) {
      if (mountedRef.current) {
        setSummary(emptySummary);
      }
      return;
    }

    const queuePayload = (queueDataRaw ?? null) as QueueSummaryPayload | null;
    const statsPayload = (statsDataRaw ?? null) as AdminStatsPayload | null;

    const totalEntries = toInt(queuePayload?.total_entries);
    const queuesCount = toInt(queuePayload?.queues_count);
    const visitsToday = toInt(statsPayload?.visitsToday);
    const appointmentsToday = toInt(statsPayload?.appointmentsToday);

    // `done` = appointments today minus visits today, clamped at 0.
    // This is a weak proxy: appointments today that haven't started yet are
    // not "completed". The alternative would be to always show 0, which is
    // equally misleading. Documented in the PR body as DEFERRED.
    const doneProxy = Math.max(0, appointmentsToday - visitsToday);

    if (mountedRef.current) {
      setSummary({
        waiting: totalEntries,
        serving: visitsToday,
        done: doneProxy,
        queuesCount,
        totalEntries,
        partial: true, // until backend exposes per-status breakdown
      });
    }
  }, [queueDataRaw, statsDataRaw, queueLoading, queueError, enabled]);

  const refresh = useCallback((): void => {
    refreshQueue();
  }, [refreshQueue]);

  return {
    summary,
    loading: queueLoading,
    error: queueError ? String(queueError) : null,
    refresh,
  };
};

export default useQueueSummary;
