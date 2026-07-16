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
import useModal from '../hooks/useModal.jsx';
import { usePayments } from '../hooks/usePayments';
import { useDebouncedValue } from '../hooks/useDebouncedCallback';
import { useHotkeys } from '../hooks/useHotkeys';
import { useSessionTimeoutWarning } from '../hooks/useSessionTimeoutWarning';
import { getApiOrigin } from '../api/runtime';
import { api } from '../api/client';  // PR-53: replace raw fetch with axios
import { printPanelReceiptInBrowser } from '../services/panelPrint';
import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';
import { getErrorMessage } from '../utils/errorHandler';
import { formatRegistrarDate, formatRegistrarTime, parseRegistrarTimestamp } from '../utils/dateUtils';
import notify from '../services/notify';
// STRAT#31: useTranslation adapter for confirm/notify i18n.
import { useTranslation } from '../i18n/useTranslation';
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

// Функция для получения даты в формате YYYY-MM-DD
const getLocalDateString = (date = new Date()) => {
  const d = new Date(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

// UX Audit #1.4: Quick date presets for typical financial reporting ranges.
// Replaces single "Сегодня" button with a 4-option segmented control.
// Saves cashier clicks when reconciling shifts (typical: «Вчера» / «Неделя»).
const shiftDay = (days) => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return getLocalDateString(d);
};

// STRAT#31 i18n: DATE_PRESETS uses stable `id` for option value matching.
// The user-visible label is computed inside the component via tI18n('cashier.range_<id>').
const DATE_PRESETS = [
  { id: 'today',   getRange: () => ({ from: getLocalDateString(), to: getLocalDateString() }) },
  { id: 'yesterday', getRange: () => ({ from: shiftDay(-1), to: shiftDay(-1) }) },
  { id: 'week',    getRange: () => ({ from: shiftDay(-6), to: getLocalDateString() }) },
  { id: 'month',   getRange: () => ({ from: shiftDay(-29), to: getLocalDateString() }) },
];

// Вспомогательная функция для создания прозрачного цвета была удалена (MEDIUM #14 dead code cleanup)
// STRAT#31 i18n: PAYMENT_METHOD_LABELS converted to a factory that takes `t` (the unified
// useTranslation t function) so that cash/card labels are reactive to language changes.
const buildPaymentMethodLabels = (t) => ({
  cash: t('cashier.method_cash'),
  card: t('cashier.method_card'),
  payme: 'PayMe',
  click: 'Click',
});

const resolvePaymentId = (paymentRowOrId) => {
  if (typeof paymentRowOrId === 'number' || typeof paymentRowOrId === 'string') {
    return paymentRowOrId;
  }

  return (
    paymentRowOrId?.id ||
    paymentRowOrId?.payment_id ||
    paymentRowOrId?.grouped_payments?.[0] ||
    null
  );
};

const resolvePaymentMethodCode = (method) => {
  const normalizedMethod = String(method || '').trim().toLowerCase();

  if (!normalizedMethod) return 'cash';
  if (normalizedMethod === 'наличные') return 'cash';
  if (normalizedMethod === 'карта') return 'card';

  return normalizedMethod;
};

const resolvePaymentMethodLabel = (method, labels) => {
  const methodCode = resolvePaymentMethodCode(method);
  return labels[methodCode] || String(method || labels.cash);
};

const extractReceiptDateTime = (paymentRow) => {
  const sourceTimestamp = paymentRow?.paid_at || paymentRow?.created_at || null;
  const parsedDate = sourceTimestamp ? parseRegistrarTimestamp(sourceTimestamp) : null;
  const hasValidDate = parsedDate && !Number.isNaN(parsedDate.getTime());

  return {
    date: paymentRow?.date || (hasValidDate ? formatRegistrarDate(parsedDate) : ''),
    time: paymentRow?.time || (
      hasValidDate
        ? formatRegistrarTime(parsedDate)
        : ''
    )
  };
};

const buildReceiptServices = (paymentRow, totalAmount) => {
  const currency = String(paymentRow?.currency || 'UZS');
  const namedServices = Array.isArray(paymentRow?.services_names) ? paymentRow.services_names : [];

  if (namedServices.length > 0) {
    return namedServices
      .filter(Boolean)
      .map((serviceName) => ({
      name: serviceName,
      quantity: 1,
      price: totalAmount,
      total: totalAmount,
      currency
      }));
  }

  if (Array.isArray(paymentRow?.services) && paymentRow.services.length > 0) {
    return paymentRow.services.flatMap((serviceItem) => {
      if (typeof serviceItem === 'object' && serviceItem !== null) {
        const displayName = serviceItem.name || serviceItem.code || null;
        if (!displayName) {
          return [];
        }
        const quantity = Number(serviceItem.quantity || 1);
        const price = Number(serviceItem.price || totalAmount);
        return {
          name: displayName,
          quantity,
          price,
          total: Number(serviceItem.total || price * quantity),
          currency: serviceItem.currency || currency
        };
      }

      if (!serviceItem) {
        return [];
      }

      return {
        name: String(serviceItem),
        quantity: 1,
        price: totalAmount,
        total: totalAmount,
        currency
      };
    });
  }

  return [];
};

const buildReceiptPrintPayload = (paymentRow, labels, defaultPatientLabel) => {
  const paymentId = resolvePaymentId(paymentRow);
  const totalAmount = Number(paymentRow?.total_amount || paymentRow?.amount || 0);
  const services = buildReceiptServices(paymentRow, totalAmount);
  const { date, time } = extractReceiptDateTime(paymentRow);
  const methodCode = resolvePaymentMethodCode(paymentRow?.method);
  // HIGH #9 fix: use real change_due if provided by CashPaymentModal, otherwise 0.
  const changeDue = Number(paymentRow?.change_due || paymentRow?.change || 0);
  const receivedAmount = Number(paymentRow?.received_amount || totalAmount);

  return {
    payment: {
      number: paymentRow?.receipt_no || `PAY-${paymentId}`,
      date,
      time,
      services,
      subtotal: totalAmount,
      discount: 0,
      total: totalAmount,
      method: methodCode,
      method_name: resolvePaymentMethodLabel(paymentRow?.method, labels),
      status: paymentRow?.status ?? null,
      paid_amount: receivedAmount,
      change: changeDue
    },
    patient: {
      full_name: paymentRow?.patient || paymentRow?.patient_name || defaultPatientLabel,
      phone: paymentRow?.patient_phone || null
    },
    services,
    clinic: null
  };
};

const getPaymentStatusMeta = (status, t) => {
  const normalizedStatus = String(status || '').trim().toLowerCase();
  const statusMap = {
    paid: { variant: 'success', ariaLabel: t('cashier.status_paid_aria') },
    partial: { variant: 'info', ariaLabel: t('cashier.status_partial_aria') },
    cancelled: { variant: 'danger', ariaLabel: t('cashier.status_cancelled_aria') },
    refunded: { variant: 'danger', ariaLabel: t('cashier.status_refunded_aria') },
    pending: { variant: 'warning', ariaLabel: t('cashier.status_pending_aria') },
    unknown: { variant: 'secondary', ariaLabel: t('cashier.status_unknown_aria') },
  };

  return statusMap[normalizedStatus] || statusMap.unknown;
};

const getPaymentStatusLabel = (status, t) => {
  const normalizedStatus = String(status || '').trim().toLowerCase();
  const statusMap = {
    paid: t('cashier.status_paid'),
    partial: t('cashier.status_partial'),
    cancelled: t('cashier.status_cancelled'),
    refunded: t('cashier.status_refunded'),
    pending: t('cashier.status_pending'),
    unknown: t('cashier.status_unknown'),
  };

  return statusMap[normalizedStatus] || statusMap.unknown;
};

// P-018 fix: getPaymentActionContext / getAppointmentPaymentActionContext helpers
// were removed — they leaked patient names (PHI) into aria-labels, and after
// localization all action buttons now use static Russian aria-labels instead.

const resolveCashierVisitIds = (appointment) => {
  const paymentVisitIds = Array.isArray(appointment?.payment_visit_ids)
    ? appointment.payment_visit_ids.filter((visitId) => visitId !== null && visitId !== undefined)
    : [];

  if (paymentVisitIds.length > 0) {
    return [...new Set(paymentVisitIds)];
  }

  if (appointment?.payment_visit_id !== null && appointment?.payment_visit_id !== undefined) {
    return [appointment.payment_visit_id];
  }

  const groupedVisitIds = Array.isArray(appointment?.visit_ids)
    ? appointment.visit_ids.filter((visitId) => visitId !== null && visitId !== undefined)
    : [];

  if (groupedVisitIds.length > 0) {
    return [...new Set(groupedVisitIds)];
  }

  return appointment?.visit_id !== null && appointment?.visit_id !== undefined
    ? [appointment.visit_id]
    : [];
};

const resolveSingleCashierVisitId = (appointment) => {
  const visitIds = resolveCashierVisitIds(appointment);
  return visitIds.length === 1 ? visitIds[0] : null;
};

const isBackendGroupedCashierPayment = (appointment) =>
  appointment?.payment_contract === 'grouped_visits' ||
  appointment?.can_create_grouped_payment === true;

const canCreateDirectCashierPayment = (appointment) => {
  return appointment?.can_create_direct_payment === true;
};

const canCreateCashierPayment = (appointment) =>
  canCreateDirectCashierPayment(appointment) || appointment?.can_create_grouped_payment === true;

const createGroupedCashierPayment = async (appointment, paymentData) => {
  // PR-53: migrated from raw fetch() to axios client
  const token = tokenManager.getAccessToken();
  if (!token) {
    throw new Error('Missing access token for grouped cashier payment.');
  }

  const visitIds = resolveCashierVisitIds(appointment);
  if (visitIds.length === 0 || appointment?.can_create_grouped_payment !== true) {
    throw new Error('Backend did not provide a grouped cashier payment contract for this row.');
  }

  const response = await api.post('/cashier/payments/grouped', {
    patient_id: appointment?.patient_id ?? null,
    visit_ids: visitIds,
    amount: paymentData.amount,
    method: paymentData.method,
    note: paymentData.note || 'Grouped cashier payment'
  });

  return response.data;
};

const PAYMENT_ACTION_CAN_FIELD = {
  cancel: 'can_cancel',
  refund: 'can_refund',
  print_receipt: 'can_print_receipt',
  confirm: 'can_confirm'
};

const hasBackendPaymentAction = (paymentRow, action) => {
  const normalizedAction = String(action || '').trim().toLowerCase();
  if (!normalizedAction) {
    return false;
  }

  if (Array.isArray(paymentRow?.available_actions)) {
    return paymentRow.available_actions.some(
      (availableAction) => String(availableAction || '').trim().toLowerCase() === normalizedAction
    );
  }

  const canField = PAYMENT_ACTION_CAN_FIELD[normalizedAction];
  if (canField && Object.prototype.hasOwnProperty.call(paymentRow || {}, canField)) {
    return Boolean(paymentRow[canField]);
  }

  return false;
};

const CashierPanel = () => {
  // P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
  // The hook returns [confirm, dialogNode]; dialogNode must be rendered once
  // in the component tree (we render it at the end of the JSX below).
  const [confirm, confirmDialog] = useConfirm();
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
    return params.get('patientId') ? parseInt(params.get('patientId'), 10) : null;
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
          const token = tokenManager.getAccessToken();
          if (!token) return;

          const response = await api.get(`/patients/${patientIdFromUrl}`);
          const patientData = response.data;
          const patientName = `${patientData.last_name || ''} ${patientData.first_name || ''}`.trim();
          setQuery(patientName);
          logger.info('[Cashier] Patient loaded from URL', { patientId: patientData?.id });
        } catch (error) {
          logger.error('[Cashier] Не удалось загрузить пациента:', error);
        }
      };
      loadPatientForSearch();
    }
  }, [location.search, getPatientIdFromUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  const [status, setStatus] = useState('all');
  const [payments, setPayments] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [paymentSuccess, setPaymentSuccess] = useState(null);
  const [paymentError, setPaymentError] = useState(null);

  // Состояния для календаря
  const [dateMode, setDateMode] = useState('single'); // 'single' | 'range'
  const [selectedDate, setSelectedDate] = useState(() => getLocalDateString());
  const [dateFrom, setDateFrom] = useState(() => getLocalDateString());
  const [dateTo, setDateTo] = useState(() => getLocalDateString());

  // Состояние для вкладок
  const [activeTab, setActiveTab] = useState('pending'); // 'pending' | 'history'

  // ✅ УЛУЧШЕНИЕ: Новые состояния для отмены платежа
  // UX Audit #2.1: контекст отменяемого платежа (id + patient + amount) —
  // показывается в диалоге, чтобы кассир видел, ЧТО именно он отменяет.
  const [cancelPaymentContext, setCancelPaymentContext] = useState(null);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState('');

  // UX Audit #4.5: anti-double-click state для action-кнопок.
  // Хранит {type, id} текущего action; пока не null — все action-кнопки disabled.
  const [processingAction, setProcessingAction] = useState(null);

  // UX Audit #4.2: client-side sort state для таба «История платежей».
  // Сортировка применяется к уже загруженным filteredPayments (после groupPaymentsByPatientAndTime).
  // Поддерживаемые поля: 'date' | 'patient' | 'amount'.
  const [sortField, setSortField] = useState('date');
  const [sortDir, setSortDir] = useState('desc'); // 'asc' | 'desc'

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
  const [stats, setStats] = useState({
    total_amount: 0,
    cash_amount: 0,
    card_amount: 0,
    pending_count: 0,
    pending_amount: 0,
    paid_count: 0,
    cancelled_count: 0
  });

  // ✅ УЛУЧШЕНИЕ: Универсальные хуки вместо дублированных состояний
  const paymentModal = useModal();
  const paymentWidget = useModal();

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
        if (statsResult.success && statsResult.data) {
          setStats(statsResult.data);
        }
      } catch (error) {
        logger.error('Error loading stats:', error);
        setStats({
          total_amount: 0,
          cash_amount: 0,
          card_amount: 0,
          pending_count: 0,
          pending_amount: 0,
          paid_count: 0,
          cancelled_count: 0
        });
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
          setAppointments(appointmentsData);

          if (pendingResult.pagination) {
            setPendingTotalPages(pendingResult.pagination.pages);
            setPendingTotalItems(pendingResult.pagination.total);
          }
        } else {
          logger.warn('Error loading pending payments:', pendingResult.error);
          setAppointments([]);
        }
      } catch (error) {
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
          setPayments(paymentsData);

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
      } catch (error) {
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

  // MEDIUM #15: CashierPanel hotkeys — focus search (Ctrl+F), refresh (F5 / Ctrl+R), export (Ctrl+E).
  // Only triggers when not focused in input/textarea to avoid hijacking text entry.
  // Note: handlers use lazy references via refs because some callbacks (exportToCSV)
  // are defined further down in the component body.
  const handlersRef = useRef({});
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

  // Deferred #1: session timeout warning — prevents silent JWT expiry while
  // cashier is processing a payment. Mirrors all other clinical panels.
  const [sessionWarning, setSessionWarning] = useState(null);
  // UX Audit #2.5: счётчик секунд до истечения сессии.
  const [sessionSecondsLeft, setSessionSecondsLeft] = useState(null);
  useSessionTimeoutWarning({
    onWarning: (expiresAt) => {
      // UX Audit #2.5: сохраняем expiresAt для счётчика обратного отсчёта.
      const ms = expiresAt ? (expiresAt - Date.now()) : 60 * 1000;
      setSessionWarning({ active: true, expiresAt });
      setSessionSecondsLeft(Math.max(0, Math.floor(ms / 1000)));
    },
    onExpired: () => {
      setSessionWarning(null);
      setSessionSecondsLeft(null);
      notify.error(tI18n('cashier.session_expired'));
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    },
  });

  // UX Audit #2.5: тикаем каждую секунду, пока показано предупреждение.
  useEffect(() => {
    if (!sessionWarning?.active || !sessionWarning.expiresAt) return undefined;
    const tick = () => {
      const ms = sessionWarning.expiresAt - Date.now();
      setSessionSecondsLeft(Math.max(0, Math.floor(ms / 1000)));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [sessionWarning]);

  // UX Audit #2.3: используем единый formatUZS из utils/formatCurrency.js.
  // Раньше тут было inline-определение new Intl.NumberFormat('ru-RU').format(n) + ' сум',
  // что приводило к расхождениям с CashPaymentModal (formatCurrency → «UZS»)
  // и RefundRequestsTable (toLocaleString + «сум»).
  const format = formatUZS;

  // ✅ УЛУЧШЕНИЕ: Обработчики с универсальными хуками
  const handlePaymentSuccess = (paymentData) => {
    setPaymentSuccess(paymentData);
    paymentWidget.closeModal();
    // Force reload to get fresh data after successful payment.
    triggerDataReload();
  };

  const handlePaymentError = (error) => {
    const message = getErrorMessage(error, tI18n('cashier.payment_process_failed'));
    setPaymentError(message);
    logger.error('Ошибка платежа:', error);
  };

  const handlePaymentCancel = () => {
    paymentWidget.closeModal();
  };

  const openPaymentWidget = (appointment) => {
    if (!canCreateDirectCashierPayment(appointment) || isBackendGroupedCashierPayment(appointment)) {
      const message = tI18n('cashier.online_payment_group_unavailable');
      setPaymentError(message);
      notify.error(message);
      return;
    }
    paymentWidget.openModal(appointment);
    setPaymentError(null);
    setPaymentSuccess(null);
  };

  // ✅ УЛУЧШЕНИЕ: Функции для работы с оплатами через SSOT hook
  // Теперь appointment содержит сгруппированные данные пациента (все его неоплаченные визиты)
  const processPayment = async (appointment, paymentData) => {
    try {
      const groupedPayment = isBackendGroupedCashierPayment(appointment);
      const visitId = resolveSingleCashierVisitId(appointment);

      if (!groupedPayment && !visitId) {
        throw new Error('Cannot process payment: backend must provide exactly one visit_id or a backend-owned allocation contract.');
      }

      if (groupedPayment) {
        await createGroupedCashierPayment(appointment, paymentData);
      } else {
        const result = await paymentsHook.createPayment({
          visit_id: visitId,
          amount: paymentData.amount,
          method: paymentData.method,
          note: paymentData.note || tI18n('cashier.payment_note_default')
        });

        if (!result.success) {
          throw new Error(tI18n('cashier.payment_visit_failed', { visitId, error: result.error }));
        }
      }

      notify.success(tI18n('cashier.payment_success', { amount: format(paymentData.amount) }));
      paymentModal.closeModal();
      setPendingPage(1);
      setRefreshKey((prev) => prev + 1); // Принудительное обновление списка

    } catch (error) {
      logger.error('Ошибка обработки платежа:', error);
      const message = getErrorMessage(error, tI18n('cashier.payment_process_failed'));
      setPaymentError(message);
      notify.error(message);
    }
  };

  // ✅ УЛУЧШЕНИЕ: Функции для работы с кнопками в истории платежей
  const confirmPayment = async (paymentId) => {
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
      setRefreshKey((prev) => prev + 1); // Обновляем данные
    } catch (err) {
      logger.error('Error confirming payment:', err);
      notify.error(getErrorMessage(err, tI18n('cashier.payment_confirm_failed')));
    } finally {
      setProcessingAction(null);
    }
  };

  const openCancelDialog = (payment) => {
    // UX Audit #2.1: принимаем объект payment целиком, чтобы показать контекст.
    // Раньше принимали только paymentId, и в диалоге было видно только #{id}.
    const paymentId = typeof payment === 'object' && payment !== null
      ? (payment.id || payment.payment_id)
      : payment;
    const patient = typeof payment === 'object' && payment !== null
      ? (payment.patient || payment.patient_name || tI18n('cashier.patient_with_id', { id: payment.patient_id }))
      : null;
    const amount = typeof payment === 'object' && payment !== null
      ? Number(payment.total_amount || payment.amount || 0)
      : 0;
    setCancelPaymentContext({ id: paymentId, patient, amount });
    setCancelDialogOpen(true);
    setCancelReason('');
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
      if (result.success) {
        setCancelDialogOpen(false);
        setCancelPaymentContext(null);
        setCancelReason('');
        notify.info(tI18n('cashier.payment_cancelled'));
        triggerDataReload();
      } else {
        notify.error(getErrorMessage(result.error, tI18n('cashier.refund_failed')));
      }
    } catch (error) {
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

      if (!result.success) {
        notify.error(
          getErrorMessage(
            result.error,
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

  // ✅ v2.0: Состояние для возврата
  const [refundDialogOpen, setRefundDialogOpen] = useState(false);
  const [refundPaymentId, setRefundPaymentId] = useState(null);
  const [refundPaymentAmount, setRefundPaymentAmount] = useState(0);
  const [refundAmount, setRefundAmount] = useState('');
  const [refundReason, setRefundReason] = useState('');

  // ✅ v2.0: Обработчик открытия диалога возврата
  const openRefundDialog = (payment) => {
    setRefundPaymentId(payment.id);
    setRefundPaymentAmount(payment.amount);
    setRefundAmount(String(payment.amount - (payment.refunded_amount || 0)));
    setRefundReason('');
    setRefundDialogOpen(true);
  };

  // ✅ v2.0: Обработчик возврата
  const handleRefund = async () => {
    if (!refundAmount || !refundReason || refundReason.length < 3) {
      notify.warning(tI18n('cashier.refund_fields_required'));
      return;
    }
    try {
      // UX Audit #4.5: anti-double-click protection.
      setProcessingAction({ type: 'refund', id: refundPaymentId });
      const result = await paymentsHook.refundPayment(refundPaymentId, {
        amount: parseFloat(refundAmount),
        reason: refundReason
      });
      if (result.success) {
        setRefundDialogOpen(false);
        setRefundPaymentId(null);
        setRefundReason('');
        setRefundAmount('');
        notify.success(tI18n('cashier.refund_success_amount', { amount: result.data.refunded_amount }));
        triggerDataReload();
      } else {
        notify.error(getErrorMessage(result.error, tI18n('cashier.refund_create_failed')));
      }
    } catch (error) {
      notify.error(getErrorMessage(error, tI18n('cashier.refund_failed')));
    } finally {
      setProcessingAction(null);
    }
  };

  // ✅ v2.0: Обработчик печати чека
  const handlePrintReceipt = async (paymentRowOrId) => {
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
        } catch (error) {
          logger.error('[Cashier] Unexpected browser receipt print error:', error);
        }
      }

      const result = await paymentsHook.getReceipt(paymentId);
      if (!result.success) {
        notify.error(getErrorMessage(result.error, tI18n('cashier.receipt_load_failed')));
        return;
      }

      notify.warning(tI18n('cashier.print_dialog_failed'));
    } finally {
      setProcessingAction(null);
    }
  };

  // ✅ v2.0: Состояние для почасовой статистики
  const [hourlyStats, setHourlyStats] = useState([]);
  const [showHourlyChart, setShowHourlyChart] = useState(false);

  // ✅ v2.0: Загрузка почасовой статистики
  const loadHourlyStats = async () => {
    const result = await paymentsHook.getHourlyStats({ target_date: selectedDate });
    if (result.success) {
      setHourlyStats(result.data);
      setShowHourlyChart(true);
    } else {
      notify.error(getErrorMessage(result.error, tI18n('cashier.stats_load_failed')));
    }
  };

  // ✅ ОТОБРАЖЕНИЕ УСЛУГ: Рендерим коды услуг с бейджами и tooltip (как в RegistrarPanel)
  const renderServiceBadges = (serviceCodes, serviceNames) => {
    // Если нет кодов, возвращаем пустой элемент
    if (!serviceCodes || !Array.isArray(serviceCodes) || serviceCodes.length === 0) {
      return <span className="cashier-empty">—</span>;
    }

    // ✅ ИСПРАВЛЕНИЕ: Обрабатываем случай когда services - это массив объектов {id, name, price, quantity}
    let codes = serviceCodes;
    let names = serviceNames;

    // Проверяем, является ли первый элемент объектом
    if (serviceCodes.length > 0 && typeof serviceCodes[0] === 'object' && serviceCodes[0] !== null) {
      // Извлекаем имена услуг из объектов
      codes = serviceCodes.map((s) => s.name || s.code || tI18n('cashier.service_fallback', { id: s.id || '?' }));
      names = serviceCodes.map((s) => {
        const parts = [];
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
              {code}
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

  // ✅ ГРУППИРОВКА: Объединяем платежи одного пациента, созданных в одно время
  // NOTE: Server pagination makes grouping across pages impossible. 
  // We only group within the current page.
  const groupPaymentsByPatientAndTime = (paymentsList) => {
    if (!paymentsList) return [];

    // Convert backend specific date/time format if needed
    // The backend returns 'created_at'. We can use that.

    const grouped = {};

    paymentsList.forEach((payment) => {
      // Parse dates from backend
      const dateObj = parseRegistrarTimestamp(payment.created_at);
      const dateKey = formatRegistrarDate(dateObj || payment.created_at);
      const timeKey = formatRegistrarTime(dateObj || payment.created_at);

      const groupKey = `${payment.patient_id}_${dateKey}_${timeKey}`;

      if (!grouped[groupKey]) {
        // Создаём новую группу
        grouped[groupKey] = {
          ...payment,
          services: Array.isArray(payment.services) ? [...payment.services] : [],
          services_names: Array.isArray(payment.services_names) ? [...payment.services_names] : [],
          grouped_payments: [payment.id],
          total_amount: Number(payment.amount || 0),
          date: dateKey, // Display helpers
          time: timeKey,
          patient: payment.patient_name,
          service: payment.service || null
        };
      } else {
        grouped[groupKey].grouped_payments.push(payment.id);
        grouped[groupKey].total_amount += Number(payment.amount);
        if (payment.service && !grouped[groupKey].service) {
          grouped[groupKey].service = payment.service;
        }
        if (Array.isArray(payment.services)) {
          grouped[groupKey].services.push(...payment.services);
        }
        if (Array.isArray(payment.services_names)) {
          grouped[groupKey].services_names.push(...payment.services_names);
        }
      }
    });

    return Object.values(grouped).map((group) => ({
      ...group,
      services: Array.from(new Set(group.services.filter(Boolean))),
      services_names: Array.from(new Set(group.services_names.filter(Boolean))),
      service: group.service || group.services_names[0] || group.services[0] || null
    }));
  };

  // Group payments for display (already filtered by server)
  // UX Audit #4.2: client-side sort по sortField/sortDir.
  const toggleSort = (field) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  };

  const groupedPayments = groupPaymentsByPatientAndTime(payments);
  const sortedPayments = [...groupedPayments].sort((a, b) => {
    let aVal, bVal;
    if (sortField === 'amount') {
      aVal = Number(a.total_amount || a.amount || 0);
      bVal = Number(b.total_amount || b.amount || 0);
    } else if (sortField === 'patient') {
      aVal = String(a.patient || '').toLowerCase();
      bVal = String(b.patient || '').toLowerCase();
    } else {
      // 'date' — sortBy date+time string
      aVal = `${a.date || ''} ${a.time || ''}`;
      bVal = `${b.date || ''} ${b.time || ''}`;
    }
    const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    return sortDir === 'asc' ? cmp : -cmp;
  });

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
                  onChange={setDateMode}
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
                    onChange={(id) => {
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
                    onChange={(id) => {
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
          <Card variant="outline" className="cashier-stats-card">
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
                size="sm"
                variant="outline"
                onClick={handleRefresh}
                title={tI18n('cashier.refresh_title')}>

                {tI18n('cashier.refresh_btn')}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={exportToCSV}
                title={tI18n('cashier.export_title')}>

                {tI18n('cashier.export_btn')}
              </Button>
              <Button
                size="sm"
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
                setActiveTab(newTab);
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
                      key={`${appointment.record_type || 'appointment'}-${appointment.id || index}-${appointment.visit_ids?.join('-') || ''}`}
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
                              {format(appointment.total_amount || appointment.remaining_amount || appointment.payment_amount || 0)}
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
                            size="sm"
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
                            size="sm"
                            onClick={() => {
                              paymentModal.openModal(appointment);
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
                    size="sm"
                    variant="outline"
                    disabled={pendingPage === 1 || pendingLoading}
                    onClick={() => setPendingPage((p) => Math.max(1, p - 1))}>

                          {tI18n('cashier.prev_page')}
                        </Button>
                        <span className="cashier-pagination-info">
                          {tI18n('cashier.pagination_info', { current: pendingPage, total: pendingTotalPages, total_items: pendingTotalItems })}
                        </span>
                        <Button
                    size="sm"
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
                <Button size="sm" variant="outline" onClick={() => setActiveTab('history')}>
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
                                {row.patient}
                              </td>
                              <td className="cashier-text-sm cashier-text-primary">
                                {/* PR-43 / Medium-24: services info rendered from row.service
                                    (single service name). Multi-service breakdown requires
                                    backend changes to the history endpoint payload. */}
                                 {row.service || '—'}
                              </td>
                              <td className="cashier-text-sm cashier-text-primary">
                                {row.method}
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
                                  size="sm"
                                  variant="success"
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
                            <td colSpan="7" className="cashier-empty-cell">
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
                    size="sm"
                    variant="outline"
                    disabled={currentPage === 1 || historyLoading}
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}>

                          {tI18n('cashier.prev_page')}
                        </Button>
                        <span className="cashier-pagination-info">
                          {tI18n('cashier.pagination_info', { current: currentPage, total: totalPages, total_items: totalItems })}
                        </span>
                        <Button
                    size="sm"
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
            onClose={() => setCancelDialogOpen(false)}
            maxWidth="sm"
            fullWidth>

            <DialogTitle>{tI18n('cashier.cancel_dialog_title')}</DialogTitle>
            <DialogContent>
              {cancelPaymentContext && (
                <div className="cashier-cancel-context" role="group" aria-label={tI18n('cashier.cancel_context_aria')}>
                  <Typography variant="body2" color="textSecondary">
                    {tI18n('cashier.payment_id_label', { id: cancelPaymentContext.id })}
                  </Typography>
                  {cancelPaymentContext.patient && (
                    <Typography variant="body1">
                      {tI18n('cashier.patient_label')} <strong>{cancelPaymentContext.patient}</strong>
                    </Typography>
                  )}
                  {cancelPaymentContext.amount > 0 && (
                    <Typography variant="body1">
                      {tI18n('cashier.amount_label')} <strong>{format(cancelPaymentContext.amount)}</strong>
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
              <Button variant="outline" onClick={() => setCancelDialogOpen(false)}>
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
                  {tI18n('cashier.patient_summary', { name: paymentWidget.selectedItem.patient_name, department: paymentWidget.selectedItem.department })}
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
                visitId={canCreateDirectCashierPayment(paymentWidget.selectedItem) ? resolveSingleCashierVisitId(paymentWidget.selectedItem) : null}
                amount={paymentWidget.selectedItem.remaining_amount || paymentWidget.selectedItem.total_amount || paymentWidget.selectedItem.cost || 0}
                currency="UZS"
                description={tI18n('cashier.payment_description', { department: paymentWidget.selectedItem.department || tI18n('cashier.payment_note_default') })}
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
                  {paymentSuccess.change_due > 0 &&
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
              <Button onClick={() => setPaymentSuccess(null)} variant="contained">
                OK
              </Button>
            </DialogActions>
          </Dialog>

          {/* ✅ v2.0: Диалог возврата */}
          <Dialog open={refundDialogOpen} onClose={() => setRefundDialogOpen(false)}>
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
              <Button variant="outline" onClick={() => setRefundDialogOpen(false)}>
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
          <Dialog open={showHourlyChart} onClose={() => setShowHourlyChart(false)}>
            <DialogTitle>
              {tI18n('cashier.hourly_stats_dialog_title', { date: selectedDate })}
            </DialogTitle>
            <DialogContent>
              {hourlyStats.filter((h) => h.count > 0).length > 0 ? (
                <div className="cashier-hourly-chart">
                  <ResponsiveContainer width="100%" height={300}>
                    <BarChart data={hourlyStats.filter((h) => h.count > 0)}>
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
                          background: 'var(--mac-surface, white)',
                          border: '1px solid var(--mac-border, #d8dde8)',
                          borderRadius: '8px',
                          fontSize: '13px',
                        }}
                        labelFormatter={(h) => `${h}:00`}
                        formatter={(value, name) => {
                          if (name === 'count') return [value, tI18n('cashier.hourly_stats_count_label')];
                          if (name === 'amount') return [formatUZS(value), tI18n('cashier.hourly_stats_amount_label')];
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
              <Button onClick={() => setShowHourlyChart(false)}>{tI18n('cashier.close_btn')}</Button>
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
                onClick={() => setSessionWarning(null)}
                className="cashier-session-warning-btn cashier-session-warning-btn--secondary">
                {tI18n('cashier.session_warning_dismiss')}
              </button>
              <button
                type="button"
                onClick={() => { setSessionWarning(null); notify.info(tI18n('cashier.session_extending')); }}
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
