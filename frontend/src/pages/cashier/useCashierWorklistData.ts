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
import type { Appointment } from '../../types/domain/clinic';
import type { UsePaymentsReturn } from '../../hooks/usePayments';

// ✅ УЛУЧШЕНИЕ: Статистика из API (shape moved verbatim from CashierPanel).
export interface CashierStatsSnapshot {
  total_amount: number;
  cash_amount: number;
  card_amount: number;
  pending_count: number;
  pending_amount: number;
  paid_count: number;
  cancelled_count: number;
  [k: string]: unknown;
}

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

  // ✅ v2.1: ОПТИМИЗАЦИЯ - Загрузка статистики (только при изменении дат)
  useEffect(() => {
    const loadStats = async () => {
      const { date_from, date_to } = getDateParams();
      logger.log('Loading stats with params:', { date_from, date_to });

      try {
        const statsResult = await getStats({
          date_from: date_from || undefined,
          date_to: date_to || undefined
        });
        if ((statsResult as { success?: boolean }).success && (statsResult as { data?: Record<string, unknown> }).data) {
          setStats((statsResult as { data?: Record<string, unknown> }).data as CashierStatsSnapshot);
        }
      } catch (error: unknown) {
        logger.error('Error loading stats:', error);
        setStats(EMPTY_STATS);
      }
    };

    loadStats();
  }, [getDateParams, refreshKey, getStats]);

  // ✅ v2.1: ОПТИМИЗАЦИЯ - Загрузка pending payments (только при изменении pendingPage)
  useEffect(() => {
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

        if (pendingResult.success) {
          const appointmentsData = Array.isArray(pendingResult.data) ? pendingResult.data : [];
          setAppointments(appointmentsData as Appointment[]);

          if (pendingResult.pagination) {
            setPendingTotalPages(pendingResult.pagination.pages);
            setPendingTotalItems(pendingResult.pagination.total);
          }
        } else {
          logger.warn('Error loading pending payments:', pendingResult.error);
          setAppointments([]);
        }
      } catch (error: unknown) {
        logger.error('Error loading pending payments:', error);
        setAppointments([]);
      }
      setPendingLoading(false);
    };

    loadPending();
  }, [pendingPage, search, getDateParams, refreshKey, getPendingPayments]);

  // ✅ v2.1: ОПТИМИЗАЦИЯ - Загрузка истории платежей (только при изменении currentPage)
  useEffect(() => {
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

        if (paymentsResult.success) {
          const paymentsData = Array.isArray(paymentsResult.data) ? paymentsResult.data : [];
          setPayments(paymentsData as Record<string, unknown>[]);

          if (paymentsResult.pagination) {
            setTotalPages(paymentsResult.pagination.pages);
            setTotalItems(paymentsResult.pagination.total);
          } else {
            setTotalPages(1);
            setTotalItems(paymentsData.length);
          }
        } else {
          logger.warn('Error loading payment history:', paymentsResult.error);
          setPayments([]);
          setTotalPages(1);
        }
      } catch (error: unknown) {
        logger.error('Error loading payment history:', error);
        setPayments([]);
      }
      setHistoryLoading(false);
    };

    loadHistory();
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
