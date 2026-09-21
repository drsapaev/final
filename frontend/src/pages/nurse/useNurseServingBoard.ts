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
 *  - 403 assignment loss    -> the SYNCHRONOUS revocation clear below,
 *    then the workplaces re-read (owner review round);
 *  - 404 operation-specific -> refetch the board (another staffer took
 *    the patient / no one is waiting / the execution is already gone) —
 *    NEVER "station unavailable": that verdict belongs to the board GET
 *    itself (owner review: a call-next 404 used to eject the nurse from
 *    a perfectly healthy station);
 *  - 5xx/network            -> keep the rendered state, surface Retry.
 *
 * Board-read boundary (owner review): 403/404 on the board GET clear the
 * PHI from the screen IMMEDIATELY (403 also re-reads workplaces — the
 * assignment world changed), while network/5xx keep the last rendered
 * state; the error is visible EVEN when a previous board is still shown.
 *
 * Workplace discovery (owner review): the zero-workplace screen and the
 * focus refresh re-read the workplaces list — a fresh assignment lands
 * without a full page reload.
 *
 * Stale-response guard (owner review): board responses apply only when
 * they still describe the CURRENT selection — a slow response for
 * workplace A must never overwrite (or blank) workplace B after a quick
 * switch (the epoch + selected check below).
 *
 * Owner review round additions:
 *  - Station-switch PHI boundary (P1): switching A -> B clears the
 *    rendered A board IMMEDIATELY (a pending or failing B request must
 *    never leave A's patient under B's header — the board also renders
 *    only while it matches the current selection, see NurseTabletPage).
 *  - Synchronous revocation (P1): every 401/403 path runs the SAME
 *    synchronous action FIRST — bump ALL request epochs, clear board,
 *    draining, selection — and only THEN re-read the workplaces world;
 *    the draining discovery clears with the board (a revoked role must
 *    not keep its PHI + terminal actions alive on a shared tablet).
 *  - Stale silent-poll failures (P2): the catch of a silent board poll
 *    passes the SAME epoch + selection check as the success path — a
 *    late 403 for a superseded request never blanks the current state.
 *  - Distinguishable workplaces failure (P2): a network/5xx failure of
 *    the workplaces GET proves NOTHING — the previous list stays, a
 *    visible error appears; only a server-confirmed empty list (or an
 *    access loss) may drop the workflow.
 *  - Draining epoch (P2): terminal mutations and newer draining reads
 *    supersede every earlier in-flight draining response — a late
 *    answer can never resurrect an already-completed card.
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

/**
 * Owner review round (P2): the workplaces read result is DISTINGUISHABLE —
 * `{ok: true, items}` is a server-confirmed list (empty included), while
 * `{ok: false, status}` failed WITHOUT proving anything about the
 * assignments (network/5xx keep the current workflow; 401/403 is an
 * access loss and runs the synchronous revocation clear).
 */
export type NurseWorkplacesResult =
  | { ok: true; items: NurseWorkplace[] }
  | { ok: false; status: number | null };

export type NurseServingBoardState = {
  workplaces: NurseWorkplace[];
  workplacesLoading: boolean;
  /** A visible read error when the workplaces GET failed without
   *  proving the list empty (owner review P2) — the stale list stays. */
  workplacesError: NurseBoardError;
  /** null = not chosen yet; a persisted id is a HINT, never access. */
  selectedWorkplaceId: number | null;
  board: NurseStationBoard | null;
  boardLoading: boolean;
  boardError: NurseBoardError;
  /** The N2-3 follow-up drain-recovery discovery (§8 reload restore). */
  draining: NurseServingDrainingExecutionItemDto[];
  drainingLoading: boolean;
  /** The stale-draining warning (owner review): network/5xx keep the
   *  last rendered list, honestly labeled as possibly outdated. */
  drainingError: NurseBoardError;
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
    workplacesError: null,
    selectedWorkplaceId: null,
    board: null,
    boardLoading: false,
    boardError: null,
    draining: [],
    drainingLoading: true,
    drainingError: null,
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

  /**
   * The selection guard ref. applySelection is its ONLY writer (every
   * selectedWorkplaceId patch goes through it) — a render-time sync
   * from state could clobber the imperative write during the setState
   * flush window and drop a legitimate board response.
   */
  const selectedRef = useRef<number | null>(null);
  const workplacesRef = useRef<NurseWorkplace[]>([]);
  workplacesRef.current = state.workplaces;

  /**
   * The board-response epoch (owner review): every loadBoard bumps it;
   * a response (success OR error) applies only when it is still the
   * newest request AND still describes the current selection.
   */
  const boardEpochRef = useRef(0);

  /**
   * The draining-response epoch (owner review round, P2): every
   * draining read bumps it; a terminal mutation bumps it too — a late
   * response for an already-superseded read can never resurrect a
   * completed drain card.
   */
  const drainingEpochRef = useRef(0);

  /**
   * Which station the RENDERED board describes (owner review round,
   * P1): a board for workplace A must never linger — not while B loads,
   * not after B fails — under workplace B's header.
   */
  const boardResourceIdRef = useRef<number | null>(null);

  const patch = useCallback((partial: Partial<NurseServingBoardState>) => {
    setState((prev) => ({ ...prev, ...partial }));
  }, []);

  /**
   * Selection write: the guard ref updates IMMEDIATELY (the stale-
   * response check reads it while the setState flush is still pending —
   * a response that lands in that window must still pass the
   * selected-check), then converges with the rendered state.
   */
  const applySelection = useCallback(
    (queueResourceId: number | null) => {
      selectedRef.current = queueResourceId;
      patch({ selectedWorkplaceId: queueResourceId });
    },
    [patch],
  );

  /**
   * The SYNCHRONOUS revocation clear (owner review round, P1): ALL PHI
   * leaves the screen at once — every request epoch is bumped (in-flight
   * responses become stale), the board, the draining discovery and the
   * selection clear — BEFORE any second request runs. A slow, hung or
   * dead workplaces re-read must never keep a revoked patient on the
   * shared tablet; the re-read itself is orchestrated by the caller.
   */
  const clearAllPhi = useCallback(
    (notice?: string) => {
      boardEpochRef.current += 1;
      drainingEpochRef.current += 1;
      boardResourceIdRef.current = null;
      applySelection(null);
      patch({
        board: null,
        boardError: null,
        boardLoading: false,
        draining: [],
        drainingLoading: false,
        drainingError: null,
        ...(notice ? { notice } : {}),
      });
    },
    [applySelection, patch],
  );

  // -------------------------------------------------------------------------
  // read plane
  // -------------------------------------------------------------------------

  const loadWorkplaces = useCallback(
    async (): Promise<NurseWorkplacesResult> => {
      patch({ workplacesLoading: true });
      try {
        const data = await api.listWorkplaces();
        const items = data.items ?? [];
        patch({
          workplaces: items,
          workplacesLoading: false,
          workplacesError: null,
        });
        return { ok: true, items };
      } catch (err) {
        const status = api.nurseServingErrorStatus(err);
        if (status === 401 || status === 403) {
          // Access loss: the unified synchronous clear (PHI out) — the
          // list itself describes access, so it goes too.
          clearAllPhi('nurse.notice_workplace_access_lost');
          patch({ workplaces: [], workplacesLoading: false, workplacesError: null });
          return { ok: false, status };
        }
        // Owner review round (P2): a network/5xx failure proves NOTHING
        // about the assignments — the previous list STAYS, the error is
        // visible, and nothing drops the current workflow.
        patch({
          workplacesLoading: false,
          workplacesError: {
            status,
            message: api.nurseServingErrorText(err, 'nurse.workplaces_unavailable'),
          },
        });
        return { ok: false, status };
      }
    },
    [api, clearAllPhi, patch],
  );

  /**
   * Access revoked anywhere (board/draining/mutation 403): PHI out
   * synchronously, THEN the assignment world is re-read asynchronously.
   */
  const handleAccessRevoked = useCallback(
    (notice?: string) => {
      clearAllPhi(notice);
      void loadWorkplaces();
    },
    [clearAllPhi, loadWorkplaces],
  );

  /**
   * §4 selection invariant over a FRESH workplaces list: a still-granted
   * selection stays; a revoked one drops to the picker; a lone workplace
   * auto-selects (and loads its board) — the same rule the initial load
   * applies, re-run whenever the assignment world is re-read.
   */
  const ensureSelection = useCallback(
    async (items: NurseWorkplace[]): Promise<void> => {
      const selected = selectedRef.current;
      if (
        selected != null &&
        items.some((workplace) => workplace.queue_resource_id === selected)
      ) {
        return;
      }
      if (items.length === 1) {
        applySelection(items[0].queue_resource_id);
        patch({ notice: null });
        await loadBoardRef.current(items[0].queue_resource_id);
        return;
      }
      if (selected != null) {
        applySelection(null);
        boardResourceIdRef.current = null;
        patch({ board: null, boardError: null });
      }
    },
    [applySelection, patch],
  );

  /** Late-bound so ensureSelection can call loadBoard declared below. */
  const loadBoardRef = useRef<
    (queueResourceId: number) => Promise<NurseStationBoard | null>
  >(() => Promise.resolve(null));

  const loadBoard = useCallback(
    async (queueResourceId: number): Promise<NurseStationBoard | null> => {
      const epoch = ++boardEpochRef.current;
      if (boardResourceIdRef.current !== queueResourceId) {
        // Owner review round (P1): the request describes a DIFFERENT
        // station than the rendered board — station A's patient leaves
        // the screen NOW, not after B lands (and not at all on B's
        // network failure). A same-station reload keeps the rendered
        // state (§9).
        boardResourceIdRef.current = null;
        patch({ board: null, boardError: null, boardLoading: true });
      } else {
        patch({ boardLoading: true, boardError: null });
      }
      try {
        const board = await api.getStationBoard(queueResourceId);
        if (
          epoch !== boardEpochRef.current ||
          selectedRef.current !== queueResourceId
        ) {
          // A newer request (or a workplace switch) superseded this
          // response — applying it would render station A's PHI under
          // station B's header.
          return null;
        }
        boardResourceIdRef.current = queueResourceId;
        patch({ board, boardLoading: false });
        return board;
      } catch (err) {
        if (
          epoch !== boardEpochRef.current ||
          selectedRef.current !== queueResourceId
        ) {
          // A stale failure never blanks the CURRENT station either.
          return null;
        }
        const status = api.nurseServingErrorStatus(err);
        if (status === 403 || status === 404) {
          // Access-revocation boundary (owner review): the PHI leaves
          // the screen immediately. 403 = the assignment world changed
          // (also re-read workplaces — and the draining discovery clears
          // with the board: the same role world guards it); 404 = this
          // station surface is unavailable today. Network/5xx keep the
          // rendered state. The selection decision belongs to the caller
          // (initial load / picker / silent poll reset) — never to a
          // load->403->reset loop.
          boardResourceIdRef.current = null;
          drainingEpochRef.current += 1;
          patch({
            board: null,
            boardLoading: false,
            draining: [],
            drainingError: null,
            boardError: {
              status,
              message: api.nurseServingErrorText(
                err,
                'errors.nurse.board_unavailable',
              ),
            },
          });
          if (status === 403) {
            // Fire-and-forget list refresh — its own 403 would run the
            // full synchronous revocation clear.
            void loadWorkplaces();
          }
          return null;
        }
        // §9: keep the last RENDERED server state — do not blank the
        // board — but make the error visible even alongside it.
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
    [api, loadWorkplaces, patch],
  );
  loadBoardRef.current = loadBoard;

  const loadDraining = useCallback(
    async (opts: { silent?: boolean } = {}): Promise<void> => {
      const epoch = ++drainingEpochRef.current;
      if (!opts.silent) {
        patch({ drainingLoading: true });
      }
      try {
        const data = await api.listDrainingExecutions();
        if (epoch !== drainingEpochRef.current) {
          // Superseded by a newer read or a terminal mutation — a late
          // answer must never resurrect an already-completed card.
          return;
        }
        patch({
          draining: data.items ?? [],
          drainingLoading: false,
          drainingError: null,
        });
      } catch (err) {
        if (epoch !== drainingEpochRef.current) {
          return;
        }
        const status = api.nurseServingErrorStatus(err);
        if (status === 401 || status === 403) {
          // Owner review round (P1): the endpoint is Nurse-role-guarded —
          // a revoked role must not keep the stale drain items (ФИО,
          // service, terminal actions) on a shared tablet. The unified
          // synchronous clear + the asynchronous workplaces re-read.
          handleAccessRevoked('nurse.notice_workplace_access_lost');
          return;
        }
        if (status === 404) {
          // The discovery surface is unavailable — its items are no
          // longer provably accessible: drop them.
          patch({ draining: [], drainingLoading: false, drainingError: null });
          return;
        }
        // network/5xx: keep the stale list, but label it honestly
        // (owner review round: a visible warning, never a silent lie).
        patch({
          drainingLoading: false,
          drainingError: {
            status,
            message: api.nurseServingErrorText(err, 'nurse.draining_stale'),
          },
        });
      }
    },
    [api, handleAccessRevoked, patch],
  );

  /** §4: 403/404 on the chosen workplace -> recheck workplaces, re-pick. */
  const resetWorkplace = useCallback(
    async (notice?: string) => {
      // Owner review round (P1): the PHI clears SYNCHRONOUSLY — before
      // the workplaces re-read even starts. A hung listWorkplaces must
      // never keep a revoked patient on screen (the regression pins
      // exactly this ordering).
      clearAllPhi(notice);
      const result = await loadWorkplaces();
      const items = result.ok ? result.items : [];
      applySelection(items.length === 1 ? items[0].queue_resource_id : null);
      if (items.length === 1) {
        await loadBoardRef.current(items[0].queue_resource_id);
      }
      return items;
    },
    [applySelection, clearAllPhi, loadBoardRef, loadWorkplaces],
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
      applySelection(queueResourceId);
      patch({ notice: null });
      await loadBoard(queueResourceId);
    },
    [applySelection, loadBoard, patch],
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
          // a terminal outcome may have finished drain work too — the
          // epoch bump also invalidates every earlier draining response
          // (owner review round, P2)
          await loadDraining();
        }
        const selected = selectedRef.current;
        if (selected != null) {
          await loadBoardRef.current(selected);
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
            await loadBoardRef.current(selected);
          }
          patch({ notice: 'nurse.notice_state_changed' });
          return 'conflict';
        }
        if (status === 403) {
          // assignment lost / never granted for THIS station — the PHI
          // clears synchronously inside resetWorkplace, then the world
          // is re-read (owner review round: no window where a revoked
          // patient outlives a slow second request).
          await resetWorkplace('nurse.notice_workplace_access_lost');
          return 'forbidden';
        }
        if (status === 404) {
          // Owner review: operation-specific 404s — "no waiting patients",
          // "the entry was taken by another staffer", "the execution is
          // gone" — all mean REFRESH THE BOARD, not "station unavailable".
          // A real station/queue loss surfaces through the board GET's own
          // 403/404 handling; the old blanket reset ejected the nurse from
          // a healthy station on an ordinary call-next race.
          const selected = selectedRef.current;
          if (selected != null) {
            await loadBoardRef.current(selected);
          }
          if (opts.terminal) {
            await loadDraining();
          }
          patch({ notice: 'nurse.notice_state_changed' });
          return 'not-found';
        }
        // 5xx / network: keep the rendered state, surface a retry notice
        patch({ notice: 'nurse.notice_retry' });
        return 'error';
      }
    },
    [api, loadDraining, patch, resetWorkplace],
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
      const result = await loadWorkplaces();
      await loadDraining();
      if (cancelled) return;
      const items = result.ok ? result.items : [];
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
        applySelection(items[0].queue_resource_id);
        await loadBoardRef.current(items[0].queue_resource_id);
      } else if (valid != null) {
        applySelection(valid);
        const board = await loadBoardRef.current(valid);
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

  /**
   * Silent refresh: board + draining, only when idle and visible.
   *
   * The board response (success OR failure — owner review round, P2)
   * applies only while it still describes the current selection and no
   * newer request superseded it (the epoch + selected check). 403 -> the
   * full synchronous revocation reset (PHI out, workplaces re-read);
   * 404 -> the station surface clears; network/5xx -> keep the rendered
   * state. When the tablet sits on the zero-workplace screen (or nothing
   * is selected), the workplaces list is re-read too — a fresh assignment
   * lands without a page reload (owner review).
   */
  const silentRefresh = useCallback(async () => {
    if (busyRef.current || state.pending.size > 0) return;
    busyRef.current = true;
    try {
      const selected = selectedRef.current;
      const epoch = boardEpochRef.current;
      if (selected != null) {
        try {
          const board = await api.getStationBoard(selected);
          if (
            boardEpochRef.current === epoch &&
            selectedRef.current === selected &&
            mountedRef.current
          ) {
            boardResourceIdRef.current = selected;
            patch({ board });
          }
        } catch (err) {
          // Owner review round (P2): a stale FAILURE is discarded exactly
          // like a stale success — the epoch + selection check, never
          // the selection check alone (a late 403 for a superseded
          // request must not blank the fresh state or trigger a reset).
          if (
            boardEpochRef.current === epoch &&
            selectedRef.current === selected
          ) {
            const status = api.nurseServingErrorStatus(err);
            if (status === 403) {
              // assignment revoked: PHI out synchronously + workplaces
              // re-read + notice
              await resetWorkplace('nurse.notice_workplace_access_lost');
            } else if (status === 404) {
              boardResourceIdRef.current = null;
              patch({
                board: null,
                boardError: {
                  status,
                  message: api.nurseServingErrorText(
                    err,
                    'errors.nurse.board_unavailable',
                  ),
                },
              });
            }
            // network/5xx: silent poll failure keeps the rendered state
          }
        }
      }
      // The draining discovery refresh goes through loadDraining — the
      // epoch guard keeps a late answer from resurrecting a completed
      // card, and 401/403 run the synchronous revocation clear.
      await loadDraining({ silent: true });
      // Zero-workplace / nothing-selected discovery: re-read workplaces
      // (throttled by the poll interval / focus throttle) so a new
      // assignment appears without a full page reload. A failed read
      // proves nothing — only a server-confirmed list may re-select.
      if (
        mountedRef.current &&
        (workplacesRef.current.length === 0 || selectedRef.current == null)
      ) {
        const result = await loadWorkplaces();
        if (mountedRef.current && result.ok) {
          await ensureSelection(result.items);
        }
      }
    } finally {
      busyRef.current = false;
    }
  }, [
    api,
    ensureSelection,
    loadDraining,
    loadWorkplaces,
    patch,
    resetWorkplace,
    state.pending.size,
  ]);

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

  /**
   * Manual refresh: the FULL read plane — workplaces (the §4 access
   * SSOT — an assignment may have appeared or vanished) + the board +
   * the draining discovery. A failed workplaces read proves NOTHING
   * (owner review round, P2): the current workflow stays and the board
   * still gets its own refresh chance.
   */
  const refresh = useCallback(async () => {
    const result = await loadWorkplaces();
    const selected = selectedRef.current;
    if (result.ok) {
      if (
        selected != null &&
        result.items.some((workplace) => workplace.queue_resource_id === selected)
      ) {
        await loadBoardRef.current(selected);
      } else {
        await ensureSelection(result.items);
      }
    } else if (selected != null) {
      await loadBoardRef.current(selected);
    }
    await loadDraining();
  }, [ensureSelection, loadBoardRef, loadDraining, loadWorkplaces]);

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
