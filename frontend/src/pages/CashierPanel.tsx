import { useEffect, useState, useCallback } from 'react';
import './cashier.css';
import { useLocation } from 'react-router-dom';
import { CreditCard, DollarSign, RefreshCw } from 'lucide-react';
import { Card } from '../components/ui/macos';
import { useConfirm } from '../components/common/ConfirmDialog';
import MacOSTab from '../components/ui/macos/MacOSTab';
// PR-UI-14-5 (plan item 4): локальный ErrorBoundary вокруг контента панели.
import ErrorBoundary from '../components/common/ErrorBoundary';

// ✅ УЛУЧШЕНИЕ: Универсальные хуки для устранения дублирования
import useModal from '../hooks/useModal';
import { usePayments } from '../hooks/usePayments';
import { useDebouncedValue } from '../hooks/useDebouncedCallback';
import { getPatient as fetchPatientById } from '../api/patients';
import type { Patient } from '../types/domain/clinic';
import tokenManager from '../utils/tokenManager';
import logger from '../utils/logger';
// STRAT#31: useTranslation adapter for confirm/notify i18n.
import { useTranslation } from '../i18n/useTranslation';
import type { Appointment } from '../types/domain/clinic';
import {
  getLocalDateString,
  DATE_PRESETS,
} from './cashier/cashierPaymentContracts';
import { useCashierWorklistData } from './cashier/useCashierWorklistData';
import {
  groupPaymentsByPatientAndTime,
  sortCashierPayments,
  type CashierSortField,
  type CashierSortDir,
} from './cashier/cashierPaymentRows';
import { useCashierDialogs } from './cashier/useCashierDialogs';
import { useCashierSessionWarning } from './cashier/useCashierSessionWarning';
import { useCashierActions } from './cashier/useCashierActions';
// PR-UI-14-5: presentation moved verbatim to ./cashier/views/*.
import CashierFiltersCard from './cashier/views/CashierFiltersCard';
import CashierStatsCard from './cashier/views/CashierStatsCard';
import CashierPendingTable from './cashier/views/CashierPendingTable';
import CashierHistoryTable from './cashier/views/CashierHistoryTable';
import CashierDialogsLayer from './cashier/views/CashierDialogsLayer';

// ✅ Компоненты для возвратов
import RefundRequestsTable from '../components/cashier/RefundRequestsTable';


const CashierPanel = () => {
  // P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
  // The hook returns [confirm, dialogNode]; dialogNode must be rendered once
  // in the component tree (we render it at the end of the JSX below).
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw;
  // STRAT#31: useTranslation adapter for confirm/notify i18n.
  const { t: tI18n } = useTranslation();
  const location = useLocation();
  const { getStats, getPendingPayments, getPayments, ...paymentsHook } = usePayments();
  // ✅ v2.1: isLoading теперь вычисляется из отдельных loading состояний (см. ниже)

  const datePresets = DATE_PRESETS.map((p) => ({
    ...p,
    label: tI18n(`cashier.range_${p.id}`),
  }));

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
  // UX Audit #2.4: показывать подсказку с примерами синтаксиса поиска,
  // пока input в фокусе и запрос пустой.
  const [searchFocused, setSearchFocused] = useState(false);
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

  // PR-UI-14-3: dialog state machines moved verbatim to
  // ./cashier/useCashierDialogs (12 useState -> 1 useReducer) and
  // ./cashier/useCashierSessionWarning (warning + countdown + redirect).
  const {
    state: dialogs,
    setPaymentSuccess, setPaymentError, clearPaymentFeedback,
    openCancelDialog: openCancelDialogAction,
    closeCancelDialog, resetCancelDialog, setCancelReason,
    openRefundDialog: openRefundDialogAction,
    closeRefundDialog, resetRefundDialog, setRefundAmount, setRefundReason,
    showHourlyStats, closeHourlyChart,
  } = useCashierDialogs();
  const {
    sessionWarning, sessionSecondsLeft, dismissSessionWarning,
  } = useCashierSessionWarning();

  // PR-UI-14-3: flattened dialog state bindings (verbatim names, so every
  // handler/JSX reference below keeps reading exactly like before).
  const {
    paymentSuccess, paymentError,
    cancelPaymentContext, cancelDialogOpen, cancelReason,
    refundDialogOpen, refundPaymentId, refundPaymentAmount, refundAmount, refundReason,
    hourlyStats, showHourlyChart,
  } = dialogs;

  // Состояния для календаря
  const [dateMode, setDateMode] = useState('single'); // 'single' | 'range'
  const [selectedDate, setSelectedDate] = useState(() => getLocalDateString());
  const [dateFrom, setDateFrom] = useState(() => getLocalDateString());
  const [dateTo, setDateTo] = useState(() => getLocalDateString());

  // PR-UI-14-1: data lifecycle (stats/pending/history fetch + pagination +
  // refresh lifecycle) moved verbatim to ./cashier/useCashierWorklistData.
  const {
    payments, appointments, stats,
    pendingLoading, historyLoading,
    currentPage, setCurrentPage, totalPages, totalItems,
    pendingPage, setPendingPage, pendingTotalPages, pendingTotalItems,
    getDateParams, triggerDataReload, bumpRefreshKey,
  } = useCashierWorklistData({
    search: debouncedQuery,
    status,
    dateMode, selectedDate, dateFrom, dateTo,
    paymentsApi: { getStats, getPendingPayments, getPayments },
  });

  // Состояние для вкладок
  const [activeTab, setActiveTab] = useState('pending'); // 'pending' | 'history'



  // UX Audit #4.2: client-side sort state для таба «История платежей».
  // Сортировка применяется к уже загруженным filteredPayments (после groupPaymentsByPatientAndTime).
  // Поддерживаемые поля: 'date' | 'patient' | 'amount'.
  const [sortField, setSortField] = useState<CashierSortField>('date');
  const [sortDir, setSortDir] = useState<CashierSortDir>('desc'); // 'asc' | 'desc'

  // ✅ УЛУЧШЕНИЕ: Универсальные хуки вместо дублированных состояний
  const paymentModal = useModal();
  const paymentWidget = useModal();

  // PR-UI-14-4: business-action handlers + hotkeys + anti-double-click guard
  // moved verbatim to ./cashier/useCashierActions (13-5 deps-object precedent).
  const {
    processingAction,
    handlePaymentSuccess, handlePaymentError, handlePaymentCancel,
    openPaymentWidget, processPayment,
    confirmPayment, openCancelDialog, handleCancelPayment,
    exportToCSV, handleRefresh,
    openRefundDialog, handleRefund,
    handlePrintReceipt, loadHourlyStats,
  } = useCashierActions({
    confirm,
    tI18n,
    paymentsApi: paymentsHook,
    worklist: { getDateParams, setPendingPage, bumpRefreshKey, triggerDataReload },
    dialogs: {
      setPaymentSuccess, setPaymentError, clearPaymentFeedback,
      openCancelDialog: openCancelDialogAction,
      resetCancelDialog,
      openRefundDialog: openRefundDialogAction,
      resetRefundDialog,
      showHourlyStats,
    },
    dialogValues: {
      cancelPaymentContext, cancelReason,
      refundPaymentId, refundAmount, refundReason,
    },
    paymentModal,
    paymentWidget,
    selectedDate,
  });

  // Group payments for display (already filtered by server)
  // UX Audit #4.2: client-side sort по sortField/sortDir.
  const toggleSort = (field: CashierSortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  // PR-UI-14-2: grouping + client-side sort moved verbatim to
  // ./cashier/cashierPaymentRows.ts (presentation-only view-model).
  const groupedPayments = groupPaymentsByPatientAndTime(payments);
  const sortedPayments = sortCashierPayments(groupedPayments, sortField, sortDir);

  const filteredPayments = sortedPayments;


  return (
    <div className="cashier-root">

      <div className="cashier-root-inner">
        <div className="max-w-7xl mx-auto space-y-6">

          {/* UX Audit #3.5: page header для ориентира (Nielsen #1 —
              visibility of system status). hideSidebar:true убирает боковую
              навигацию, поэтому без заголовка кассир теряет контекст страницы. */}
          <header className="cashier-page-header">
            <h1 className="cashier-page-title">{tI18n('cashier.title')}</h1>
            <p className="cashier-page-subtitle">
              {tI18n('cashier.subtitle', { date: new Date().toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }) })}
            </p>
          </header>

          {/* Filters — PR-UI-14-5: verbatim JSX moved to views/CashierFiltersCard */}
          <CashierFiltersCard
            query={query}
            onQueryChange={setQuery}
            searchFocused={searchFocused}
            onSearchFocusedChange={setSearchFocused}
            showStatusFilter={activeTab === 'history'}
            status={status}
            onStatusChange={setStatus}
            dateMode={dateMode}
            onDateModeChange={setDateMode}
            selectedDate={selectedDate}
            onSelectedDateChange={setSelectedDate}
            dateFrom={dateFrom}
            onDateFromChange={setDateFrom}
            dateTo={dateTo}
            onDateToChange={setDateTo}
            datePresets={datePresets}
            tI18n={tI18n} />

          {/* Stats + toolbar — PR-UI-14-5: verbatim JSX moved to views/CashierStatsCard */}
          <CashierStatsCard
            isHistoryTab={activeTab === 'history'}
            stats={stats}
            onRefresh={handleRefresh}
            onExport={exportToCSV}
            onHourlyStats={loadHourlyStats}
            tI18n={tI18n} />

          {/* Объединенная секция с вкладками */}
          {/* PR-UI-14-5 (plan §PR-UI-14 item 4): локальный ErrorBoundary вокруг
              основного контента панели (tabs + таблицы) — падение рендера любой
              из таблиц не уронит всю страницу кассира (registrar 13-4 precedent). */}
          <ErrorBoundary>
            <Card
              variant="default"
              padding="default">

              <MacOSTab
                tabs={[
                {
                  id: 'pending',
                  label: tI18n('cashier.tab_pending'),
                  icon: DollarSign,
                  badge: appointments.length > 0 ? appointments.length : undefined
                },
                {
                  id: 'history',
                  label: tI18n('cashier.tab_history'),
                  icon: CreditCard,
                  // UX Audit #3.3: badge с totalItems для консистентности.
                  badge: totalItems > 0 ? totalItems : undefined
                },
                {
                  id: 'refunds',
                  label: tI18n('cashier.tab_refunds'),
                  icon: RefreshCw
                  // UX Audit #3.3: badge для refunds будет добавлен в отдельном PR,
                  // когда RefundRequestsTable будет экспортировать свой count через callback.
                  // Сейчас показ badge без данных вводил бы в заблуждение.
                }]
                }
                activeTab={activeTab}
                onTabChange={(newTab) => {
                  // UX Audit #3.6: сброс пагинации при смене таба.
                  // Раньше: пользователь на табе «История», стр. 5 → переключился
                  // на «Ожидающие» → вернулся → оказался на стр. 5 истории,
                  // хотя ожидал стр. 1 (Nielsen #1 — visibility of system status).
                  setActiveTab(String(newTab));
                  setCurrentPage(1);
                  setPendingPage(1);
                }}
                size="md"
                variant="default" />


              {/* PR-UI-14-5: pending table — verbatim JSX moved to views/CashierPendingTable */}
              {activeTab === 'pending' &&
                <CashierPendingTable
                  appointments={appointments}
                  pendingLoading={pendingLoading}
                  pendingPage={pendingPage}
                  onPendingPageChange={setPendingPage}
                  pendingTotalPages={pendingTotalPages}
                  pendingTotalItems={pendingTotalItems}
                  openPaymentWidget={openPaymentWidget}
                  onOpenCashPaymentModal={(appointment) => {
                    paymentModal.openModal(appointment as unknown as null);
                  }}
                  onOpenHistory={() => setActiveTab('history')}
                  tI18n={tI18n} />
              }

              {/* PR-UI-14-5: history table — verbatim JSX moved to views/CashierHistoryTable */}
              {activeTab === 'history' &&
                <CashierHistoryTable
                  historyLoading={historyLoading}
                  filteredPayments={filteredPayments}
                  sortField={sortField}
                  sortDir={sortDir}
                  onToggleSort={toggleSort}
                  confirmPayment={confirmPayment}
                  openCancelDialog={openCancelDialog}
                  openRefundDialog={openRefundDialog}
                  handlePrintReceipt={handlePrintReceipt}
                  processingAction={processingAction}
                  currentPage={currentPage}
                  onCurrentPageChange={setCurrentPage}
                  totalPages={totalPages}
                  totalItems={totalItems}
                  tI18n={tI18n} />
              }

              {/* Вкладка Возвраты */}
              {activeTab === 'refunds' &&
              <div className="cashier-section-gap">
                  <RefundRequestsTable onRefresh={handleRefresh} />
                </div>
              }
            </Card>
          </ErrorBoundary>

          {/* PR-UI-14-5: all modal surfaces — verbatim JSX moved to
              views/CashierDialogsLayer (cancel/payment/success/refund/hourly
              dialogs + session warning overlay + confirm dialog node). */}
          <CashierDialogsLayer
            cancelDialogOpen={cancelDialogOpen}
            closeCancelDialog={closeCancelDialog}
            cancelPaymentContext={cancelPaymentContext}
            cancelReason={cancelReason}
            setCancelReason={setCancelReason}
            handleCancelPayment={handleCancelPayment}
            processingAction={processingAction}
            paymentModal={paymentModal}
            processPayment={processPayment}
            paymentWidget={paymentWidget}
            handlePaymentSuccess={handlePaymentSuccess}
            handlePaymentError={handlePaymentError}
            handlePaymentCancel={handlePaymentCancel}
            paymentError={paymentError}
            paymentSuccess={paymentSuccess}
            setPaymentSuccess={setPaymentSuccess}
            refundDialogOpen={refundDialogOpen}
            closeRefundDialog={closeRefundDialog}
            refundPaymentAmount={refundPaymentAmount}
            refundAmount={refundAmount}
            setRefundAmount={setRefundAmount}
            refundReason={refundReason}
            setRefundReason={setRefundReason}
            handleRefund={handleRefund}
            showHourlyChart={showHourlyChart}
            closeHourlyChart={closeHourlyChart}
            hourlyStats={hourlyStats}
            selectedDate={selectedDate}
            sessionWarning={sessionWarning}
            sessionSecondsLeft={sessionSecondsLeft}
            dismissSessionWarning={dismissSessionWarning}
            confirmDialog={confirmDialog}
            tI18n={tI18n} />
        </div>
      </div>
    </div>);

};

export default CashierPanel;
