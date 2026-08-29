/**
 * Cashier worklist data lifecycle — PR-UI-14-1 verbatim extraction from
 * pages/CashierPanel.tsx.
 *
 * Single responsibility: owning the cashier worklist DATA slice —
 * search query (+ URL patientId deep-link), status filter, date range params,
 * stats / pending-payments / payment-history loading effects, both server-side
 * paginations and the refresh lifecycle (refreshKey / triggerDataReload).
 *
 * Behavior-preservation notes (unit-pinned where observable):
 *  - every effect body and its deps array is ported 1:1 (effect re-run
 *    semantics = runtime behavior);
 *  - `query` is intentionally NOT a dep of the URL-patient effect (original
 *    stale-closure semantics preserved, incl. the eslint-disable directive);
 *  - usePayments() is instantiated exactly once per panel render tree (moved
 *    inside this hook, re-exported as `paymentsHook`); its callbacks are
 *    useCallback-stable, so effect deps behave identically;
 *  - `bumpRefreshKey()` wraps the original `setRefreshKey((prev) => prev + 1)`
 *    call shape (single state transition, call-time equivalent);
 *  - `triggerDataReload` keeps its original body: reset BOTH pages + bump key
 *    (do NOT reuse it where the original code reset only pendingPage — e.g.
 *    processPayment — that would change history-page behavior).
 */
import { useCallback, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { usePayments } from '../../hooks/usePayments';
import { useDebouncedValue } from '../../hooks/useDebouncedCallback';
import { getPatient as fetchPatientById } from '../../api/patients';
import type { Patient, Appointment } from '../../types/domain/clinic';
import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
import { getLocalDateString } from './cashierPaymentContract';

export interface CashierStats {
  total_amount: number;
  cash_amount: number;
  card_amount: number;
  pending_count: number;
  pending_amount: number;
  paid_count: number;
  cancelled_count: number;
  [k: string]: unknown;
}

const EMPTY_STATS: CashierStats = {
  total_amount: 0,
  cash_amount: 0,
  card_amount: 0,
  pending_count: 0,
  pending_amount: 0,
  paid_count: 0,
  cancelled_count: 0
};

export const useCashierWorklistData = () => {
  const location = useLocation();
  const { getStats, getPendingPayments, getPayments, ...paymentsHook } = usePayments();

  // ✅ Получаем patientId из URL для автоматического поиска
  const getPatientIdFromUrl = useCallback(() => {
    const params = new URLSearchParams(location.search);
    const patientIdParam = params.get('patientId');
    return patientIdParam ? parseInt(patientIdParam, 10) : null;
  }, [location.search]);

  // Search state - инициализируем с patientId если есть
  const [query, setQuery] = useState(() => {
    const patientId = new URLSearchParams(window.location.search).get('patientId');
    return patientId ? `patient:${patientId}` : '';
  });
  const debouncedQuery = useDebouncedValue(query, 500); // 500ms debounce

  // ✅ Эффект для загрузки пациента из URL
  useEffect(() => {
    const patientIdFromUrl = getPatientIdFromUrl();
    if (patientIdFromUrl && !query.includes(`patient:${patientIdFromUrl}`)) {
      // Загружаем данные пациента для поиска
      const loadPatientForSearch = async () => {
        try {
          // PR-53: migrated from raw fetch() to axios client
          // Wave G5: use api/patients.ts which returns domain Patient via mapper
          const token = tokenManager.getAccessToken();
          if (!token) return;

          const patientData: Patient = await fetchPatientById(patientIdFromUrl);
          const patientName = `${patientData.last_name || ''} ${patientData.first_name || ''}`.trim();
          setQuery(patientName);
          logger.info('[Cashier] Patient loaded from URL', { patientId: patientData?.id });
        } catch (error: unknown) {
          logger.error('[Cashier] Не удалось загрузить пациента:', error);
        }
      };
      loadPatientForSearch();
    }
  }, [location.search, getPatientIdFromUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  const [status, setStatus] = useState('all');
  const [payments, setPayments] = useState<Record<string, unknown>[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);

  // Состояния для календаря
  const [dateMode, setDateMode] = useState('single'); // 'single' | 'range'
  const [selectedDate, setSelectedDate] = useState(() => getLocalDateString());
  const [dateFrom, setDateFrom] = useState(() => getLocalDateString());
  const [dateTo, setDateTo] = useState(() => getLocalDateString());

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
  const [stats, setStats] = useState<CashierStats>({ ...EMPTY_STATS });

  // Load Data Effect
  // ✅ v2.1: Отдельные loading состояния для каждой секции
  const [pendingLoading, setPendingLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);

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
          setStats((statsResult as { data?: Record<string, unknown> }).data as CashierStats);
        }
      } catch (error: unknown) {
        logger.error('Error loading stats:', error);
        setStats({ ...EMPTY_STATS });
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
          search: debouncedQuery || undefined,
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
  }, [pendingPage, debouncedQuery, getDateParams, refreshKey, getPendingPayments]);

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
          search: debouncedQuery || undefined,
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
  }, [currentPage, debouncedQuery, status, getDateParams, refreshKey, getPayments]);

  // Reset page when date or search changes
  useEffect(() => {
    setCurrentPage(1);
    setPendingPage(1);
  }, [dateMode, selectedDate, dateFrom, dateTo, debouncedQuery]);

  const triggerDataReload = useCallback(() => {
    setCurrentPage(1);
    setPendingPage(1);
    setRefreshKey((prev) => prev + 1);
  }, []);

  // Wraps the original `setRefreshKey((prev) => prev + 1)` call shape — single
  // state transition, call-time equivalent to the inline original.
  const bumpRefreshKey = useCallback(() => {
    setRefreshKey((prev) => prev + 1);
  }, []);

  return {
    // Payments SSOT API (rest of usePayments — stable useCallback identities).
    // Kept under the original `paymentsHook` name so panel handler bodies stay verbatim.
    paymentsHook,
    // Search
    query, setQuery, debouncedQuery,
    // Status filter
    status, setStatus,
    // Worklist data
    payments, appointments, stats,
    // Date range
    dateMode, setDateMode,
    selectedDate, setSelectedDate,
    dateFrom, setDateFrom,
    dateTo, setDateTo,
    // History pagination
    currentPage, setCurrentPage, totalPages, totalItems,
    // Pending pagination
    pendingPage, setPendingPage, pendingTotalPages, pendingTotalItems,
    // Loading
    pendingLoading, historyLoading,
    // Refresh lifecycle
    refreshKey, bumpRefreshKey, triggerDataReload,
    // Date params
    getDateParams,
  };
};

export default useCashierWorklistData;
