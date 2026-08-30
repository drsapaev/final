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
}

export type WorklistDataAction =
  | { type: 'LOAD_STARTED'; silent: boolean }
  | { type: 'LOAD_TOKEN_MISSING'; silent: boolean }
  | { type: 'LOAD_EMPTY' }
  | { type: 'LOAD_SUCCEEDED'; rows: Appointment[] }
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
      return {
        ...state,
        dataSource: action.silent ? state.dataSource : 'api',
        appointments: [],
      };
    case 'LOAD_EMPTY':
      // Original (NOT in startTransition): setAppointments([]); setDataSource('api');
      // setAppointmentsLoading(false);
      return { ...state, appointments: [], dataSource: 'api', appointmentsLoading: false };
    case 'LOAD_SUCCEEDED':
      // Original (startTransition): setAppointments(enriched); setDataSource('api');
      return { ...state, appointments: action.rows, dataSource: 'api' };
    case 'LOAD_FAILED':
      // Original (startTransition): if (!silent) setDataSource('error'); setAppointments([]);
      return {
        ...state,
        dataSource: action.silent ? state.dataSource : 'error',
        appointments: [],
      };
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

  const { appointments, dataSource, appointmentsLoading, paginationInfo } = state;
  const appointmentsCount = appointments.length;

  // In-flight / cooldown / freshness guards (ports of panel refs).
  const initialLoadRef = useRef(false);
  const loadAppointmentsInFlightRef = useRef(false);
  const autoRefreshCooldownUntilRef = useRef(0);
  const autoRefreshCooldownLoggedRef = useRef(false);
  // UX Audit R-4.1: track last WebSocket update timestamp to skip redundant interval refresh.
  const lastQueueUpdatedRef = useRef(0);

  // Filter inputs for the no-op filters-changed logger (kept for log parity).
  const searchQuery = searchParams.get('q')?.toLowerCase() ?? '';
  const statusFilter = searchParams.get('status');

  // Улучшенная загрузка записей с поддержкой тихого режима
  // (port of RegistrarPanel.loadAppointments — verbatim control flow)
  const loadAppointments = useCallback(async (rawOptions: unknown = {}) => {
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
        return;
      }

      if (loadAppointmentsInFlightRef.current) {
        logger.info('⏭️ Автообновление пропущено: предыдущий запрос еще выполняется');
        return;
      }
    }

    loadAppointmentsInFlightRef.current = true;
    try {
      if (!silent) {
        dispatch({ type: 'LOAD_STARTED', silent: Boolean(silent) });
      }

      // Проверяем наличие токена
      const token = tokenManager.getAccessToken();
      if (!token) {
        logger.warn('Токен аутентификации отсутствует, показываем пустое состояние');
        startTransition(() => {
          dispatch({ type: 'LOAD_TOKEN_MISSING', silent: Boolean(silent) });
        });
        return;
      }

      // Используем новый эндпоинт для получения очередей на указанную дату
      // Если календарь открыт, используем historyDate, иначе сегодня
      const urlDate = searchParams.get('date');
      const dateParam = showCalendar && historyDate ? historyDate : urlDate || getLocalDateString();

      const response = await api.get('/registrar/queues/today', { params: { target_date: dateParam } }) as import('axios').AxiosResponse<Record<string, unknown>>;

      // Axios successful response
      const data = response.data;

      // Новый формат: данные сгруппированы по специальностям
      let appointmentsData: Record<string, unknown>[] = [];

      if (data && typeof data === 'object') {
        // Обрабатываем формат от эндпоинта registrar_integration.py
        if (data.queues && Array.isArray(data.queues)) {
          // ⭐ SSOT: Simple flatMap - no deduplication, no aggregation
          // Each backend entry = one frontend row
          // Removed: appointmentsMap, mergedByPatientKey, getAppointmentKey, calcPriority, mergeAppointments

          // ⭐ SSOT: flatMap all entries without any deduplication or aggregation
          const queuesList = data.queues as Record<string, unknown>[];
          appointmentsData = queuesList.flatMap((queue) =>
          (Array.isArray(queue.entries) ? queue.entries : [] as unknown[]).
          map((entry: Record<string, unknown>) => adaptQueueEntry(entry, queue, data, dateParam, tI18n('registrarPanel.rp_unknown_patient'))).
          filter((entry: Record<string, unknown> | null) => entry !== null) // Remove entries without ID
          );

          logger.info(`📊 SSOT: Loaded ${appointmentsData.length} entries (no dedup, no aggregation)`);
        } else {
          // Обрабатываем старый формат для совместимости
          if (activeTab && data[activeTab]) {
            appointmentsData = Array.isArray(data[activeTab]) ? data[activeTab] : [];
          } else {
            // Берем все специальности и объединяем
            for (const dept in data) {
              const deptData = data[dept];
              if (Array.isArray(deptData)) {
                appointmentsData.push(...deptData);
              }
            }
          }
        }

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
          dispatch({ type: 'LOAD_EMPTY' });
          return; // ✅ Выходим из функции, не загружаем демо-данные
        }
      } else {
        logger.warn('⚠️ Получены некорректные данные от сервера:', data);
        throw new Error(tI18n('registrarPanel.rp_err_invalid_data'));
      }

      if (appointmentsData.length > 0) {
        // Обогащаем данные записей информацией о пациентах
        const enriched = await enrichAppointmentsWithPatientData(appointmentsData);

        // ⭐ SSOT: Просто устанавливаем данные без local overrides
        // Removed: _locallyModified, localStorage overrides
        startTransition(() => {
          dispatch({ type: 'LOAD_SUCCEEDED', rows: enriched as unknown as Appointment[] });
        });
        logger.info('✅ SSOT: Загружено', enriched.length, 'записей (без local overrides)');
      } else {
        // QW-03 fix: empty API response is a valid state, not a demo fallback.
        // Empty result is already handled earlier (line ~1370). This branch
        // is unreachable but kept as defensive code.
        startTransition(() => {
          dispatch({ type: 'LOAD_SUCCEEDED', rows: [] });
        });
      }
    } catch (error: unknown) {
      if ((error as HttpApiError)?.response?.status === 429) {
        autoRefreshCooldownUntilRef.current = Date.now() + 60_000;
        autoRefreshCooldownLoggedRef.current = false;
        logger.warn('⏳ Регистраторская очередь ограничена по частоте, включаем cooldown на 60с', {
          source: callSource,
          dateParam: showCalendar && historyDate ? historyDate : getLocalDateString()
        });
        return;
      }

      // Handle axios errors
      if ((error as HttpApiError)?.response?.status === 401) {
        // Токен недействителен
        logger.warn('Токен недействителен (401), очищаем и показываем ошибку');
        sessionStorage.removeItem('auth_token');  // PR-39 / P0-2;
        // QW-03 fix: show error state instead of demo data.
        startTransition(() => {
          dispatch({ type: 'LOAD_FAILED', silent: Boolean(silent) });
        });
      } else {
        // Other errors (network, 404, 500, etc.)
        logger.error('❌ Backend недоступен для загрузки записей:', getErrorMessage(error));
        logger.error('❌ Детали ошибки:', error);
        startTransition(() => {
          dispatch({ type: 'LOAD_FAILED', silent: Boolean(silent) });
        });
        // Показываем уведомление пользователю только при первой загрузке
        if (appointmentsCount === 0) {
          notify.error(tI18n('registrar.backend_unavailable'));
        }
      }
    } finally {
      loadAppointmentsInFlightRef.current = false;
      if (!silent) {
        dispatch({ type: 'LOAD_FINALLY', silent: Boolean(silent) });
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

  // Отслеживаем изменения в appointments для отладки
  useEffect(() => {
    logger.info('🔔 appointments state изменился:', {
      count: appointments.length,
      showCalendar,
      historyDate,
      first3: appointments.slice(0, 3).map((a) => ({ id: a.id, fio: a.patient_fio, date: a.appointment_date }))
    });
  }, [appointments, showCalendar, historyDate]);

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
    const anyDialogOpen = showWizard || Boolean(anyDialogOpenRef.current);
    if (anyDialogOpen) return;
    if (!autoRefresh) return;
    if (Date.now() < autoRefreshCooldownUntilRef.current) return;

    const id = setInterval(() => {
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
    loadAppointments,
    loadMoreAppointments,
  };
};

export default useRegistrarWorklistData;
