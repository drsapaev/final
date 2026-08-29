import { useEffect, useState, useCallback, useRef } from 'react';
import './cashier.css';
import { useLocation } from 'react-router-dom';
import { CreditCard, Calendar, Search, CheckCircle, DollarSign, RefreshCw, XCircle, Undo2, Receipt, MoreVertical, Loader2 } from 'lucide-react';
import {
  Card, Badge, Button,
} from '../components/ui/macos';
import { useConfirm } from '../components/common/ConfirmDialog';
import Tooltip from '../components/ui/macos/Tooltip';
import PaymentWidget from '../components/payment/PaymentWidget';
import CashPaymentModal from '../components/payment/CashPaymentModal';
import MacOSTab from '../components/ui/macos/MacOSTab';
import SegmentedControl from '../components/ui/macos/SegmentedControl';
import Input from '../components/ui/macos/Input';

// ✅ УЛУЧШЕНИЕ: Универсальные хуки для устранения дублирования
import useModal from '../hooks/useModal';
import { usePayments } from '../hooks/usePayments';
import { useDebouncedValue } from '../hooks/useDebouncedCallback';
import { useHotkeys } from '../hooks/useHotkeys';
import { getPatient as fetchPatientById } from '../api/patients';
import type { Patient } from '../types/domain/clinic';
import { printPanelReceiptInBrowser } from '../services/panelPrint';
import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';
import { getErrorMessage } from '../utils/errorHandler';
import { formatRegistrarDate, formatRegistrarTime } from '../utils/dateUtils';
import notify from '../services/notify';
// STRAT#31: useTranslation adapter for confirm/notify i18n.
import { useTranslation } from '../i18n/useTranslation';
import type { Appointment } from '../types/domain/clinic';
import type { Transaction } from '../types/domain/clinic';
import { formatUZS } from '../utils/formatCurrency';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  Box,
  Alert,
  Skeleton,
} from '../components/ui/macos';
// UX Audit #4.6: Recharts для почасовой статистики (вместо inline-баров на Box sx).
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
} from 'recharts';

// ✅ Компоненты для возвратов
import RefundRequestsTable from '../components/cashier/RefundRequestsTable';

// PR-UI-14-1: module-scope payment contracts & pure helpers moved verbatim
// to ./cashier/cashierPaymentContracts.ts (behavior-preserving decomposition).
import {
  getLocalDateString,
  DATE_PRESETS,
  buildPaymentMethodLabels,
  resolvePaymentId,
  buildReceiptPrintPayload,
  getPaymentStatusMeta,
  getPaymentStatusLabel,
  resolveSingleCashierVisitId,
  isBackendGroupedCashierPayment,
  canCreateDirectCashierPayment,
  canCreateCashierPayment,
  createGroupedCashierPayment,
  hasBackendPaymentAction,
  type CashierPaymentRow,
  type CashierPaymentRowOrId,
  type CashierPaymentData,
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

  // STRAT#31 i18n: localized helpers (reactive to language changes via tI18n).
  // paymentMethodLabels — replaces module-level PAYMENT_METHOD_LABELS constant.
  // datePresets — DATE_PRESETS with localized labels; uses stable `id` for option matching.
  const paymentMethodLabels = buildPaymentMethodLabels(tI18n);
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


  // UX Audit #4.5: anti-double-click state для action-кнопок.
  // Хранит {type, id} текущего action; пока не null — все action-кнопки disabled.
  const [processingAction, setProcessingAction] = useState<{ type?: string; id?: string | number } | null>(null);

  // UX Audit #4.2: client-side sort state для таба «История платежей».
  // Сортировка применяется к уже загруженным filteredPayments (после groupPaymentsByPatientAndTime).
  // Поддерживаемые поля: 'date' | 'patient' | 'amount'.
  const [sortField, setSortField] = useState<CashierSortField>('date');
  const [sortDir, setSortDir] = useState<CashierSortDir>('desc'); // 'asc' | 'desc'

  // ✅ УЛУЧШЕНИЕ: Универсальные хуки вместо дублированных состояний
  const paymentModal = useModal();
  const paymentWidget = useModal();

  // MEDIUM #15: CashierPanel hotkeys — focus search (Ctrl+F), refresh (F5 / Ctrl+R), export (Ctrl+E).
  // Only triggers when not focused in input/textarea to avoid hijacking text entry.
  // Note: handlers use lazy references via refs because some callbacks (exportToCSV)
  // are defined further down in the component body.
  const handlersRef = useRef({} as { refresh?: () => void; export?: () => void });
  useHotkeys({
    'ctrl+f': (e) => {
      e.preventDefault();
      const node = document.getElementById('cashier-search-input');
      if (node) node.focus();
    },
    'f5': (e) => {
      e.preventDefault();
      handlersRef.current.refresh?.();
    },
    'ctrl+r': (e) => {
      e.preventDefault();
      handlersRef.current.refresh?.();
    },
    'ctrl+e': (e) => {
      e.preventDefault();
      handlersRef.current.export?.();
    },
  });

  // UX Audit #2.3: используем единый formatUZS из utils/formatCurrency.js.
  // Раньше тут было inline-определение new Intl.NumberFormat('ru-RU').format(n) + ' сум',
  // что приводило к расхождениям с CashPaymentModal (formatCurrency → «UZS»)
  // и RefundRequestsTable (toLocaleString + «сум»).
  const format = formatUZS;

  // ✅ УЛУЧШЕНИЕ: Обработчики с универсальными хуками
  const handlePaymentSuccess = (paymentData: unknown) => {
    setPaymentSuccess(paymentData as Record<string, unknown>);
    paymentWidget.closeModal();
    // Force reload to get fresh data after successful payment.
    triggerDataReload();
  };

  const handlePaymentError = (error: unknown) => {
    const message = getErrorMessage(error, tI18n('cashier.payment_process_failed'));
    setPaymentError(message);
    logger.error('Ошибка платежа:', error);
  };

  const handlePaymentCancel = () => {
    paymentWidget.closeModal();
  };

  const openPaymentWidget = (appointment: Appointment) => {
    if (!canCreateDirectCashierPayment(appointment) || isBackendGroupedCashierPayment(appointment)) {
      const message = tI18n('cashier.online_payment_group_unavailable');
      setPaymentError(message);
      notify.error(message);
      return;
    }
    paymentWidget.openModal(appointment as unknown as null);
    clearPaymentFeedback();
  };

  // ✅ УЛУЧШЕНИЕ: Функции для работы с оплатами через SSOT hook
  // Теперь appointment содержит сгруппированные данные пациента (все его неоплаченные визиты)
  const processPayment = async (appointment: unknown, paymentData: unknown) => {
    // CashPaymentModal declares `onProcessPayment?: (...args: unknown[]) => Promise<void>`
    // so the args arrive as `unknown`. Narrow to domain types for the body.
    const appt = appointment as Appointment;
    const pData = paymentData as CashierPaymentData;
    try {
      const groupedPayment = isBackendGroupedCashierPayment(appt);
      const visitId = resolveSingleCashierVisitId(appt);

      if (!groupedPayment && !visitId) {
        throw new Error('Cannot process payment: backend must provide exactly one visit_id or a backend-owned allocation contract.');
      }

      if (groupedPayment) {
        await createGroupedCashierPayment(appt, pData);
      } else {
        const result = await paymentsHook.createPayment({
          visit_id: visitId,
          amount: pData.amount,
          method: pData.method,
          note: pData.note || tI18n('cashier.payment_note_default')
        });

        if (!(result as { success?: boolean }).success) {
          throw new Error(tI18n('cashier.payment_visit_failed', { visitId, error: (result as { error?: string }).error }));
        }
      }

      notify.success(tI18n('cashier.payment_success', { amount: format(pData.amount) }));
      paymentModal.closeModal();
      setPendingPage(1);
      bumpRefreshKey(); // Принудительное обновление списка

    } catch (error: unknown) {
      logger.error('Ошибка обработки платежа:', error);
      const message = getErrorMessage(error, tI18n('cashier.payment_process_failed'));
      setPaymentError(message);
      notify.error(message);
    }
  };

  // ✅ УЛУЧШЕНИЕ: Функции для работы с кнопками в истории платежей
  const confirmPayment = async (paymentId: string | number | undefined) => {
    if (paymentId === undefined) {
      notify.error(tI18n('cashier.no_payment_for_receipt'));
      return;
    }
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    // The new dialog names the specific action and uses primary intent
    // (Confirm is a constructive action, not destructive).
    const ok = await confirm({
      title: tI18n('cashier.confirm_payment_title'),
      message: tI18n('cashier.confirm_payment_message'),
      description: tI18n('cashier.confirm_payment_description'),
      confirmLabel: tI18n('cashier.confirm_payment_confirm'),
      cancelLabel: tI18n('cashier.cancel'),
      intent: 'primary',
    });
    if (!ok) {
      return;
    }

    try {
      // UX Audit #4.5: anti-double-click protection.
      setProcessingAction({ type: 'confirm', id: paymentId });
      await paymentsHook.confirmPayment(paymentId);
      bumpRefreshKey(); // Обновляем данные
    } catch (err) {
      logger.error('Error confirming payment:', err);
      notify.error(getErrorMessage(err, tI18n('cashier.payment_confirm_failed')));
    } finally {
      setProcessingAction(null);
    }
  };

  const openCancelDialog = (payment: CashierPaymentRowOrId) => {
    // UX Audit #2.1: принимаем объект payment целиком, чтобы показать контекст.
    // Раньше принимали только paymentId, и в диалоге было видно только #{id}.
    const paymentRow = typeof payment === 'object' && payment !== null ? payment : null;
    const paymentId: string | number | undefined = paymentRow
      ? (paymentRow.id || paymentRow.payment_id)
      : (typeof payment === 'string' || typeof payment === 'number' ? payment : undefined);
    const patient = paymentRow
      ? (paymentRow.patient || paymentRow.patient_name || tI18n('cashier.patient_with_id', { id: paymentRow.patient_id }))
      : null;
    const amount = paymentRow
      ? Number(paymentRow.total_amount || paymentRow.amount || 0)
      : 0;
    openCancelDialogAction({ id: paymentId, patient, amount });
  };

  const handleCancelPayment = async () => {
    if (!cancelPaymentContext?.id) return;
    // UX Audit #2.1: обязательная причина отмены (минимум 10 символов).
    // Раньше textarea была помечена «необязательно» — аудит-лог пустовал.
    if (!cancelReason || cancelReason.trim().length < 10) {
      notify.warning(tI18n('cashier.cancel_reason_required'));
      return;
    }

    try {
      // UX Audit #4.5: anti-double-click protection.
      setProcessingAction({ type: 'cancel', id: cancelPaymentContext.id });
      const result = await paymentsHook.cancelPayment(cancelPaymentContext.id, cancelReason.trim());
      if ((result as { success?: boolean }).success) {
        resetCancelDialog();
        notify.info(tI18n('cashier.payment_cancelled'));
        triggerDataReload();
      } else {
        notify.error(getErrorMessage((result as { error?: string }).error, tI18n('cashier.refund_failed')));
      }
    } catch (error: unknown) {
      notify.error(getErrorMessage(error, tI18n('cashier.cancel_failed')));
    } finally {
      setProcessingAction(null);
    }
  };

  // ✅ УЛУЧШЕНИЕ: Экспорт в CSV через серверный endpoint
  const exportToCSV = async () => {
    const { date_from, date_to } = getDateParams();
    const result = await paymentsHook.exportPayments({
      date_from: date_from || undefined,
      date_to: date_to || undefined
    });

      if (!(result as { success?: boolean }).success) {
        notify.error(
          getErrorMessage(
            (result as { error?: string }).error,
            tI18n('cashier.export_failed')
          )
        );
      }
  };

  // ✅ УЛУЧШЕНИЕ: Кнопка обновления данных
  const handleRefresh = () => {
    triggerDataReload();
  };

  // Sync hotkey handlers ref (MEDIUM #15)
  handlersRef.current.refresh = handleRefresh;
  handlersRef.current.export = exportToCSV;


  // ✅ v2.0: Обработчик открытия диалога возврата
  const openRefundDialog = (payment: CashierPaymentRow) => {
    openRefundDialogAction(payment);
  };

  // ✅ v2.0: Обработчик возврата
  const handleRefund = async () => {
    if (!refundAmount || !refundReason || refundReason.length < 3) {
      notify.warning(tI18n('cashier.refund_fields_required'));
      return;
    }
    try {
      // UX Audit #4.5: anti-double-click protection.
      setProcessingAction({ type: 'refund', id: refundPaymentId ?? undefined });
      const result = await paymentsHook.refundPayment(refundPaymentId ?? 0, {
        amount: parseFloat(refundAmount),
        reason: refundReason
      });
      if ((result as { success?: boolean }).success) {
        resetRefundDialog();
        notify.success(tI18n('cashier.refund_success_amount', { amount: ((result as { data?: { refunded_amount?: number } }).data?.refunded_amount) }));
        triggerDataReload();
      } else {
        notify.error(getErrorMessage((result as { error?: string }).error, tI18n('cashier.refund_create_failed')));
      }
    } catch (error: unknown) {
      notify.error(getErrorMessage(error, tI18n('cashier.refund_failed')));
    } finally {
      setProcessingAction(null);
    }
  };

  // ✅ v2.0: Обработчик печати чека
  const handlePrintReceipt = async (paymentRowOrId: CashierPaymentRowOrId) => {
    const paymentId = resolvePaymentId(paymentRowOrId);

    if (!paymentId) {
      notify.error(tI18n('cashier.no_payment_for_receipt'));
      return;
    }

    // UX Audit #4.5: anti-double-click protection.
    setProcessingAction({ type: 'print_receipt', id: paymentId });
    try {
      if (paymentRowOrId && typeof paymentRowOrId === 'object') {
        try {
          const opened = printPanelReceiptInBrowser(buildReceiptPrintPayload(paymentRowOrId, paymentMethodLabels, tI18n('cashier.default_patient')));
          if (opened) {
            notify.success(tI18n('cashier.print_dialog_opened'));
            return;
          }

          logger.warn('[Cashier] Browser receipt print popup blocked, falling back to PDF', {
            paymentId
          });
        } catch (error: unknown) {
          logger.error('[Cashier] Unexpected browser receipt print error:', error);
        }
      }

      const result = await paymentsHook.getReceipt(paymentId);
      if (!(result as { success?: boolean }).success) {
        notify.error(getErrorMessage((result as { error?: string }).error, tI18n('cashier.receipt_load_failed')));
        return;
      }

      notify.warning(tI18n('cashier.print_dialog_failed'));
    } finally {
      setProcessingAction(null);
    }
  };


  // ✅ v2.0: Загрузка почасовой статистики
  const loadHourlyStats = async () => {
    const result = await paymentsHook.getHourlyStats({ target_date: selectedDate });
    if ((result as { success?: boolean }).success) {
      showHourlyStats(((result as { data?: unknown }).data as unknown[]) || []);
    } else {
      notify.error(getErrorMessage((result as { error?: string }).error, tI18n('cashier.stats_load_failed')));
    }
  };

  // ✅ ОТОБРАЖЕНИЕ УСЛУГ: Рендерим коды услуг с бейджами и tooltip (как в RegistrarPanel)
  const renderServiceBadges = (serviceCodes: unknown, serviceNames: unknown) => {
    // Если нет кодов, возвращаем пустой элемент
    if (!serviceCodes || !Array.isArray(serviceCodes) || serviceCodes.length === 0) {
      return <span className="cashier-empty">—</span>;
    }

    type ServiceObject = { id?: string | number; name?: string; code?: string; price?: number; quantity?: number };
    // ✅ ИСПРАВЛЕНИЕ: Обрабатываем случай когда services - это массив объектов {id, name, price, quantity}
    let codes: unknown[] = serviceCodes;
    let names: unknown = serviceNames;

    // Проверяем, является ли первый элемент объектом
    if (serviceCodes.length > 0 && typeof serviceCodes[0] === 'object' && serviceCodes[0] !== null) {
      // Извлекаем имена услуг из объектов
      const serviceObjs = serviceCodes as ServiceObject[];
      codes = serviceObjs.map((s) => s.name || s.code || tI18n('cashier.service_fallback', { id: s.id || '?' }));
      names = serviceObjs.map((s) => {
        const parts: string[] = [];
        if (s.name) parts.push(s.name);
        if (s.price) parts.push(formatUZS(s.price));
        if (s.quantity && s.quantity > 1) parts.push(`x${s.quantity}`);
        return parts.length > 0 ? parts.join(' — ') : tI18n('cashier.service_fallback', { id: s.id || '?' });
      });
    }

    // Создаем tooltip с полными названиями услуг
    const tooltipContent =
    <div className="cashier-tooltip">
        {names && Array.isArray(names) && names.length === codes.length ?
      names.map((name, idx) =>
      <div key={idx} className="cashier-tooltip-row">
              {name}
            </div>
      ) :
      codes.map((code, idx) =>
      <div key={idx} className="cashier-tooltip-row">
              {typeof code === 'string' ? code : String(code)}
            </div>
      )
      }
      </div>;


    return (
      <Tooltip
        content={tooltipContent}
        position="bottom"
        delay={200}
        followCursor>

        <div className="cashier-badge-wrap">
          {/* UX Audit #4.1: показываем только первые 2 бейджа + счётчик «+N».
              Раньше все бейджи рендерились, что раздувало строку при 5+ услугах. */}
          {codes.slice(0, 2).map((code, idx) =>
          <span key={idx} className="cashier-badge">
              {typeof code === 'string' ? code : String(code)}
            </span>
          )}
          {codes.length > 2 && (
            <span className="cashier-badge cashier-badge-more" title={tI18n('cashier.services_more', { count: codes.length - 2 })}>
              +{codes.length - 2}
            </span>
          )}
        </div>
      </Tooltip>);

  };

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

          {/* Filters */}
          <Card
            variant="default"
            padding="default"
            className="cashier-mb-4">

            <div className="cashier-filter-row">
              {/* Поиск */}
              {/* UX Audit #2.4: улучшенный placeholder + раскрывающаяся подсказка
                  с примерами синтаксиса (patient:ID). Раньше placeholder был обрезан
                  и не раскрывал скрытые возможности поиска. */}
              <div className="cashier-search-wrap">
                <Search className="cashier-search-icon" />
                <input
                  id="cashier-search-input"
                  aria-label={tI18n('cashier.search_aria')}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onFocus={() => setSearchFocused(true)}
                  onBlur={() => setSearchFocused(false)}
                  className="cashier-text-sm cashier-text-primary"
                  placeholder={tI18n('cashier.search_placeholder')}
                  title={tI18n('cashier.search_title')} />
                {searchFocused && !query && (
                  <div className="cashier-search-hint" role="status" aria-live="polite">
                    <span className="cashier-search-hint-label">{tI18n('cashier.search_hint_label')}</span>
                    <code className="cashier-search-hint-code">{tI18n('cashier.search_example_name')}</code>
                    <code className="cashier-search-hint-code">patient:123</code>
                    <code className="cashier-search-hint-code">+99890...</code>
                  </div>
                )}
              </div>

              {/* Статус — показывается только на табе истории платежей.
                  На табе «Ожидающие оплаты» статус заведомо = pending,
                  поэтому фильтр избыточен (закон Хика — убираем лишний выбор). */}
              {activeTab === 'history' && (
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  aria-label={tI18n('cashier.filter_status')}
                  className="cashier-text-sm cashier-text-primary">
                  <option value="all">{tI18n('cashier.all_statuses')}</option>
                  <option value="paid">{tI18n('cashier.status_paid')}</option>
                  <option value="partial">{tI18n('cashier.status_partial')}</option>
                  <option value="pending">{tI18n('cashier.status_pending')}</option>
                  <option value="cancelled">{tI18n('cashier.status_cancelled')}</option>
                  <option value="refunded">{tI18n('cashier.status_refunded')}</option>
                </select>
              )}

              {/* Переключатель режима даты */}
              <div className="cashier-date-mode">
                <Calendar className="cashier-date-icon" />
                <SegmentedControl
                  options={[
                  { label: tI18n('cashier.single_date'), value: 'single' },
                  { label: tI18n('cashier.date_mode_range'), value: 'range' }]
                  }
                  value={dateMode}
                  onChange={(v: unknown) => setDateMode(String(v))}
                  size="default" />

              </div>

              {/* Поля даты */}
              {dateMode === 'single' ?
              <>
                  <Input
                  type="date"
                  value={selectedDate}
                  onChange={(e) => setSelectedDate(e.target.value)}
                  className="cashier-min-w-160" />

                  {/* UX Audit #1.4: Quick date presets replace single "Сегодня" button.
                      Reduces 2-3 clicks (open date picker → navigate to yesterday) to 1 click. */}
                  <SegmentedControl
                    options={datePresets.map((p) => ({ label: p.label, value: p.id }))}
                    value="__none__"
                    onChange={(id: string | number) => {
                      const preset = datePresets.find((p) => p.id === id);
                      if (!preset) return;
                      setSelectedDate(preset.getRange().to);
                    }}
                    size="default"
                    aria-label={tI18n('cashier.date_preset_aria')}
                  />
                </> :

              <>
                  <Input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                  className="cashier-min-w-140" />

                  <span className="cashier-date-sep">—</span>
                  <Input
                  type="date"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                  className="cashier-min-w-140" />

                  <SegmentedControl
                    options={datePresets.map((p) => ({ label: p.label, value: p.id }))}
                    value="__none__"
                    onChange={(id: string | number) => {
                      const preset = datePresets.find((p) => p.id === id);
                      if (!preset) return;
                      const { from, to } = preset.getRange();
                      setDateFrom(from);
                      setDateTo(to);
                    }}
                    size="default"
                    aria-label={tI18n('cashier.date_range_preset_aria')}
                  />
                </>
              }
            </div>
          </Card>

          {/* ✅ УЛУЧШЕНИЕ: Статистика платежей из API */}
          {/* UX Audit #3.1 + #3.2: stats-card теперь содержит ТОЛЬКО метрики.
              Кнопки «Обновить/Экспорт/Аналитика» вынесены в отдельный toolbar над табами —
              Nielsen #8 (эстетический и минималистичный дизайн) + IA-разделение.
              Скрытые плитки (visibility:hidden) удалены — визуальный шум устранён. */}
          <Card variant="outlined" className="cashier-stats-card">
            <div className="cashier-stats-grid">
              {activeTab === 'history' ?
              <>
                  <div className="cashier-text-center">
                    <div className="cashier-stat-num cashier-stat-accent">
                      {format(stats.total_amount)}
                    </div>
                    <div className="cashier-stat-cap">
                      {tI18n('cashier.total_period')}
                    </div>
                  </div>
                  <div className="cashier-text-center">
                    <div className="cashier-stat-num cashier-stat-green">
                      {format(stats.cash_amount)}
                    </div>
                    <div className="cashier-stat-cap">
                      {tI18n('cashier.method_cash')}
                    </div>
                  </div>
                  <div className="cashier-text-center">
                    <div className="cashier-stat-num cashier-stat-blue">
                      {format(stats.card_amount)}
                    </div>
                    <div className="cashier-stat-cap">
                      {tI18n('cashier.method_card')}
                    </div>
                  </div>
                  <div className="cashier-text-center">
                    <div className="cashier-stat-num cashier-stat-purple">
                      {stats.paid_count}
                    </div>
                    <div className="cashier-stat-cap">
                      {tI18n('cashier.status_paid')}
                    </div>
                  </div>
                  {stats.cancelled_count > 0 &&
                <div className="cashier-text-center">
                      <div className="cashier-stat-num cashier-stat-danger">
                        {stats.cancelled_count}
                      </div>
                      <div className="cashier-stat-cap">
                        {tI18n('cashier.cancelled_count')}
                      </div>
                    </div>
                }
                </> :

              <>
              <div className="cashier-text-center">
                  <div className="cashier-stat-num-lg cashier-stat-orange">
                    {format(stats.pending_amount || 0)}
                  </div>
                  <div className="cashier-stat-cap-base">
                    {tI18n('cashier.pending_count_caption', { count: stats.pending_count })}
                  </div>
                </div>
              </>
              }
            </div>
          </Card>

          {/* UX Audit #3.1: отдельный toolbar для действий над списком. */}
          <div className="cashier-toolbar">
            <div className="cashier-toolbar-actions">
              <Button
                size="small"
                variant="outline"
                onClick={handleRefresh}
                title={tI18n('cashier.refresh_title')}>

                {tI18n('cashier.refresh_btn')}
              </Button>
              <Button
                size="small"
                variant="outline"
                onClick={exportToCSV}
                title={tI18n('cashier.export_title')}>

                {tI18n('cashier.export_btn')}
              </Button>
              <Button
                size="small"
                variant="outline"
                onClick={loadHourlyStats}
                title={tI18n('cashier.hourly_stats_title')}>

                {tI18n('cashier.analytics_btn')}
              </Button>
            </div>
          </div>

          {/* Объединенная секция с вкладками */}
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


            {activeTab === 'pending' &&
            <div className="cashier-section-gap">
                {pendingLoading ?
              (/* UX Audit #4.4: skeleton rows внутри tbody сохраняют заголовки таблицы. */
              <div className="cashier-table-scroll">
                <table className="cashier-table">
                  <thead>
                    <tr className="cashier-table-row">
                      <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_date_time')}</th>
                      <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_patient')}</th>
                      <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_services')}</th>
                      <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_amount')}</th>
                      <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_status')}</th>
                      <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.from({ length: 5 }).map((_, i) => (
                      <tr key={`skeleton-pending-${i}`} className="cashier-table-row">
                        {Array.from({ length: 6 }).map((_, j) => (
                          <td key={j} className="cashier-cell-padded"><Skeleton height={20} /></td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              ) :
              appointments.length > 0 ?
              <div className="cashier-table-scroll">
                    <table className="cashier-table">
                      <thead>
                        <tr className="cashier-table-row">
                          <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_date_time')}</th>
                          <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_patient')}</th>
                          <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_services')}</th>
                          <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_amount')}</th>
                          <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_status')}</th>
                          <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_actions')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {appointments.map((appointment, index) =>
                    <tr
                      key={`${appointment.record_type || 'appointment'}-${appointment.id || index}-${Array.isArray(appointment.visit_ids) ? (appointment.visit_ids as unknown[]).join('-') : ''}`}
                      className="cashier-table-row">

                            <td
                              aria-label={tI18n('cashier.appointment_date_aria')}
                              className="cashier-text-sm cashier-text-primary">
                              <div className="cashier-date-stack">
                                <span className="cashier-date-main">
                                  {appointment.created_at ?
                            formatRegistrarDate(appointment.created_at) :
                            appointment.appointment_date || '—'
                            }
                                </span>
                                <span className="cashier-date-sub">
                                  {appointment.created_at ?
                            formatRegistrarTime(appointment.created_at) :
                            appointment.appointment_time || '—'
                            }
                                </span>
                              </div>
                            </td>
                            <td className="cashier-text-sm cashier-text-primary">
                              {appointment.patient_last_name && appointment.patient_first_name ?
                        `${appointment.patient_last_name} ${appointment.patient_first_name}` :
                        appointment.patient_name || tI18n('cashier.patient_with_id', { id: appointment.patient_id })
                        }
                              {/* UX Audit #2.6: badge «Групповой» для grouped-платежей,
                                  чтобы было видно, почему кнопка «Онлайн» дизейблится. */}
                              {isBackendGroupedCashierPayment(appointment) && (
                                <span className="cashier-badge cashier-badge-grouped" title={tI18n('cashier.grouped_payment_title')}>
                                  {tI18n('cashier.grouped_badge')}
                                </span>
                              )}
                            </td>
                            <td className="cashier-text-sm cashier-text-primary">
                              {renderServiceBadges(appointment.services, appointment.services_names)}
                            </td>
                            <td className="cashier-text-sm cashier-text-accent">
                              {format(Number(appointment.total_amount || appointment.remaining_amount || appointment.payment_amount || 0))}
                            </td>
                            <td className="cashier-cell-padded">
                              <Badge
                                variant="warning"
                                role="status"
                                aria-label={tI18n('cashier.status_pending_aria')}>
                                {tI18n('cashier.pending_payment_badge')}
                              </Badge>
                            </td>
                            <td className="cashier-cell-padded">
                              <div className="cashier-refresh-row">
                                <Button
                            size="small"
                            variant="outline"
                            onClick={() => openPaymentWidget(appointment)}
                            disabled={!canCreateDirectCashierPayment(appointment) || isBackendGroupedCashierPayment(appointment)}
                            aria-label={tI18n('cashier.start_online_payment_aria')}
                            title={!canCreateDirectCashierPayment(appointment) || isBackendGroupedCashierPayment(appointment)
                              ? tI18n('cashier.online_payment_disabled_title')
                              : tI18n('cashier.online_payment_enabled_title')}>

                                  {tI18n('cashier.online_btn')}
                                </Button>
                                <Button
                            size="small"
                            onClick={() => {
                              paymentModal.openModal(appointment as unknown as null);
                            }}
                            disabled={!canCreateCashierPayment(appointment)}
                            aria-label={tI18n('cashier.cash_payment_aria')}
                            title={!canCreateCashierPayment(appointment) ? tI18n('cashier.cash_payment_disabled_title') : tI18n('cashier.cash_payment_aria')}>

                                  {tI18n('cashier.cash_btn')}
                                </Button>
                              </div>
                            </td>
                          </tr>
                    )}
                      </tbody>
                    </table>

                    {/* ✅ v2.0: Пагинация для ожидающих оплаты */}
                    {pendingTotalPages > 1 &&
                <div className="cashier-pagination">
                        <Button
                    size="small"
                    variant="outline"
                    disabled={pendingPage === 1 || pendingLoading}
                    onClick={() => setPendingPage((p) => Math.max(1, p - 1))}>

                          {tI18n('cashier.prev_page')}
                        </Button>
                        <span className="cashier-pagination-info">
                          {tI18n('cashier.pagination_info', { current: pendingPage, total: pendingTotalPages, total_items: pendingTotalItems })}
                        </span>
                        <Button
                    size="small"
                    variant="outline"
                    disabled={pendingPage === pendingTotalPages || pendingLoading}
                    onClick={() => setPendingPage((p) => Math.min(pendingTotalPages, p + 1))}>

                          {tI18n('cashier.next_page')}
                        </Button>
                      </div>
                }
                  </div> :

              (/* UX Audit #4.3: actionable empty state вместо голого текста. */
              <div className="cashier-empty-state" role="status">
                <CheckCircle size={32} className="cashier-empty-state-icon" aria-hidden="true" />
                <div className="cashier-empty-state-title">{tI18n('cashier.empty_pending_title')}</div>
                <div className="cashier-empty-state-text">
                  {tI18n('cashier.empty_pending_text')}
                </div>
                <Button size="small" variant="outline" onClick={() => setActiveTab('history')}>
                  {tI18n('cashier.open_history_btn')}
                </Button>
              </div>
              )}
              </div>
            }

            {activeTab === 'history' &&
            <div className="cashier-section-gap">
                {historyLoading ?
              (/* UX Audit #4.4: skeleton rows для history-tab — сохраняют заголовки таблицы. */
              <div className="cashier-table-scroll">
                <table className="cashier-table">
                  <thead>
                    <tr className="cashier-table-row">
                      <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_date_time')}</th>
                      <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_patient')}</th>
                      <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_service')}</th>
                      <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_method_short')}</th>
                      <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_amount')}</th>
                      <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_status')}</th>
                      <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Array.from({ length: 5 }).map((_, i) => (
                      <tr key={`skeleton-history-${i}`} className="cashier-table-row">
                        {Array.from({ length: 7 }).map((_, j) => (
                          <td key={j} className="cashier-cell-padded"><Skeleton height={20} /></td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              ) :

              <div className="cashier-table-scroll">
                    <table className="cashier-table">
                      <thead>
                        <tr className="cashier-table-row">
                          {/* UX Audit #4.2: кликабельные заголовки с сортировкой. */}
                          <th className="cashier-text-sm cashier-text-primary cashier-th-sortable" onClick={() => toggleSort('date')}>
                            {tI18n('cashier.col_date_time')} {sortField === 'date' && (sortDir === 'asc' ? '↑' : '↓')}
                          </th>
                          <th className="cashier-text-sm cashier-text-primary cashier-th-sortable" onClick={() => toggleSort('patient')}>
                            {tI18n('cashier.col_patient')} {sortField === 'patient' && (sortDir === 'asc' ? '↑' : '↓')}
                          </th>
                          <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_service')}</th>
                          <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_method_short')}</th>
                          <th className="cashier-text-sm cashier-text-primary cashier-th-sortable" onClick={() => toggleSort('amount')}>
                            {tI18n('cashier.col_amount')} {sortField === 'amount' && (sortDir === 'asc' ? '↑' : '↓')}
                          </th>
                          <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_status')}</th>
                          <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_actions')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredPayments.length > 0 ?
                    filteredPayments.map((row, index) =>
                    <tr key={`payment-${row.id || row.payment_id || index}`} className="cashier-table-row">

                              <td
                                aria-label={tI18n('cashier.payment_history_date_aria')}
                                className="cashier-text-sm cashier-text-primary">
                                <div className="cashier-date-stack">
                                  <span className="cashier-date-main">{row.date || '—'}</span>
                                  <span className="cashier-date-sub">{row.time || '—'}</span>
                                </div>
                              </td>
                              <td className="cashier-text-sm cashier-text-primary">
                                {String(row.patient ?? '')}
                              </td>
                              <td className="cashier-text-sm cashier-text-primary">
                                {/* PR-43 / Medium-24: services info rendered from row.service
                                    (single service name). Multi-service breakdown requires
                                    backend changes to the history endpoint payload. */}
                                 {String(row.service ?? '—')}
                              </td>
                              <td className="cashier-text-sm cashier-text-primary">
                                {String(row.method ?? '')}
                              </td>
                              <td className="cashier-text-sm cashier-text-primary">
                                {format(row.total_amount || row.amount || 0)}
                              </td>
                              <td className="cashier-cell-padded">
                                <Badge
                                  variant={getPaymentStatusMeta(row.status, tI18n).variant}
                                  role="status"
                                  aria-label={getPaymentStatusMeta(row.status, tI18n).ariaLabel}>
                                  {getPaymentStatusLabel(row.status, tI18n)}
                                </Badge>
                              </td>
                              <td className="cashier-cell-actions">
                                {/* UX Audit #2.2: primary action + overflow menu.
                                    Раньше: 4 равноправные кнопки (success/danger/warning/ghost) —
                                    слабая визуальная иерархия (Nielsen #4),
                                    на узких экранах ломалось flex-wrap.
                                    Теперь: primary «Принять» видна всегда, остальные 3 —
                                    в overflow menu через нативный <details>. */}
                                <Button
                                  size="small"
                                  variant="primary"
                                  onClick={() => confirmPayment(row.id)}
                                  disabled={!hasBackendPaymentAction(row, 'confirm') || processingAction?.id === row.id}
                                  aria-label={tI18n('cashier.confirm_payment_aria')}>
                                  {processingAction?.id === row.id && processingAction?.type === 'confirm' ?
                                    <Loader2 size={14} className="animate-spin" aria-hidden="true" /> :
                                    <CheckCircle size={14} />}
                                  {tI18n('cashier.confirm_payment_confirm')}
                                </Button>
                                <details className="cashier-overflow-menu">
                                  <summary className="cashier-overflow-trigger" aria-label={tI18n('cashier.more_actions_aria')}>
                                    <MoreVertical size={16} aria-hidden="true" />
                                  </summary>
                                  <div className="cashier-overflow-popover" role="menu">
                                    <button
                                      type="button"
                                      className="cashier-overflow-item cashier-overflow-item--danger"
                                      onClick={() => openCancelDialog(row)}
                                      disabled={!hasBackendPaymentAction(row, 'cancel') || processingAction?.id === row.id}
                                      role="menuitem"
                                      aria-label={tI18n('cashier.btn_cancel')}>
                                      <XCircle size={14} aria-hidden="true" /> {tI18n('cashier.btn_cancel')}
                                    </button>
                                    <button
                                      type="button"
                                      className="cashier-overflow-item cashier-overflow-item--warning"
                                      onClick={() => openRefundDialog(row)}
                                      disabled={!hasBackendPaymentAction(row, 'refund') || processingAction?.id === row.id}
                                      role="menuitem"
                                      aria-label={tI18n('cashier.refund_aria')}>
                                      <Undo2 size={14} aria-hidden="true" /> {tI18n('cashier.refund_confirm')}
                                    </button>
                                    <button
                                      type="button"
                                      className="cashier-overflow-item"
                                      onClick={() => handlePrintReceipt(row)}
                                      disabled={!hasBackendPaymentAction(row, 'print_receipt') || processingAction?.id === row.id}
                                      role="menuitem"
                                      aria-label={tI18n('cashier.print_receipt_aria')}>
                                      <Receipt size={14} aria-hidden="true" /> {tI18n('cashier.print_receipt_btn')}
                                    </button>
                                  </div>
                                </details>
                              </td>
                            </tr>
                    ) :

                    <tr className="cashier-empty-row">
                            <td colSpan={7} className="cashier-empty-cell">
                              {/* UX Audit #4.3: actionable empty state для истории. */}
                              <div className="cashier-empty-state cashier-empty-state--inline" role="status">
                                <div className="cashier-empty-state-title">{tI18n('cashier.empty_history_title')}</div>
                                <div className="cashier-empty-state-text">
                                  {tI18n('cashier.empty_history_text')}
                                </div>
                              </div>
                            </td>
                          </tr>
                    }
                      </tbody>
                    </table>

                    {/* ✅ УЛУЧШЕНИЕ: Пагинация c Server-Side логикой */}
                    {totalPages > 1 &&
                <div className="cashier-pagination">
                        <Button
                    size="small"
                    variant="outline"
                    disabled={currentPage === 1 || historyLoading}
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}>

                          {tI18n('cashier.prev_page')}
                        </Button>
                        <span className="cashier-pagination-info">
                          {tI18n('cashier.pagination_info', { current: currentPage, total: totalPages, total_items: totalItems })}
                        </span>
                        <Button
                    size="small"
                    variant="outline"
                    disabled={currentPage === totalPages || historyLoading}
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}>

                          {tI18n('cashier.next_page')}
                        </Button>
                      </div>
                }
                  </div>
              }
              </div>
            }

            {/* Вкладка Возвраты */}
            {activeTab === 'refunds' &&
            <div className="cashier-section-gap">
                <RefundRequestsTable onRefresh={handleRefresh} />
              </div>
            }

          </Card>

          {/* ✅ УЛУЧШЕНИЕ: Диалог подтверждения отмены платежа */}
          {/* UX Audit #2.1: показываем контекст платежа + обязательная причина (min 10 chars). */}
          <Dialog
            open={cancelDialogOpen}
            onClose={closeCancelDialog}
            maxWidth="sm"
            fullWidth>

            <DialogTitle>{tI18n('cashier.cancel_dialog_title')}</DialogTitle>
            <DialogContent>
              {cancelPaymentContext && (
                <div className="cashier-cancel-context" role="group" aria-label={tI18n('cashier.cancel_context_aria')}>
                  <Typography variant="body2" color="textSecondary">
                    {tI18n('cashier.payment_id_label', { id: cancelPaymentContext.id })}
                  </Typography>
                  {Boolean(cancelPaymentContext.patient) && (
                    <Typography variant="body1">
                      {tI18n('cashier.patient_label')} <strong>{String(cancelPaymentContext.patient)}</strong>
                    </Typography>
                  )}
                  {Number(cancelPaymentContext.amount ?? 0) > 0 && (
                    <Typography variant="body1">
                      {tI18n('cashier.amount_label')} <strong>{format(Number(cancelPaymentContext.amount ?? 0))}</strong>
                    </Typography>
                  )}
                </div>
              )}
              <Typography variant="body2" className="cashier-mb-4">
                {tI18n('cashier.cancel_dialog_text')}
              </Typography>
              <textarea
                aria-label={tI18n('cashier.cancel_reason_aria')}
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                placeholder={tI18n('cashier.cancel_reason_placeholder')}
                required
                minLength={10}
                className="cashier-text-sm cashier-text-primary cashier-refund-textarea" />
              <Typography variant="caption" color="textSecondary">
                {tI18n('cashier.char_count', { count: cancelReason.trim().length })}
              </Typography>
            </DialogContent>
            <DialogActions>
              <Button variant="outline" onClick={closeCancelDialog}>
                {tI18n('cashier.close_btn')}
              </Button>
              <Button
                variant="danger"
                onClick={handleCancelPayment}
                disabled={processingAction?.type === 'cancel' || cancelReason.trim().length < 10}>
                {processingAction?.type === 'cancel' ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : null}
                {tI18n('cashier.btn_cancel')}
              </Button>
            </DialogActions>
          </Dialog>

          {/* ✅ УЛУЧШЕНИЕ: Модальное окно оплаты с универсальным хуком */}
          {paymentModal.isOpen && paymentModal.selectedItem &&
          <CashPaymentModal
            appointment={paymentModal.selectedItem}
            onProcessPayment={processPayment}
            onClose={paymentModal.closeModal} />

          }

          {/* ✅ УЛУЧШЕНИЕ: Диалог онлайн-оплаты с универсальным хуком */}
          <Dialog
            open={paymentWidget.isOpen}
            onClose={handlePaymentCancel}
            maxWidth="md"
            fullWidth>

            <DialogTitle>
              <Typography variant="h6">
                {tI18n('cashier.online_payment_dialog_title')}
              </Typography>
              {paymentWidget.selectedItem &&
              <Typography variant="body2" color="textSecondary">
                  {tI18n('cashier.patient_summary', { name: (paymentWidget.selectedItem as unknown as Appointment).patient_name, department: (paymentWidget.selectedItem as unknown as Appointment).department })}
                </Typography>
              }
            </DialogTitle>

            <DialogContent>
              {paymentError &&
              <Alert severity="error" className="cashier-alert-error">
                  {paymentError}
                </Alert>
              }

              {paymentWidget.selectedItem &&
              <PaymentWidget
                visitId={canCreateDirectCashierPayment(paymentWidget.selectedItem as unknown as Appointment) ? resolveSingleCashierVisitId(paymentWidget.selectedItem as unknown as Appointment) : null}
                amount={Number((paymentWidget.selectedItem as unknown as Appointment).remaining_amount || (paymentWidget.selectedItem as unknown as Appointment).total_amount || (paymentWidget.selectedItem as unknown as Appointment).cost || 0)}
                currency="UZS"
                description={tI18n('cashier.payment_description', { department: (paymentWidget.selectedItem as unknown as Appointment).department || tI18n('cashier.payment_note_default') })}
                onSuccess={handlePaymentSuccess}
                onError={handlePaymentError}
                onCancel={handlePaymentCancel} />

              }
            </DialogContent>

            <DialogActions>
              <Button onClick={handlePaymentCancel}>
                {tI18n('cashier.close_btn')}
              </Button>
            </DialogActions>
          </Dialog>

          {/* Диалог успешной оплаты */}
          <Dialog
            open={!!paymentSuccess}
            onClose={() => setPaymentSuccess(null)}
            maxWidth="sm"
            fullWidth>

            <DialogTitle>
              <Box display="flex" alignItems="center">
                <CheckCircle className="cashier-check-icon" />
                {tI18n('cashier.payment_success_dialog_title')}
              </Box>
            </DialogTitle>

            <DialogContent>
              {paymentSuccess &&
              <Box>
                  <Typography variant="body1" gutterBottom>
                    {tI18n('cashier.payment_success_dialog_body')}
                  </Typography>
                  {paymentSuccess.amount !== undefined &&
                  <Typography variant="body2" color="textSecondary">
                    {tI18n('cashier.amount_label')} {format(Number(paymentSuccess.amount) || 0)}
                  </Typography>
                  }
                  {Number(paymentSuccess.change_due ?? 0) > 0 &&
                  <Typography variant="body2" color="textSecondary">
                    {tI18n('cashier.change_label')} {format(Number(paymentSuccess.change_due))}
                  </Typography>
                  }
                  <Typography variant="body2" color="textSecondary">
                    {tI18n('cashier.payment_id_field', { id: paymentSuccess.payment_id })}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    {tI18n('cashier.provider_label', { provider: paymentSuccess.provider })}
                  </Typography>
                </Box>
              }
            </DialogContent>

            <DialogActions>
              <Button onClick={() => setPaymentSuccess(null)} variant="primary">
                OK
              </Button>
            </DialogActions>
          </Dialog>

          {/* ✅ v2.0: Диалог возврата */}
          <Dialog open={refundDialogOpen} onClose={closeRefundDialog}>
            <DialogTitle>
              <Box display="flex" alignItems="center">
                {tI18n('cashier.refund_title')}
              </Box>
            </DialogTitle>
            <DialogContent>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Typography variant="body2" color="textSecondary">
                  {tI18n('cashier.refund_dialog_subtitle', { amount: formatUZS(refundPaymentAmount) })}
                </Typography>
                <Box>
                  <Typography variant="body2" gutterBottom>{tI18n('cashier.refund_amount_label')}:</Typography>
                  <input
                    type="number"
                    aria-label={tI18n('cashier.refund_amount_label')}
                    value={refundAmount}
                    onChange={(e) => setRefundAmount(e.target.value)}
                    className="cashier-refund-input"
                    max={refundPaymentAmount}
                    min={1} />

                </Box>
                <Box>
                  <Typography variant="body2" gutterBottom>{tI18n('cashier.refund_reason_label')}:</Typography>
                  <textarea
                    aria-label={tI18n('cashier.refund_reason_label')}
                    value={refundReason}
                    onChange={(e) => setRefundReason(e.target.value)}
                    placeholder={tI18n('cashier.refund_reason_placeholder')}
                    rows={3}
                    className="cashier-refund-textarea" />

                </Box>
              </Box>
            </DialogContent>
            <DialogActions>
              <Button variant="outline" onClick={closeRefundDialog}>
                {tI18n('cashier.cancel')}
              </Button>
              <Button variant="danger" onClick={handleRefund} disabled={processingAction?.type === 'refund'}>
                {processingAction?.type === 'refund' ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : null}
                {tI18n('cashier.refund_execute_btn')}
              </Button>
            </DialogActions>
          </Dialog>

          {/* ✅ v2.0: Диалог почасовой статистики */}
          {/* UX Audit #4.6: Recharts вместо inline-баров на Box sx={{...}}.
              Раньше: примитивный bar chart без осей, без интерактива, без tooltip.
              Теперь: полноценный BarChart с XAxis/YAxis/Tooltip/CartesianGrid. */}
          <Dialog open={showHourlyChart} onClose={closeHourlyChart}>
            <DialogTitle>
              {tI18n('cashier.hourly_stats_dialog_title', { date: selectedDate })}
            </DialogTitle>
            <DialogContent>
              {hourlyStats.filter((h) => Number((h as { count?: number }).count ?? 0) > 0).length > 0 ? (
                <div className="cashier-hourly-chart">
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={hourlyStats.filter((h) => Number((h as { count?: number }).count ?? 0) > 0)}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--mac-border, #d8dde8)" />
                      <XAxis
                        dataKey="hour"
                        tickFormatter={(h) => `${h}:00`}
                        stroke="var(--mac-text-secondary, #6b7280)"
                        fontSize={12}
                      />
                      <YAxis
                        stroke="var(--mac-text-secondary, #6b7280)"
                        fontSize={12}
                        allowDecimals={false}
                      />
                      <RechartsTooltip
                        contentStyle={{
                          background: 'var(--mac-bg-tertiary)',
                          border: '1px solid var(--mac-border, #d8dde8)',
                          borderRadius: '8px',
                          fontSize: '13px',
                        }}
                        labelFormatter={(h) => `${h}:00`}
                        formatter={(value, name) => {
                          if (name === 'count') return [value, tI18n('cashier.hourly_stats_count_label')];
                          if (name === 'amount') return [formatUZS(typeof value === 'number' || typeof value === 'string' ? value : 0), tI18n('cashier.hourly_stats_amount_label')];
                          return [value, name];
                        }}
                      />
                      <Bar dataKey="count" fill="var(--mac-success, #34c759)" radius={[4, 4, 0, 0]} name="count" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <Typography color="textSecondary">{tI18n('cashier.hourly_stats_empty')}</Typography>
              )}
            </DialogContent>
            <DialogActions>
              <Button onClick={closeHourlyChart}>{tI18n('cashier.close_btn')}</Button>
            </DialogActions>
          </Dialog>
        </div>
      </div>
      {/* Session timeout warning dialog (UX Audit #2.5: явные последствия + таймер). */}
      {sessionWarning && (
        <div
          role="alertdialog"
          aria-label={tI18n('cashier.session_warning_aria')}
          className="cashier-session-warning-overlay">
          <div className="cashier-session-warning-card">
            <h3 className="cashier-session-warning-title">
              {tI18n('cashier.session_warning_title')}
            </h3>
            <p className="cashier-session-warning-text">
              {tI18n('cashier.session_warning_text', { seconds: sessionSecondsLeft ?? '?' })}
            </p>
            <div className="cashier-session-warning-actions">
              <button
                type="button"
                onClick={dismissSessionWarning}
                className="cashier-session-warning-btn cashier-session-warning-btn--secondary">
                {tI18n('cashier.session_warning_dismiss')}
              </button>
              <button
                type="button"
                onClick={() => { dismissSessionWarning(); notify.info(tI18n('cashier.session_extending')); }}
                className="cashier-session-warning-btn cashier-session-warning-btn--primary">
                {tI18n('cashier.session_warning_extend')}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}
    </div>);

};

export default CashierPanel;
