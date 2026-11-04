/**
 * Registrar Panel — worklist data lifecycle hook.
 *
 * PR-UI-13-1: extracted verbatim from RegistrarPanel.tsx (Decomp step 8).
 * Owns the appointments worklist data slice: fetching (GET /registrar/queues/today),
 * the SSOT flatMap adaptation (registrarQueueAdapter), patient enrichment
 * hand-off, pagination info, and the full refresh lifecycle:
 *
 * Lifecycle responsibilities (all ports preserved exactly):
 * - initial one-shot load (React 18 double-mount guard via initialLoadRef)
 * - `queueUpdated` window-event listener (WebSocket-driven refresh with
 *   critical-action immediate refresh + 300/500ms delays, silent otherwise)
 * - `departments:updated` window-event listener (→ loadIntegratedData)
 * - 30s auto-refresh interval with: in-flight guard, 60s 429 cooldown,
 *   30s WebSocket-freshness skip (R-4.1), dialog-open resilience (P-026/R-26)
 * - calendar date-change reload
 *
 * State machine (useReducer — plan §PR-UI-13 "top-level state machine"):
 *   idle → loading → api | error   (+ silent variants that keep indicators)
 * Transitions preserve the original per-branch quirks, including which
 * branches ran inside startTransition and which did not.
 *
 * @param deps.searchParams  react-router URLSearchParams (date param)
 * @param deps.activeTab     selected department tab (legacy-format fallback)
 * @param deps.showCalendar  calendar mode flag (historyDate wins over URL date)
 * @param deps.historyDate   calendar-selected date
 * @param deps.showWizard    wizard open flag (auto-refresh effect dependency)
 * @param deps.anyDialogOpenRef ref snapshot of other dialog-open flags — read
 *   at effect-run time only, mirroring the original stale-closure semantics
 *   (dialog flags were intentionally NOT in the effect deps)
 * @param deps.enrichAppointmentsWithPatientData from useRegistrarData
 * @param deps.loadIntegratedData from useRegistrarData
 * @param deps.tI18n         unified translator
 */
import { useCallback, useEffect, useReducer, useRef } from 'react';
import { startTransition } from 'react';
import type { RefObject } from 'react';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
import notify from '../../services/notify';
import { getLocalDateString } from '../../utils/dateUtils';
import { getErrorMessage } from '../../utils/errorHandler';
import type { HttpApiError } from '../../types/errors';
import type { Appointment } from '../../types/domain/clinic';
import { adaptQueueEntry } from './registrarQueueAdapter';

/**
 * REG-FE-008 (registrar audit ledger): typed outcome of one loadAppointments
 * call, so manual refresh callers can reward ONLY a verified result instead
 * of toasting success for a request they never awaited.
 *
 * - 'loaded'        — fresh rows applied to the sample.
 * - 'empty'         — authoritative empty day: still a SUCCESSFUL refresh.
 * - 'failed'        — 429 / 401 / network / malformed-envelope failure (the
 *                    reducer already drove the honest error/stale state).
 * - 'token-missing' — no access token; the empty session state was applied.
 * - 'superseded'    — a newer request owns the sample now (RQ-22 guard).
 * - 'skipped'       — auto-refresh cooldown or in-flight guard said no.
 */
export type RegistrarWorklistLoadOutcome =
  | 'loaded'
  | 'empty'
  | 'failed'
  | 'token-missing'
  | 'superseded'
  | 'skipped';

export interface WorklistPaginationInfo {
  total: number;
  hasMore: boolean;
  loadingMore: boolean;
}

export interface WorklistDataState {
  appointments: Appointment[];
  dataSource: 'loading' | 'api' | 'error';
  appointmentsLoading: boolean;
  paginationInfo: WorklistPaginationInfo;
  /** RQ-22 (F-18): true when the displayed rows are previously loaded data
   *  kept after a failed refresh. Staleness must be explicit, never silent. */
  stale: boolean;
  /** PR #3851 review (P2): target_date of the last VERIFIED sample — the
   *  clinic day whose rows are actually in `appointments`. null until the
   *  first successful load, and after a deliberate wipe (token-missing) or
   *  a primary failure. The SELECTED date (calendar/URL) is a different
   *  concept: on a date switch the selection changes instantly while the
   *  sample still belongs to the previous day (and a failed refresh keeps
   *  it there, RQ-22) — today- instruments must key off THIS value. */
  loadedDate: string | null;
}

export type WorklistDataAction =
  | { type: 'LOAD_STARTED'; silent: boolean }
  | { type: 'LOAD_TOKEN_MISSING'; silent: boolean }
  | { type: 'LOAD_EMPTY'; date: string }
  | { type: 'LOAD_SUCCEEDED'; rows: Appointment[]; date: string }
  | { type: 'LOAD_FAILED'; silent: boolean }
  | { type: 'LOAD_FINALLY'; silent: boolean }
  | { type: 'PAGINATION_REPLACED'; pagination: WorklistPaginationInfo }
  | { type: 'PAGINATION_PATCH'; patch: Partial<WorklistPaginationInfo> }
  | { type: 'APPOINTMENTS_UPDATER'; updater: (prev: Appointment[]) => Appointment[] };

export const initialWorklistDataState: WorklistDataState = {
  appointments: [],
  dataSource: 'loading',
  appointmentsLoading: false,
  paginationInfo: { total: 0, hasMore: false, loadingMore: false },
  stale: false,
  loadedDate: null,
};

/**
 * Pure reducer for the worklist data slice. Exported for unit testing.
 * Each action maps 1:1 to the original setState sequence it replaces.
 */
export const worklistDataReducer = (
  state: WorklistDataState,
  action: WorklistDataAction,
): WorklistDataState => {
  switch (action.type) {
    case 'LOAD_STARTED':
      // Original: if (!silent) { setAppointmentsLoading(true); setDataSource('loading'); }
      if (action.silent) return state;
      return { ...state, appointmentsLoading: true, dataSource: 'loading' };
    case 'LOAD_TOKEN_MISSING':
      // Original (startTransition): if (!silent) setDataSource('api'); setAppointments([]);
      // RQ-22: a deliberate auth-data wipe is not staleness — flag resets.
      // PR #3851 review (P2): the wiped sample is no longer a verified day.
      return {
        ...state,
        dataSource: action.silent ? state.dataSource : 'api',
        appointments: [],
        stale: false,
        loadedDate: null,
      };
    case 'LOAD_EMPTY':
      // Original (NOT in startTransition): setAppointments([]); setDataSource('api');
      // setAppointmentsLoading(false);
      // RQ-22: an authoritative empty answer is fresh data, not staleness.
      // PR #3851 review (P2): an empty day is still a VERIFIED day — its
      // target_date becomes the loaded sample's date.
      return { ...state, appointments: [], dataSource: 'api', appointmentsLoading: false, stale: false, loadedDate: action.date };
    case 'LOAD_SUCCEEDED':
      // Original (startTransition): setAppointments(enriched); setDataSource('api');
      // RQ-22: a successful response refreshes the sample — staleness clears.
      // PR #3851 review (P2): the sample now verifiably belongs to action.date.
      return { ...state, appointments: action.rows, dataSource: 'api', stale: false, loadedDate: action.date };
    case 'LOAD_FAILED': {
      // Original (startTransition): if (!silent) setDataSource('error'); setAppointments([]);
      // RQ-22 (F-18): a failed refresh must NOT wipe previously loaded rows
      // into a misleading "successfully empty" list. When rows exist they
      // stay on screen with an explicit stale flag (retry affordance in
      // WorklistView); only a PRIMARY failure (nothing loaded yet) keeps
      // the plain error state. Silent failures keep the indicators intact
      // (original contract) but still mark the displayed data stale.
      const hasRows = state.appointments.length > 0;
      if (!hasRows) {
        // PR #3851 review (P2): nothing was ever verified — no loaded day.
        return {
          ...state,
          dataSource: action.silent ? state.dataSource : 'error',
          appointments: [],
          stale: false,
          loadedDate: null,
        };
      }
      // PR #3851 review (P2): kept rows still belong to the day they were
      // loaded for — loadedDate stays (sampleIsToday must not flip to
      // the newly SELECTED day whose load just failed).
      return {
        ...state,
        dataSource: 'api',
        appointments: state.appointments,
        stale: true,
      };
    }
    case 'LOAD_FINALLY':
      // Original: if (!silent) setAppointmentsLoading(false);
      if (action.silent) return state;
      return { ...state, appointmentsLoading: false };
    case 'PAGINATION_REPLACED':
      return { ...state, paginationInfo: action.pagination };
    case 'PAGINATION_PATCH':
      return { ...state, paginationInfo: { ...state.paginationInfo, ...action.patch } };
    case 'APPOINTMENTS_UPDATER':
      // setAppointments(prev => ...) shim used by useRegistrarReschedule.
      return { ...state, appointments: action.updater(state.appointments) };
    default:
      return state;
  }
};

export const useRegistrarWorklistData = ({
  searchParams,
  activeTab,
  showCalendar,
  historyDate,
  showWizard,
  anyDialogOpenRef,
  enrichAppointmentsWithPatientData,
  loadIntegratedData,
  tI18n,
}: {
  searchParams: URLSearchParams;
  activeTab: string | null;
  showCalendar: boolean;
  historyDate: string;
  showWizard: boolean;
  anyDialogOpenRef: RefObject<boolean>;
  enrichAppointmentsWithPatientData: (appointments: Record<string, unknown>[]) => Promise<Record<string, unknown>[]>;
  loadIntegratedData: () => Promise<void> | void;
  tI18n: (key: string, options?: Record<string, unknown>) => string;
}) => {
  const [state, dispatch] = useReducer(worklistDataReducer, initialWorklistDataState);

  const { appointments, dataSource, appointmentsLoading, paginationInfo, stale, loadedDate } = state;
  const appointmentsCount = appointments.length;

  // In-flight / cooldown / freshness guards (ports of panel refs).
  const initialLoadRef = useRef(false);
  const loadAppointmentsInFlightRef = useRef(false);
  // RQ-22 (S-19): monotonically increasing request id — the hook keeps only
  // the LATEST request's result. A late response of a superseded request
  // (calendar date switch, manual retry after a timeout) must not overwrite
  // the newer sample or clobber its state.
  const requestSeqRef = useRef(0);
  const autoRefreshCooldownUntilRef = useRef(0);
  const autoRefreshCooldownLoggedRef = useRef(false);
  // UX Audit R-4.1: track last WebSocket update timestamp to skip redundant interval refresh.
  const lastQueueUpdatedRef = useRef(0);

  // Filter inputs for the no-op filters-changed logger (kept for log parity).
  const searchQuery = searchParams.get('q')?.toLowerCase() ?? '';
  const statusFilter = searchParams.get('status');

  // Улучшенная загрузка записей с поддержкой тихого режима
  // (port of RegistrarPanel.loadAppointments — verbatim control flow)
  const loadAppointments = useCallback(async (rawOptions: unknown = {}): Promise<RegistrarWorklistLoadOutcome> => {
    const options: Record<string, unknown> = (rawOptions && typeof rawOptions === 'object' ? rawOptions : {}) as Record<string, unknown>;
    const { silent = false } = options;
    const callSource = String(options.source || 'unknown');
    const isAutoRefreshCall = callSource === 'auto_refresh';
    if (isAutoRefreshCall) {
      const cooldownUntil = autoRefreshCooldownUntilRef.current;
      if (Date.now() < cooldownUntil) {
        if (!autoRefreshCooldownLoggedRef.current) {
          logger.info('⏳ Автообновление приостановлено после rate limit', {
            cooldownUntil: new Date(cooldownUntil).toISOString()
          });
          autoRefreshCooldownLoggedRef.current = true;
        }
        return 'skipped';
      }

      if (loadAppointmentsInFlightRef.current) {
        logger.info('⏭️ Автообновление пропущено: предыдущий запрос еще выполняется');
        return 'skipped';
      }
    }

    loadAppointmentsInFlightRef.current = true;
    // RQ-22: claim this request's id BEFORE any await; only the newest id wins.
    const requestId = ++requestSeqRef.current;
    const isSuperseded = () => requestId !== requestSeqRef.current;
    try {
      if (!silent) {
        dispatch({ type: 'LOAD_STARTED', silent: Boolean(silent) });
      }

      // Проверяем наличие токена
      const token = tokenManager.getAccessToken();
      if (!token) {
        logger.warn('Токен аутентификации отсутствует, показываем пустое состояние');
        if (!isSuperseded()) {
          startTransition(() => {
            dispatch({ type: 'LOAD_TOKEN_MISSING', silent: Boolean(silent) });
          });
        }
        return 'token-missing';
      }

      // Используем новый эндпоинт для получения очередей на указанную дату
      // Если календарь открыт, используем historyDate, иначе сегодня
      const urlDate = searchParams.get('date');
      const dateParam = showCalendar && historyDate ? historyDate : urlDate || getLocalDateString();

      const response = await api.get('/registrar/queues/today', { params: { target_date: dateParam } }) as import('axios').AxiosResponse<Record<string, unknown>>;

      // RQ-22 (S-19): a newer request has started while this one was in
      // flight — this response is stale and must not overwrite the sample.
      if (isSuperseded()) {
        return 'superseded';
      }

      // Axios successful response
      const data = response.data;

      // REG-FE-034 (audit ledger 3803): контракт канонического ответа —
      // объект с массивом queues (backend _today_queues.py сериализует
      // именно такой конверт). Старый произвольный fallback «объединить
      // все массивы по ключам» удалён: конверт 200 без массива queues —
      // это ошибка контракта (LOAD_FAILED → error/stale), а не «пустой
      // день». { queues: [] } остаётся валидным пустым днём.
      const rawQueues = data && typeof data === 'object'
        ? (data as { queues?: unknown }).queues
        : undefined;
      if (!Array.isArray(rawQueues)) {
        logger.warn('⚠️ Получены некорректные данные от сервера: queues array missing');
        throw new Error(tI18n('registrarPanel.rp_err_invalid_data'));
      }

      // ⭐ SSOT: Simple flatMap - no deduplication, no aggregation
      // Each backend entry = one frontend row
      // Removed: appointmentsMap, mergedByPatientKey, getAppointmentKey, calcPriority, mergeAppointments

      // ⭐ SSOT: flatMap all entries without any deduplication or aggregation
      let appointmentsData: Record<string, unknown>[] = [];
      const queuesList = rawQueues as Record<string, unknown>[];
      // REG-FE-067 (audit ledger 3803): per-queue contract validation — the
      // REG-FE-034 envelope check extends to each element of queues: a queue
      // that is not an object, or whose `entries` is not an array, is a
      // contract violation and must fail closed (LOAD_FAILED → error/stale).
      // The old `Array.isArray(queue.entries) ? queue.entries : []` coerced
      // such a body into a valid-looking EMPTY day (LOAD_EMPTY) or silently
      // dropped one queue's patients while rendering the rest.
      const validatedQueues = queuesList.map((queue) => {
        if (queue === null || typeof queue !== 'object' || !Array.isArray(queue.entries)) {
          logger.warn('⚠️ Некорректный элемент очереди: entries не является массивом (contract violation)');
          throw new Error(tI18n('registrarPanel.rp_err_invalid_data'));
        }
        return { queue, entries: queue.entries as Record<string, unknown>[] };
      });
      appointmentsData = validatedQueues.flatMap(({ queue, entries }) =>
        entries.
        map((entry: Record<string, unknown>) => adaptQueueEntry(entry, queue, data, dateParam, tI18n('registrarPanel.rp_unknown_patient'))).
        filter((entry: Record<string, unknown> | null) => entry !== null) // Remove entries without ID
      );

      logger.info(`📊 SSOT: Loaded ${appointmentsData.length} entries (no dedup, no aggregation)`);

      {
        dispatch({
          type: 'PAGINATION_REPLACED',
          pagination: {
            total: appointmentsData.length,
            hasMore: false,
            loadingMore: false
          }
        });

        logger.info(`📊 Загружено ${appointmentsData.length} записей для специальности: ${activeTab || 'все'}`);

        // Отладка: показываем ID всех загруженных записей
        if (appointmentsData.length > 0) {
          logger.info('📋 ID всех загруженных записей:', appointmentsData.map((a) => a.id));
        }

        // ✅ ИСПРАВЛЕНО: Пустая очередь - это нормально, не переключаемся в демо-режим
        if (appointmentsData.length === 0) {
          logger.info('📋 Нет записей на сегодня - это нормальная ситуация в начале дня');
          // Устанавливаем пустой массив, не выбрасываем ошибку
          dispatch({ type: 'LOAD_EMPTY', date: dateParam });
          return 'empty'; // ✅ Выходим из функции, не загружаем демо-данные
        }
      }

      if (appointmentsData.length > 0) {
        // Обогащаем данные записей информацией о пациентах
        const enriched = await enrichAppointmentsWithPatientData(appointmentsData);

        // RQ-22 (S-19): re-check after the enrichment await — a newer load
        // may have started (and even finished) while patients were enriched.
        if (isSuperseded()) {
          return 'superseded';
        }

        // ⭐ SSOT: Просто устанавливаем данные без local overrides
        // Removed: _locallyModified, localStorage overrides
        // REG-FE-008: outcome resolved only AFTER the authoritative dispatch —
        // a caller awaiting this promise cannot toast success for a sample
        // that was never applied.
        startTransition(() => {
          dispatch({ type: 'LOAD_SUCCEEDED', rows: enriched as unknown as Appointment[], date: dateParam });
        });
        logger.info('✅ SSOT: Загружено', enriched.length, 'записей (без local overrides)');
        return 'loaded';
      } else {
        // QW-03 fix: empty API response is a valid state, not a demo fallback.
        // Empty result is already handled earlier (line ~1370). This branch
        // is unreachable but kept as defensive code.
        if (isSuperseded()) {
          return 'superseded';
        }
        startTransition(() => {
          dispatch({ type: 'LOAD_SUCCEEDED', rows: [], date: dateParam });
        });
        return 'empty';
      }
    } catch (error: unknown) {
      if ((error as HttpApiError)?.response?.status === 429) {
        // REG-FE-020 (audit ledger 3803): cooldown принадлежит авторитетному
        // запросу — сменённый 429 не должен замораживать auto-refresh после
        // успеха более нового запроса.
        if (!isSuperseded()) {
          autoRefreshCooldownUntilRef.current = Date.now() + 60_000;
          autoRefreshCooldownLoggedRef.current = false;
          logger.warn('⏳ Регистраторская очередь ограничена по частоте, включаем cooldown на 60с', {
            source: callSource,
            dateParam: showCalendar && historyDate ? historyDate : getLocalDateString()
          });
          // REG-FE-007 (audit ledger 3803): 429 — явный сбой загрузки, а не
          // молчаливое «ничего»: primary → error + retry, refresh → строки
          // остаются с явным stale. Автообновление честно заморожено cooldown.
          startTransition(() => {
            dispatch({ type: 'LOAD_FAILED', silent: Boolean(silent) });
          });
        }
        return 'failed';
      }

      // Handle axios errors
      if ((error as HttpApiError)?.response?.status === 401) {
        // Токен недействителен
        logger.warn('Токен недействителен (401), очищаем и показываем ошибку');
        sessionStorage.removeItem('auth_token');  // PR-39 / P0-2;
        // QW-03 fix: show error state instead of demo data.
        if (isSuperseded()) {
          return 'superseded';
        }
        startTransition(() => {
          dispatch({ type: 'LOAD_FAILED', silent: Boolean(silent) });
        });
        return 'failed';
      } else {
        // Other errors (network, 404, 500, etc.)
        logger.error('❌ Backend недоступен для загрузки записей:', getErrorMessage(error));
        logger.error('❌ Детали ошибки:', error);
        if (isSuperseded()) {
          return 'superseded';
        }
        startTransition(() => {
          dispatch({ type: 'LOAD_FAILED', silent: Boolean(silent) });
        });
        // Показываем уведомление пользователю только при первой загрузке
        if (appointmentsCount === 0) {
          notify.error(tI18n('registrar.backend_unavailable'));
        }
        return 'failed';
      }
    } finally {
      // REG-FE-020 (audit ledger 3803): in-flight guard принадлежит новейшему
      // запросу — finally сменённого запроса не должен освобождать его, иначе
      // следующий auto-refresh tick стартует (и перехватит seq id у ещё
      // висящего более нового запроса).
      if (!isSuperseded()) {
        loadAppointmentsInFlightRef.current = false;
        // RQ-22: the finally cleanup of a SUPERSEDED request must not clear
        // the loading flag of the newer in-flight load.
        if (!silent) {
          dispatch({ type: 'LOAD_FINALLY', silent: Boolean(silent) });
        }
      }
    }
    // NOTE: tI18n is intentionally NOT in the dependency array — this mirrors
    // the original RegistrarPanel closure semantics exactly (adding it would
    // change effect re-run behavior on language switch, e.g. an extra
    // calendar-date reload while the calendar is open on a non-today date).
  }, [enrichAppointmentsWithPatientData, showCalendar, historyDate, searchParams, activeTab, appointmentsCount]);

  // Слушаем обновления отделений от админ-панели
  useEffect(() => {
    const handleDepartmentsUpdate = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      logger.info('RegistrarPanel: Получено обновление отделений, перезагружаю...', detail);
      loadIntegratedData();
    };

    window.addEventListener('departments:updated', handleDepartmentsUpdate);
    return () => window.removeEventListener('departments:updated', handleDepartmentsUpdate);
  }, [loadIntegratedData]);

  // Первичная загрузка данных (однократно) с защитой от двойного вызова в React 18
  useEffect(() => {
    if (initialLoadRef.current) return;
    initialLoadRef.current = true;
    logger.info('🚀 Starting initial data load (guarded)...');
    loadAppointments({ source: 'initial_load' });
    loadIntegratedData();
  }, [loadAppointments, loadIntegratedData]);

  // Слушаем глобальные события обновления очереди для синхронизации статусов
  useEffect(() => {
    const handleQueueUpdate = (event: Event) => {
      const detail = ((event as CustomEvent).detail ?? {}) as { action?: string; specialty?: string };
      const { action, specialty } = detail;
      // UX Audit R-4.1: record WebSocket update timestamp to skip redundant interval refresh.
      lastQueueUpdatedRef.current = Date.now();
      logger.info('[RegistrarPanel] Получено событие обновления очереди:', { action, specialty, detail });

      // Для критических действий обновляем немедленно без silent режима
      const criticalActions = ['patientCalled', 'visitStarted', 'visitCompleted', 'nextPatientCalled', 'refreshAll', 'entryAdded'];
      const shouldUpdateImmediately = action != null && criticalActions.includes(action);

      if (shouldUpdateImmediately) {
        logger.info('[RegistrarPanel] Немедленное обновление после действия:', action);
        logger.info('[RegistrarPanel] Детали события:', detail);
        // Увеличиваем задержку для гарантии сохранения данных в БД (особенно для новых записей)
        const delay = action === 'entryAdded' || action === 'refreshAll' ? 500 : 300;
        setTimeout(() => {
          logger.info('[RegistrarPanel] Выполняем обновление после задержки:', delay, 'ms');
          loadAppointments({ source: `queue_update_${action}`, silent: false });
        }, delay);
      } else {
        // Для других событий тихое обновление
        loadAppointments({ source: 'queue_update_event', silent: true });
      }
    };
    window.addEventListener('queueUpdated', handleQueueUpdate);

    return () => {
      window.removeEventListener('queueUpdated', handleQueueUpdate);
    };
  }, [loadAppointments]);

  // Перезагружаем данные при изменении фильтров
  useEffect(() => {
    if (initialLoadRef.current) {
      logger.info('🔄 Фильтры изменились (поиск/статус), но НЕ перезагружаем данные (дата контролируется календарём)');
      // Не перезагружаем данные - фильтрация происходит на клиенте через useMemo filteredAppointments
    }
  }, [searchQuery, statusFilter]);

  // Перезагружаем данные при изменении даты в календаре
  useEffect(() => {
    if (showCalendar && historyDate && initialLoadRef.current) {
      logger.info('📅 Дата календаря изменилась на:', historyDate);
      logger.info('📅 Вызываем loadAppointments с параметрами:', { showCalendar, historyDate });
      loadAppointments({ silent: false, source: 'calendar_date_change' });
    }
  }, [historyDate, showCalendar, loadAppointments]);

  // Автообновление очереди с возможностью паузы (в тихом режиме)
  const autoRefresh = true; // Новые состояния для интеграции с админ панелью
  useEffect(() => {
    // P-026 fix: previously auto-refresh was disabled whenever ANY of
    // (showWizard, paymentDialog, printDialog, cancelDialog) was open. This
    // meant a registrar with a payment dialog open for 2+ minutes would not
    // see new online-queue patients arrive in the worklist behind the dialog.
    //
    // R-26 fix: pause auto-refresh when ANY dialog is open.
    // Раньше только showWizard — но payment/cancel/reschedule dialogs
    // тоже могут пострадать от фонового refresh (row positions change).
    // NOTE (PR-UI-13-1): the dialog flags other than showWizard are read from
    // anyDialogOpenRef at effect-run time — they were intentionally NOT in the
    // original dependency array, and that stale-closure semantics is preserved.
    // REG-FE-021 (audit ledger 3803): флаг anyDialogOpenRef читается НА
    // КАЖДОМ тике интервала, а не один раз при создании эффекта —
    // открытие/закрытие диалога теперь реально управляет паузой без
    // ожидания ре-рана эффекта (реф не триггерит зависимости).
    if (showWizard) return;
    if (!autoRefresh) return;
    if (Date.now() < autoRefreshCooldownUntilRef.current) return;

    const id = setInterval(() => {
      if (anyDialogOpenRef.current) {
        return;
      }
      if (Date.now() < autoRefreshCooldownUntilRef.current || loadAppointmentsInFlightRef.current) {
        return;
      }
      // UX Audit R-4.1: skip interval refresh if WebSocket updated recently.
      // Раньше: setInterval(15000) работал ВСЕГДА, даже когда WebSocket уже
      // обновил данные. Это создавало race conditions и дублирующие network-запросы.
      // Теперь: если queueUpdated event был < 30s назад, пропускаем interval refresh.
      const lastWsUpdate = lastQueueUpdatedRef.current;
      if (lastWsUpdate && (Date.now() - lastWsUpdate) < 30000) {
        logger.info('⏰ Автообновление: пропускаем (WebSocket обновил недавно)');
        return;
      }
      // Загружаем только записи тихо, без смены индикаторов
      logger.info('⏰ Автообновление: вызов loadAppointments (dialog-open resilient)');
      loadAppointments({ silent: true, source: 'auto_refresh' } as Record<string, unknown>);
    }, 30000); // UX Audit R-4.1: 15s → 30s (WebSocket покрывает real-time)

    return () => clearInterval(id);
  }, [autoRefresh, showWizard, loadAppointments, anyDialogOpenRef]);

  // Функция для загрузки дополнительных записей
  const loadMoreAppointments = useCallback(async () => {
    if (paginationInfo.loadingMore || !paginationInfo.hasMore) return;

    dispatch({ type: 'PAGINATION_PATCH', patch: { loadingMore: true } });

    try {
      logger.info('RegistrarPanel: load-more delegates to canonical queue loader');
      await loadAppointments({ source: 'load_more', silent: true });
    } catch (error: unknown) {
      logger.error('Ошибка загрузки дополнительных записей:', error);
    } finally {
      dispatch({ type: 'PAGINATION_PATCH', patch: { loadingMore: false } });
    }
  }, [paginationInfo.loadingMore, paginationInfo.hasMore, loadAppointments]);

  // setAppointments shim: functional-updater API preserved for
  // useRegistrarReschedule.removeRescheduledAppointmentFromView.
  const setAppointments = useCallback((updater: (prev: Appointment[]) => Appointment[]) => {
    dispatch({ type: 'APPOINTMENTS_UPDATER', updater });
  }, []);

  return {
    appointments,
    setAppointments,
    dataSource,
    appointmentsLoading,
    paginationInfo,
    stale,
    loadedDate,
    loadAppointments,
    loadMoreAppointments,
  };
};

export default useRegistrarWorklistData;
