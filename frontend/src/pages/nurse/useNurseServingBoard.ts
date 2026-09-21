/**
 * NURSE-V2 N2-5 — the tablet's serving state machine.
 *
 * Server state is the ONLY source of truth (§8): nothing critical lives
 * exclusively in React state — every successful mutation refetches the
 * canonical board, a reload restores workplaces -> selection check ->
 * board (+ the drain-recovery discovery of the N2-3 follow-up), and the
 * last rendered server state is PRESERVED across network errors (§9).
 *
 * Mutation discipline (§7): buttons disable while a mutation is pending,
 * but that is UX only — the backend stays the correctness boundary:
 *  - 200 idempotent replay  -> render the durable server state (refetch);
 *  - 409                    -> no guesswork, no retry loop — refetch board;
 *  - 403 assignment loss    -> refetch workplaces, back to the picker;
 *  - 404 station gone       -> unavailable state, refetch workplaces;
 *  - 5xx/network            -> keep the rendered state, surface Retry.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import type {
  NurseServingDrainingExecutionItemDto,
  NurseStationBoard,
  NurseWorkplace,
} from '@/api/nurseServing';
import { useNurseServingApi } from '@/hooks/useNurseServingApi';

/** Moderate station-board polling (§10): the tablet is a shared screen. */
const BOARD_POLL_INTERVAL_MS = 30_000;
/** Focus/visibility revalidation throttle (the Tabs.tsx RQ-27.a pattern). */
const FOCUS_REFRESH_MIN_INTERVAL_MS = 5_000;
/** UI preference only (§4): the workplaces GET stays the access SSOT. */
const WORKPLACE_PREFERENCE_KEY = 'nurse.serving.workplace';

export type NurseBoardError = {
  status: number | null;
  message: string;
} | null;

export type NurseServingBoardState = {
  workplaces: NurseWorkplace[];
  workplacesLoading: boolean;
  /** null = not chosen yet; a persisted id is a HINT, never access. */
  selectedWorkplaceId: number | null;
  board: NurseStationBoard | null;
  boardLoading: boolean;
  boardError: NurseBoardError;
  /** The N2-3 follow-up drain-recovery discovery (§8 reload restore). */
  draining: NurseServingDrainingExecutionItemDto[];
  drainingLoading: boolean;
  /** Transient, non-PHI notice key after a mutation outcome (§9). */
  notice: string | null;
  /** Keys of in-flight mutations — buttons disable on these (§7). */
  pending: Set<string>;
};

export function useNurseServingBoard() {
  const api = useNurseServingApi();
  const [state, setState] = useState<NurseServingBoardState>({
    workplaces: [],
    workplacesLoading: true,
    selectedWorkplaceId: null,
    board: null,
    boardLoading: false,
    boardError: null,
    draining: [],
    drainingLoading: true,
    notice: null,
    pending: new Set<string>(),
  });

  /** Any in-flight HTTP work (guards silent polling, §10). */
  const busyRef = useRef(false);
  const lastFocusRefreshRef = useRef(0);
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const selectedRef = useRef<number | null>(null);
  selectedRef.current = state.selectedWorkplaceId;

  const patch = useCallback((partial: Partial<NurseServingBoardState>) => {
    setState((prev) => ({ ...prev, ...partial }));
  }, []);

  // -------------------------------------------------------------------------
  // read plane
  // -------------------------------------------------------------------------

  const loadWorkplaces = useCallback(async (): Promise<NurseWorkplace[]> => {
    patch({ workplacesLoading: true });
    try {
      const data = await api.listWorkplaces();
      const items = data.items ?? [];
      patch({ workplaces: items, workplacesLoading: false });
      return items;
    } catch {
      patch({ workplaces: [], workplacesLoading: false });
      return [];
    }
  }, [api, patch]);

  const loadBoard = useCallback(
    async (queueResourceId: number): Promise<NurseStationBoard | null> => {
      patch({ boardLoading: true, boardError: null });
      try {
        const board = await api.getStationBoard(queueResourceId);
        patch({ board, boardLoading: false });
        return board;
      } catch (err) {
        const status = api.nurseServingErrorStatus(err);
        // §9: keep the last RENDERED server state — do not blank the board.
        setState((prev) => ({
          ...prev,
          boardLoading: false,
          boardError: {
            status,
            message: api.nurseServingErrorText(err, 'errors.nurse.board_unavailable'),
          },
        }));
        return null;
      }
    },
    [api, patch],
  );

  const loadDraining = useCallback(async (): Promise<void> => {
    patch({ drainingLoading: true });
    try {
      const data = await api.listDrainingExecutions();
      patch({ draining: data.items ?? [], drainingLoading: false });
    } catch {
      // The discovery is a bonus surface: a failure here never blocks
      // the main board — just keep the previous list.
      patch({ drainingLoading: false });
    }
  }, [api, patch]);

  /** §4: 403/404 on the chosen workplace -> recheck workplaces, re-pick. */
  const resetWorkplace = useCallback(
    async (notice?: string) => {
      const items = await loadWorkplaces();
      patch({
        board: null,
        boardError: null,
        ...(notice ? { notice } : {}),
        ...(items.length === 1
          ? { selectedWorkplaceId: items[0].queue_resource_id }
          : { selectedWorkplaceId: null }),
      });
      if (items.length === 1) {
        await loadBoard(items[0].queue_resource_id);
      }
      return items;
    },
    [loadBoard, loadWorkplaces, patch],
  );

  const selectWorkplace = useCallback(
    async (queueResourceId: number) => {
      try {
        window.localStorage.setItem(
          WORKPLACE_PREFERENCE_KEY,
          String(queueResourceId),
        );
      } catch {
        // storage unavailable (private mode) — the hint is optional
      }
      patch({ selectedWorkplaceId: queueResourceId, notice: null });
      await loadBoard(queueResourceId);
    },
    [loadBoard, patch],
  );

  // -------------------------------------------------------------------------
  // mutations — every path ends in a canonical refetch (§7)
  // -------------------------------------------------------------------------

  const runMutation = useCallback(
    async (
      key: string,
      action: () => Promise<unknown>,
      opts: { terminal?: boolean } = {},
    ): Promise<'ok' | 'conflict' | 'forbidden' | 'not-found' | 'error'> => {
      setState((prev) => ({ ...prev, pending: new Set(prev.pending).add(key) }));
      try {
        await action();
        setState((prev) => {
          const next = new Set(prev.pending);
          next.delete(key);
          return { ...prev, pending: next, notice: null };
        });
        if (opts.terminal) {
          // a terminal outcome may have finished drain work too
          await loadDraining();
        }
        const selected = selectedRef.current;
        if (selected != null) {
          await loadBoard(selected);
        }
        return 'ok';
      } catch (err) {
        setState((prev) => {
          const next = new Set(prev.pending);
          next.delete(key);
          return { ...prev, pending: next };
        });
        const status = api.nurseServingErrorStatus(err);
        if (status === 409) {
          // §9: the state changed by another staff member -> refetch.
          const selected = selectedRef.current;
          if (selected != null) {
            await loadBoard(selected);
          }
          patch({ notice: 'nurse.notice_state_changed' });
          return 'conflict';
        }
        if (status === 403) {
          // assignment lost / never granted for THIS station
          await resetWorkplace('nurse.notice_workplace_access_lost');
          return 'forbidden';
        }
        if (status === 404) {
          await resetWorkplace('nurse.notice_station_unavailable');
          return 'not-found';
        }
        // 5xx / network: keep the rendered state, surface a retry notice
        patch({ notice: 'nurse.notice_retry' });
        return 'error';
      }
    },
    [api, loadBoard, loadDraining, patch, resetWorkplace],
  );

  const callNext = useCallback(
    () =>
      runMutation('call-next', () => {
        const selected = selectedRef.current;
        if (selected == null) {
          return Promise.reject(new Error('no workplace'));
        }
        return api.callNextPatient(selected);
      }),
    [api, runMutation],
  );

  const start = useCallback(
    (entryId: number) =>
      runMutation(`start:${entryId}`, () => {
        const selected = selectedRef.current;
        if (selected == null) {
          return Promise.reject(new Error('no workplace'));
        }
        return api.startEntry(selected, entryId);
      }),
    [api, runMutation],
  );

  const startExecution = useCallback(
    (visitServiceId: number, queueEntryId: number) =>
      runMutation(`execution:${visitServiceId}`, () => {
        const selected = selectedRef.current;
        if (selected == null) {
          return Promise.reject(new Error('no workplace'));
        }
        return api.startServiceExecution(selected, {
          queue_entry_id: queueEntryId,
          visit_service_id: visitServiceId,
        });
      }),
    [api, runMutation],
  );

  const completeExecution = useCallback(
    (executionId: number) =>
      runMutation(
        `complete:${executionId}`,
        () => api.completeServiceExecution(executionId),
        // terminal: a completion may have finished DRAIN work too (the
        // §8 discovery must re-read — the card must disappear at once)
        { terminal: true },
      ),
    [api, runMutation],
  );

  const incompleteExecution = useCallback(
    (executionId: number, reason: string) =>
      runMutation(
        `incomplete:${executionId}`,
        () => api.incompleteServiceExecution(executionId, { reason }),
        { terminal: true },
      ),
    [api, runMutation],
  );

  const noShow = useCallback(
    (entryId: number) =>
      runMutation(`no-show:${entryId}`, () => {
        const selected = selectedRef.current;
        if (selected == null) {
          return Promise.reject(new Error('no workplace'));
        }
        return api.markEntryNoShow(selected, entryId);
      }),
    [api, runMutation],
  );

  const entryIncomplete = useCallback(
    (entryId: number, reason: string) =>
      runMutation(`entry-incomplete:${entryId}`, () => {
        const selected = selectedRef.current;
        if (selected == null) {
          return Promise.reject(new Error('no workplace'));
        }
        return api.markEntryIncomplete(selected, entryId, { reason });
      }),
    [api, runMutation],
  );

  const dismissNotice = useCallback(() => patch({ notice: null }), [patch]);

  // -------------------------------------------------------------------------
  // lifecycle: initial load + selection restore + polling + focus (§8/§10)
  // -------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const items = await loadWorkplaces();
      await loadDraining();
      if (cancelled) return;
      let preferred: number | null = null;
      try {
        const raw = window.localStorage.getItem(WORKPLACE_PREFERENCE_KEY);
        preferred = raw ? Number(raw) : null;
      } catch {
        preferred = null;
      }
      const valid =
        preferred != null &&
        Number.isFinite(preferred) &&
        items.some((w) => w.queue_resource_id === preferred)
          ? preferred
          : null;
      if (items.length === 1) {
        // §4: single workplace auto-selects; the server stays the SSOT.
        patch({ selectedWorkplaceId: items[0].queue_resource_id });
        await loadBoard(items[0].queue_resource_id);
      } else if (valid != null) {
        patch({ selectedWorkplaceId: valid });
        const board = await loadBoard(valid);
        if (board == null) {
          // §4: the stored id failed (403/404) -> back to the picker.
          await resetWorkplace();
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Silent refresh: board + draining, only when idle and visible. */
  const silentRefresh = useCallback(async () => {
    if (busyRef.current || state.pending.size > 0) return;
    busyRef.current = true;
    try {
      const selected = selectedRef.current;
      if (selected != null) {
        try {
          const board = await api.getStationBoard(selected);
          patch({ board });
        } catch {
          // silent poll failure: keep the rendered state (§9)
        }
      }
      try {
        const data = await api.listDrainingExecutions();
        patch({ draining: data.items ?? [] });
      } catch {
        // discovery is best-effort
      }
    } finally {
      busyRef.current = false;
    }
  }, [api, patch, state.pending.size]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        void silentRefresh();
      }
    }, BOARD_POLL_INTERVAL_MS);
    const onFocus = () => {
      const now = Date.now();
      if (
        document.visibilityState === 'visible' &&
        now - lastFocusRefreshRef.current >= FOCUS_REFRESH_MIN_INTERVAL_MS
      ) {
        lastFocusRefreshRef.current = now;
        void silentRefresh();
      }
    };
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onFocus);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onFocus);
    };
  }, [silentRefresh]);

  const refresh = useCallback(async () => {
    const selected = selectedRef.current;
    if (selected != null) {
      await loadBoard(selected);
    }
    await loadDraining();
  }, [loadBoard, loadDraining]);

  return {
    ...state,
    selectWorkplace,
    resetWorkplace,
    refresh,
    callNext,
    start,
    startExecution,
    completeExecution,
    incompleteExecution,
    noShow,
    entryIncomplete,
    dismissNotice,
  };
}
