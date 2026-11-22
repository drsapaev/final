/**
 * PR-UI-14-1: cashier worklist data lifecycle.
 *
 * Verbatim move of the data-fetch/pagination/statistics slice from
 * src/pages/CashierPanel.tsx (main `d5b339309`) — behavior-preserving
 * decomposition per the PR-UI-13 registrar pattern (13-1 precedent:
 * useRegistrarWorklistData). No logic changes.
 *
 * Owns:
 *  - server data: stats / pending appointments / payment history
 *  - per-section loading flags (v2.1: pendingLoading + historyLoading)
 *  - server-side pagination for both tabs + page-reset-on-filter-change
 *  - refreshKey force-reload lifecycle + triggerDataReload / bumpRefreshKey
 *
 * Inputs (owned by the panel filter layer):
 *  - search (debounced query), status filter, date mode/range values
 *  - the three read-only getters of usePayments (single SSOT call site
 *    stays in the panel; this hook never mutates payments state)
 */

import { useCallback, useEffect, useState } from 'react';

import logger from '../../utils/logger';
import { getErrorMessage } from '../../utils/type-guards';
import type { Appointment } from '../../types/domain/clinic';
import type { UsePaymentsReturn } from '../../hooks/usePayments';

// ✅ УЛУЧШЕНИЕ: Статистика из API (shape moved verbatim from CashierPanel).
// CSH-FE-036 (#3813 follow-up): BOTH financial semantics are exposed —
// total/cash/card stay gross; refunded_amount + net_* carry the same
// period net of refunds. pending_amount has been net since CSH-FE-028.
//
// P2 (PR 3830 review, comment 4439005298): the CSH-FE-036 fields are
// OPTIONAL — during a rolling frontend/backend deploy the frontend may
// talk to an older /cashier/stats that does not return them. The payload
// is stored verbatim and zeros are never invented: an absent key stays
// `undefined` so CashierStatsCard renders «—» instead of a fake 0.
export interface CashierStatsSnapshot {
  total_amount: number;
  cash_amount: number;
  card_amount: number;
  /** Refunds inside the gross set; present only on the post-CSH-FE-036 API. */
  refunded_amount?: number;
  /** Net receipts (total − refunds); present only on the post-CSH-FE-036 API. */
  net_total_amount?: number;
  /** Net cash; present only on the post-CSH-FE-036 API. */
  net_cash_amount?: number;
  /** Net card; present only on the post-CSH-FE-036 API. */
  net_card_amount?: number;
  pending_count: number;
  pending_amount: number;
  paid_count: number;
  cancelled_count: number;
  [k: string]: unknown;
}

// P2 (PR 3830 review, comment 4439005298): the CSH-FE-036 fields are
// intentionally ABSENT from the empty snapshot — before the first
// successful load (and after a failed one) their values are UNKNOWN, not
// zero. The legacy gross counters keep the historical zero convention of
// the whole card.
const EMPTY_STATS: CashierStatsSnapshot = {
  total_amount: 0,
  cash_amount: 0,
  card_amount: 0,
  pending_count: 0,
  pending_amount: 0,
  paid_count: 0,
  cancelled_count: 0
};

export interface UseCashierWorklistDataParams {
  /** Debounced search query from the filter layer. */
  search: string;
  /** History-tab status filter ('all' means no filter). */
  status: string;
  /** Date filter inputs (panel-owned; used to compute request date params). */
  dateMode: string;
  selectedDate: string;
  dateFrom: string;
  dateTo: string;
  /** Read-only usePayments getters (single usePayments() call site = panel). */
  paymentsApi: Pick<UsePaymentsReturn, 'getStats' | 'getPendingPayments' | 'getPayments'>;
}

export const useCashierWorklistData = ({
  search,
  status,
  dateMode,
  selectedDate,
  dateFrom,
  dateTo,
  paymentsApi,
}: UseCashierWorklistDataParams) => {
  const { getStats, getPendingPayments, getPayments } = paymentsApi;

  const [payments, setPayments] = useState<Record<string, unknown>[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);

  // ✅ УЛУЧШЕНИЕ: Пагинация для истории платежей (Server-side)
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const itemsPerPage = 20;

  // ✅ v2.0: Пагинация для ожидающих оплаты
  const [pendingPage, setPendingPage] = useState(1);
  const [pendingTotalPages, setPendingTotalPages] = useState(1);
  const [pendingTotalItems, setPendingTotalItems] = useState(0);

  // ✅ УЛУЧШЕНИЕ: Ключ для принудительного обновления данных
  const [refreshKey, setRefreshKey] = useState(0);

  // ✅ УЛУЧШЕНИЕ: Статистика из API
  const [stats, setStats] = useState<CashierStatsSnapshot>(EMPTY_STATS);

  // Вычисляем параметры даты для запроса
  const getDateParams = useCallback(() => {
    if (dateMode === 'single') {
      return {
        date_from: selectedDate,
        date_to: selectedDate
      };
    } else {
      return {
        date_from: dateFrom,
        date_to: dateTo
      };
    }
  }, [dateMode, selectedDate, dateFrom, dateTo]);

  // Load Data Effect
  // ✅ v2.1: Отдельные loading состояния для каждой секции
  const [pendingLoading, setPendingLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);

  // CSH-FE-001/002: per-section failure truthfulness + stale-response
  // guards. Each effect owns a local `active` flag (the React-docs
  // "ignore stale results" pattern): the cleanup flips it on every dep
  // change and on unmount, so any response landing after its request was
  // superseded (date/search/page/refresh change or unmount) is dropped
  // BEFORE touching state.
  //
  // CSH-FE-001: a failed read is NOT a confirmed empty. The last error per
  // section is exposed (null = the last load succeeded, possibly empty);
  // rows/snapshots from the last successful load are KEPT so the views can
  // render a stale-data banner instead of a fake «no pending payments» /
  // «empty history» state. Backend stays the SSOT; nothing is invented.
  const [statsError, setStatsError] = useState<string | null>(null);
  const [pendingError, setPendingError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);

  // ✅ v2.1: ОПТИМИЗАЦИЯ - Загрузка статистики (только при изменении дат)
  useEffect(() => {
    let active = true; // CSH-FE-002: drop responses of superseded/unmounted loads
    const loadStats = async () => {
      const { date_from, date_to } = getDateParams();
      logger.log('Loading stats with params:', { date_from, date_to });

      try {
        const statsResult = await getStats({
          date_from: date_from || undefined,
          date_to: date_to || undefined
        });
        if (!active) return; // superseded/unmounted
        if ((statsResult as { success?: boolean }).success && (statsResult as { data?: Record<string, unknown> }).data) {
          setStats((statsResult as { data?: Record<string, unknown> }).data as CashierStatsSnapshot);
          setStatsError(null);
        } else {
          // CSH-FE-001: keep the previous snapshot (its values stay unknown,
          // not server-confirmed zeros) and surface the failure.
          const message = (statsResult as { error?: unknown }).error;
          setStatsError(typeof message === 'string' && message ? message : '');
        }
      } catch (error: unknown) {
        if (!active) return;
        logger.error('Error loading stats:', error);
        setStatsError(getErrorMessage(error));
      }
    };

    loadStats();
    return () => { active = false; };
  }, [getDateParams, refreshKey, getStats]);

  // ✅ v2.1: ОПТИМИЗАЦИЯ - Загрузка pending payments (только при изменении pendingPage)
  useEffect(() => {
    let active = true; // CSH-FE-002: drop responses of superseded/unmounted loads
    const loadPending = async () => {
      const { date_from, date_to } = getDateParams();
      logger.info('Loading pending payments:', { date_from, date_to, page: pendingPage });

      setPendingLoading(true);
      try {
        const pendingResult = await getPendingPayments({
          date_from: date_from || undefined,
          date_to: date_to || undefined,
          search: search || undefined,
          page: pendingPage,
          size: itemsPerPage
        });

        if (!active) return; // superseded/unmounted

        if (pendingResult.success) {
          const appointmentsData = Array.isArray(pendingResult.data) ? pendingResult.data : [];
          setAppointments(appointmentsData as Appointment[]);
          setPendingError(null);

          if (pendingResult.pagination) {
            setPendingTotalPages(pendingResult.pagination.pages);
            setPendingTotalItems(pendingResult.pagination.total);
          }
        } else {
          logger.warn('Error loading pending payments:', pendingResult.error);
          // CSH-FE-001: keep the previously loaded rows — clearing them
          // would present a server outage as «no pending payments».
          setPendingError(typeof pendingResult.error === 'string' ? pendingResult.error : '');
        }
      } catch (error: unknown) {
        if (!active) return;
        logger.error('Error loading pending payments:', error);
        setPendingError(getErrorMessage(error));
      }
      setPendingLoading(false);
    };

    loadPending();
    return () => { active = false; };
  }, [pendingPage, search, getDateParams, refreshKey, getPendingPayments]);

  // ✅ v2.1: ОПТИМИЗАЦИЯ - Загрузка истории платежей (только при изменении currentPage)
  useEffect(() => {
    let active = true; // CSH-FE-002: drop responses of superseded/unmounted loads
    const loadHistory = async () => {
      const { date_from, date_to } = getDateParams();
      logger.info('Loading payment history:', { date_from, date_to, page: currentPage, status });

      setHistoryLoading(true);
      try {
        const paymentsResult = await getPayments({
          date_from: date_from || undefined,
          date_to: date_to || undefined,
          search: search || undefined,
          status: status !== 'all' ? status : undefined,
          page: currentPage,
          size: itemsPerPage
        });

        if (!active) return; // superseded/unmounted

        if (paymentsResult.success) {
          const paymentsData = Array.isArray(paymentsResult.data) ? paymentsResult.data : [];
          setPayments(paymentsData as Record<string, unknown>[]);
          setHistoryError(null);

          if (paymentsResult.pagination) {
            setTotalPages(paymentsResult.pagination.pages);
            setTotalItems(paymentsResult.pagination.total);
          } else {
            setTotalPages(1);
            setTotalItems(paymentsData.length);
          }
        } else {
          logger.warn('Error loading payment history:', paymentsResult.error);
          // CSH-FE-001: keep the previously loaded rows and pagination —
          // clearing them would present a server outage as «empty history».
          setHistoryError(typeof paymentsResult.error === 'string' ? paymentsResult.error : '');
        }
      } catch (error: unknown) {
        if (!active) return;
        logger.error('Error loading payment history:', error);
        setHistoryError(getErrorMessage(error));
      }
      setHistoryLoading(false);
    };

    loadHistory();
    return () => { active = false; };
  }, [currentPage, search, status, getDateParams, refreshKey, getPayments]);

  // Reset page when date or search changes
  useEffect(() => {
    setCurrentPage(1);
    setPendingPage(1);
  }, [dateMode, selectedDate, dateFrom, dateTo, search]);

  const triggerDataReload = useCallback(() => {
    setCurrentPage(1);
    setPendingPage(1);
    setRefreshKey((prev) => prev + 1);
  }, []);

  // PR-UI-14-1: narrow refresh primitives previously inlined in the panel —
  // processPayment() does setPendingPage(1) + setRefreshKey(+1) WITHOUT the
  // history page reset that triggerDataReload performs; confirmPayment()
  // bumps refreshKey only. Exposed separately to keep call sites verbatim.
  const bumpRefreshKey = useCallback(() => {
    setRefreshKey((prev) => prev + 1);
  }, []);

  return {
    // server data
    payments,
    appointments,
    stats,
    // CSH-FE-001: per-section read failures (null = last load succeeded;
    // a string — possibly empty — means the last load FAILED and the rows/
    // snapshot above are the kept previous sample, not fresh data)
    statsError,
    pendingError,
    historyError,
    // loading flags
    pendingLoading,
    historyLoading,
    // history pagination
    currentPage,
    setCurrentPage,
    totalPages,
    totalItems,
    // pending pagination
    pendingPage,
    setPendingPage,
    pendingTotalPages,
    pendingTotalItems,
    // refresh lifecycle
    getDateParams,
    triggerDataReload,
    bumpRefreshKey,
  };
};
