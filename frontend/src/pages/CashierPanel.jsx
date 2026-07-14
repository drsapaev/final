import { useEffect, useState, useCallback, useRef } from 'react';
import './cashier.css';
import { useLocation } from 'react-router-dom';
import { CreditCard, Calendar, Search, CheckCircle, DollarSign, RefreshCw, XCircle, Undo2, Receipt, MoreVertical } from 'lucide-react';
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

const DATE_PRESETS = [
  { label: 'Сегодня',   getRange: () => ({ from: getLocalDateString(), to: getLocalDateString() }) },
  { label: 'Вчера',     getRange: () => ({ from: shiftDay(-1), to: shiftDay(-1) }) },
  { label: 'Неделя',    getRange: () => ({ from: shiftDay(-6), to: getLocalDateString() }) },
  { label: 'Месяц',     getRange: () => ({ from: shiftDay(-29), to: getLocalDateString() }) },
];

// Вспомогательная функция для создания прозрачного цвета была удалена (MEDIUM #14 dead code cleanup)
const PAYMENT_METHOD_LABELS = {
  cash: 'Наличные',
  card: 'Карта',
  payme: 'PayMe',
  click: 'Click'
};

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

const resolvePaymentMethodLabel = (method) => {
  const methodCode = resolvePaymentMethodCode(method);
  return PAYMENT_METHOD_LABELS[methodCode] || String(method || 'Наличные');
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

const buildReceiptPrintPayload = (paymentRow) => {
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
      method_name: resolvePaymentMethodLabel(paymentRow?.method),
      status: paymentRow?.status ?? null,
      paid_amount: receivedAmount,
      change: changeDue
    },
    patient: {
      full_name: paymentRow?.patient || paymentRow?.patient_name || 'Пациент',
      phone: paymentRow?.patient_phone || null
    },
    services,
    clinic: null
  };
};

const getPaymentStatusMeta = (status) => {
  const normalizedStatus = String(status || '').trim().toLowerCase();
  const statusMap = {
    paid: { variant: 'success', ariaLabel: 'Статус оплаты: оплачено' },
    partial: { variant: 'info', ariaLabel: 'Статус оплаты: частично оплачено' },
    cancelled: { variant: 'danger', ariaLabel: 'Статус оплаты: отменён' },
    refunded: { variant: 'danger', ariaLabel: 'Статус оплаты: возвращён' },
    pending: { variant: 'warning', ariaLabel: 'Статус оплаты: ожидает' },
    unknown: { variant: 'secondary', ariaLabel: 'Статус оплаты: неизвестно' },
  };

  return statusMap[normalizedStatus] || statusMap.unknown;
};

const getPaymentStatusLabel = (status) => {
  const normalizedStatus = String(status || '').trim().toLowerCase();
  const statusMap = {
    paid: 'Оплачено',
    partial: 'Частично',
    cancelled: 'Отменён',
    refunded: 'Возвращено',
    pending: 'Ожидает',
    unknown: 'Неизвестно',
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
  const location = useLocation();
  const { getStats, getPendingPayments, getPayments, ...paymentsHook } = usePayments();
  // ✅ v2.1: isLoading теперь вычисляется из отдельных loading состояний (см. ниже)

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
  useSessionTimeoutWarning({
    onWarning: () => setSessionWarning({ active: true }),
    onExpired: () => {
      setSessionWarning(null);
      notify.error('Сессия истекла. Пожалуйста, войдите снова.');
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    },
  });

  const format = (n) => new Intl.NumberFormat('ru-RU').format(n) + ' сум';

  // ✅ УЛУЧШЕНИЕ: Обработчики с универсальными хуками
  const handlePaymentSuccess = (paymentData) => {
    setPaymentSuccess(paymentData);
    paymentWidget.closeModal();
    // Force reload to get fresh data after successful payment.
    triggerDataReload();
  };

  const handlePaymentError = (error) => {
    const message = getErrorMessage(error, 'Не удалось обработать платёж. Проверьте соединение и попробуйте снова.');
    setPaymentError(message);
    logger.error('Ошибка платежа:', error);
  };

  const handlePaymentCancel = () => {
    paymentWidget.closeModal();
  };

  const openPaymentWidget = (appointment) => {
    if (!canCreateDirectCashierPayment(appointment) || isBackendGroupedCashierPayment(appointment)) {
      const message = 'Онлайн-оплата недоступна для групповых платежей. Используйте кнопку «Касса».';
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
          note: paymentData.note || 'Оплата медицинских услуг'
        });

        if (!result.success) {
          throw new Error(`Не удалось оплатить визит #${visitId}: ${result.error}`);
        }
      }

      notify.success(`Оплата успешно обработана! Сумма: ${format(paymentData.amount)}`);
      paymentModal.closeModal();
      setPendingPage(1);
      setRefreshKey((prev) => prev + 1); // Принудительное обновление списка

    } catch (error) {
      logger.error('Ошибка обработки платежа:', error);
      const message = getErrorMessage(error, 'Не удалось обработать платёж. Проверьте соединение и попробуйте снова.');
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
      title: 'Подтверждение платежа',
      message: 'Подтвердить этот платеж вручную?',
      description: 'Платеж будет отмечен как полученный. Действие можно отменить только через процедуру возврата.',
      confirmLabel: 'Принять',
      cancelLabel: 'Отмена',
      intent: 'primary',
    });
    if (!ok) {
      return;
    }

    try {
      await paymentsHook.confirmPayment(paymentId);
      setRefreshKey((prev) => prev + 1); // Обновляем данные
    } catch (err) {
      logger.error('Error confirming payment:', err);
      notify.error(getErrorMessage(err, 'Не удалось подтвердить платёж. Проверьте соединение и попробуйте снова.'));
    }
  };

  const openCancelDialog = (payment) => {
    // UX Audit #2.1: принимаем объект payment целиком, чтобы показать контекст.
    // Раньше принимали только paymentId, и в диалоге было видно только #{id}.
    const paymentId = typeof payment === 'object' && payment !== null
      ? (payment.id || payment.payment_id)
      : payment;
    const patient = typeof payment === 'object' && payment !== null
      ? (payment.patient || payment.patient_name || `Пациент #${payment.patient_id}`)
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
      notify.warning('Укажите причину отмены (минимум 10 символов)');
      return;
    }

    try {
      const result = await paymentsHook.cancelPayment(cancelPaymentContext.id, cancelReason.trim());
      if (result.success) {
        setCancelDialogOpen(false);
        setCancelPaymentContext(null);
        setCancelReason('');
        notify.info('Платёж отменён');
        triggerDataReload();
      } else {
        notify.error(getErrorMessage(result.error, 'Не удалось выполнить возврат. Проверьте соединение и попробуйте снова.'));
      }
    } catch (error) {
      notify.error(getErrorMessage(error, 'Не удалось отменить платёж. Проверьте соединение и попробуйте снова.'));
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
            'Не удалось экспортировать платежи. Проверьте соединение и попробуйте снова.'
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
      notify.warning('Укажите сумму возврата и причину (минимум 3 символа)');
      return;
    }
    try {
      const result = await paymentsHook.refundPayment(refundPaymentId, {
        amount: parseFloat(refundAmount),
        reason: refundReason
      });
      if (result.success) {
        setRefundDialogOpen(false);
        setRefundPaymentId(null);
        setRefundReason('');
        setRefundAmount('');
        notify.success(`Возврат успешно выполнен. Сумма: ${result.data.refunded_amount} UZS`);
        triggerDataReload();
      } else {
        notify.error(getErrorMessage(result.error, 'Не удалось оформить возврат. Проверьте соединение и попробуйте снова.'));
      }
    } catch (error) {
      notify.error(getErrorMessage(error, 'Не удалось выполнить возврат. Проверьте соединение и попробуйте снова.'));
    }
  };

  // ✅ v2.0: Обработчик печати чека
  const handlePrintReceipt = async (paymentRowOrId) => {
    const paymentId = resolvePaymentId(paymentRowOrId);

    if (!paymentId) {
      notify.error('Не удалось определить платеж для печати чека.');
      return;
    }

    if (paymentRowOrId && typeof paymentRowOrId === 'object') {
      try {
        const opened = printPanelReceiptInBrowser(buildReceiptPrintPayload(paymentRowOrId));
        if (opened) {
          notify.success('Открыт диалог печати этого компьютера.');
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
      notify.error(getErrorMessage(result.error, 'Не удалось получить чек. Проверьте соединение и попробуйте снова.'));
      return;
    }

    notify.warning('Диалог печати не открылся, поэтому был загружен PDF-чек.');
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
      notify.error(getErrorMessage(result.error, 'Не удалось загрузить статистику платежей. Проверьте соединение и попробуйте снова.'));
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
      codes = serviceCodes.map((s) => s.name || s.code || `Услуга #${s.id || '?'}`);
      names = serviceCodes.map((s) => {
        const parts = [];
        if (s.name) parts.push(s.name);
        if (s.price) parts.push(`${new Intl.NumberFormat('ru-RU').format(s.price)} сум`);
        if (s.quantity && s.quantity > 1) parts.push(`x${s.quantity}`);
        return parts.length > 0 ? parts.join(' — ') : `Услуга #${s.id || '?'}`;
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
          {codes.map((code, idx) =>
          <span key={idx} className="cashier-badge">
              {typeof code === 'string' ? code : String(code)}
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
  const filteredPayments = groupPaymentsByPatientAndTime(payments);


  return (
    <div className="cashier-root">

      <div className="cashier-root-inner">
        <div className="max-w-7xl mx-auto space-y-6">

          {/* Filters */}
          <Card
            variant="default"
            padding="default"
            className="cashier-mb-4">

            <div className="cashier-filter-row">
              {/* Поиск */}
              <div className="cashier-search-wrap">
                <Search className="cashier-search-icon" />
                <input
                  id="cashier-search-input"
                  aria-label="Поиск платежей кассира"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="cashier-text-sm cashier-text-primary"
                  placeholder="Поиск по пациенту " />

              </div>

              {/* Статус — показывается только на табе истории платежей.
                  На табе «Ожидающие оплаты» статус заведомо = pending,
                  поэтому фильтр избыточен (закон Хика — убираем лишний выбор). */}
              {activeTab === 'history' && (
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  aria-label="Фильтр по статусу платежа"
                  className="cashier-text-sm cashier-text-primary">
                  <option value="all">Все статусы</option>
                  <option value="paid">Оплачено</option>
                  <option value="partial">Частично</option>
                  <option value="pending">Ожидает</option>
                  <option value="cancelled">Отменён</option>
                  <option value="refunded">Возвращён</option>
                </select>
              )}

              {/* Переключатель режима даты */}
              <div className="cashier-date-mode">
                <Calendar className="cashier-date-icon" />
                <SegmentedControl
                  options={[
                  { label: 'Одна дата', value: 'single' },
                  { label: 'Диапазон', value: 'range' }]
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
                    options={DATE_PRESETS.map((p) => ({ label: p.label, value: p.label }))}
                    value="__none__"
                    onChange={(label) => {
                      const preset = DATE_PRESETS.find((p) => p.label === label);
                      if (!preset) return;
                      setSelectedDate(preset.getRange().to);
                    }}
                    size="default"
                    aria-label="Быстрый выбор даты"
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
                    options={DATE_PRESETS.map((p) => ({ label: p.label, value: p.label }))}
                    value="__none__"
                    onChange={(label) => {
                      const preset = DATE_PRESETS.find((p) => p.label === label);
                      if (!preset) return;
                      const { from, to } = preset.getRange();
                      setDateFrom(from);
                      setDateTo(to);
                    }}
                    size="default"
                    aria-label="Быстрый выбор диапазона дат"
                  />
                </>
              }
            </div>
          </Card>

          {/* ✅ УЛУЧШЕНИЕ: Статистика платежей из API */}
          <Card variant="outline" className="cashier-stats-card">
            <div className="cashier-stats-grid">
              {/* LOW #20: Stats grid stays stable across tabs — same column count, different content. */}
              {activeTab === 'history' ?
              <>
                  <div className="cashier-text-center">
                    <div className="cashier-stat-num cashier-stat-accent">
                      {format(stats.total_amount)}
                    </div>
                    <div className="cashier-stat-cap">
                      Всего за период
                    </div>
                  </div>
                  <div className="cashier-text-center">
                    <div className="cashier-stat-num cashier-stat-green">
                      {format(stats.cash_amount)}
                    </div>
                    <div className="cashier-stat-cap">
                      Наличные
                    </div>
                  </div>
                  <div className="cashier-text-center">
                    <div className="cashier-stat-num cashier-stat-blue">
                      {format(stats.card_amount)}
                    </div>
                    <div className="cashier-stat-cap">
                      Карта
                    </div>
                  </div>
                  <div className="cashier-text-center">
                    <div className="cashier-stat-num cashier-stat-purple">
                      {stats.paid_count}
                    </div>
                    <div className="cashier-stat-cap">
                      Оплачено
                    </div>
                  </div>
                  {stats.cancelled_count > 0 &&
                <div className="cashier-text-center">
                      <div className="cashier-stat-num cashier-stat-danger">
                        {stats.cancelled_count}
                      </div>
                      <div className="cashier-stat-cap">
                        Отменено
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
                    Ожидает оплаты ({stats.pending_count} заявок)
                  </div>
                </div>
                <div className="cashier-text-center" aria-hidden="true" style={{ visibility: 'hidden' }}>
                  <div className="cashier-stat-num cashier-stat-green">0</div>
                  <div className="cashier-stat-cap">Наличные</div>
                </div>
                <div className="cashier-text-center" aria-hidden="true" style={{ visibility: 'hidden' }}>
                  <div className="cashier-stat-num cashier-stat-blue">0</div>
                  <div className="cashier-stat-cap">Карта</div>
                </div>
                <div className="cashier-text-center" aria-hidden="true" style={{ visibility: 'hidden' }}>
                  <div className="cashier-stat-num cashier-stat-purple">0</div>
                  <div className="cashier-stat-cap">Оплачено</div>
                </div>
              </>
              }
              <div className="cashier-refresh-row">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleRefresh}
                  title="Обновить данные">

                  Обновить
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={exportToCSV}
                  title="Экспорт в CSV">

                  Экспорт
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={loadHourlyStats}
                  title="Почасовая статистика">

                  Аналитика
                </Button>
              </div>
            </div>
          </Card>

          {/* Объединенная секция с вкладками */}
          <Card
            variant="default"
            padding="default">

            <MacOSTab
              tabs={[
              {
                id: 'pending',
                label: 'Ожидающие оплаты',
                icon: DollarSign,
                badge: appointments.length > 0 ? appointments.length : undefined
              },
              {
                id: 'history',
                label: 'История платежей',
                icon: CreditCard
              },
              {
                id: 'refunds',
                label: 'Возвраты',
                icon: RefreshCw
              }]
              }
              activeTab={activeTab}
              onTabChange={setActiveTab}
              size="md"
              variant="default" />


            {activeTab === 'pending' &&
            <div className="cashier-section-gap">
                {pendingLoading ?
              <Skeleton className="cashier-skeleton-h" /> :
              appointments.length > 0 ?
              <div className="cashier-table-scroll">
                    <table className="cashier-table">
                      <thead>
                        <tr className="cashier-table-row">
                          <th className="cashier-text-sm cashier-text-primary">Дата/Время</th>
                          <th className="cashier-text-sm cashier-text-primary">Пациент</th>
                          <th className="cashier-text-sm cashier-text-primary">Услуги</th>
                          <th className="cashier-text-sm cashier-text-primary">Сумма</th>
                          <th className="cashier-text-sm cashier-text-primary">Статус</th>
                          <th className="cashier-text-sm cashier-text-primary">Действия</th>
                        </tr>
                      </thead>
                      <tbody>
                        {appointments.map((appointment, index) =>
                    <tr
                      key={`${appointment.record_type || 'appointment'}-${appointment.id || index}-${appointment.visit_ids?.join('-') || ''}`}
                      className="cashier-table-row">

                            <td
                              aria-label="Дата и время ожидаемого приёма"
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
                        appointment.patient_name || `Пациент #${appointment.patient_id}`
                        }
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
                                aria-label="Статус оплаты: ожидает">
                                Ожидает оплаты
                              </Badge>
                            </td>
                            <td className="cashier-cell-padded">
                              <div className="cashier-refresh-row">
                                <Button
                            size="sm"
                            variant="outline"
                            onClick={() => openPaymentWidget(appointment)}
                            disabled={!canCreateDirectCashierPayment(appointment) || isBackendGroupedCashierPayment(appointment)}
                            aria-label="Начать онлайн-оплату"
                            title={!canCreateDirectCashierPayment(appointment) || isBackendGroupedCashierPayment(appointment) ? 'Онлайн-оплата недоступна для этой записи' : 'Оплата онлайн'}>

                                  Онлайн
                                </Button>
                                <Button
                            size="sm"
                            onClick={() => {
                              paymentModal.openModal(appointment);
                            }}
                            disabled={!canCreateCashierPayment(appointment)}
                            aria-label="Принять оплату через кассу"
                            title={!canCreateCashierPayment(appointment) ? 'Приём оплаты недоступен для этой записи' : 'Принять оплату через кассу'}>

                                  Касса
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

                          ← Назад
                        </Button>
                        <span className="cashier-pagination-info">
                          Страница {pendingPage} из {pendingTotalPages} (Всего: {pendingTotalItems})
                        </span>
                        <Button
                    size="sm"
                    variant="outline"
                    disabled={pendingPage === pendingTotalPages || pendingLoading}
                    onClick={() => setPendingPage((p) => Math.min(pendingTotalPages, p + 1))}>

                          Вперёд →
                        </Button>
                      </div>
                }
                  </div> :

              <div className="cashier-text-sm cashier-text-secondary">
                    Нет записей, ожидающих оплаты
                  </div>
              }
              </div>
            }

            {activeTab === 'history' &&
            <div className="cashier-section-gap">
                {historyLoading ?
              <Skeleton className="cashier-skeleton-h" /> :

              <div className="cashier-table-scroll">
                    <table className="cashier-table">
                      <thead>
                        <tr className="cashier-table-row">
                          <th className="cashier-text-sm cashier-text-primary">Дата/Время</th>
                          <th className="cashier-text-sm cashier-text-primary">Пациент</th>
                          <th className="cashier-text-sm cashier-text-primary">Услуга</th>
                          <th className="cashier-text-sm cashier-text-primary">Способ</th>
                          <th className="cashier-text-sm cashier-text-primary">Сумма</th>
                          <th className="cashier-text-sm cashier-text-primary">Статус</th>
                          <th className="cashier-text-sm cashier-text-primary">Действия</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredPayments.length > 0 ?
                    filteredPayments.map((row, index) =>
                    <tr key={`payment-${row.id || row.payment_id || index}`} className="cashier-table-row">

                              <td
                                aria-label="Дата и время платежа в истории"
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
                                  variant={getPaymentStatusMeta(row.status).variant}
                                  role="status"
                                  aria-label={getPaymentStatusMeta(row.status).ariaLabel}>
                                  {getPaymentStatusLabel(row.status)}
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
                                  disabled={!hasBackendPaymentAction(row, 'confirm')}
                                  aria-label="Подтвердить платёж">
                                  <CheckCircle size={14} /> Принять
                                </Button>
                                <details className="cashier-overflow-menu">
                                  <summary className="cashier-overflow-trigger" aria-label="Дополнительные действия с платёжом">
                                    <MoreVertical size={16} aria-hidden="true" />
                                  </summary>
                                  <div className="cashier-overflow-popover" role="menu">
                                    <button
                                      type="button"
                                      className="cashier-overflow-item cashier-overflow-item--danger"
                                      onClick={() => openCancelDialog(row)}
                                      disabled={!hasBackendPaymentAction(row, 'cancel')}
                                      role="menuitem"
                                      aria-label="Отменить платёж">
                                      <XCircle size={14} aria-hidden="true" /> Отменить платёж
                                    </button>
                                    <button
                                      type="button"
                                      className="cashier-overflow-item cashier-overflow-item--warning"
                                      onClick={() => openRefundDialog(row)}
                                      disabled={!hasBackendPaymentAction(row, 'refund')}
                                      role="menuitem"
                                      aria-label="Оформить возврат">
                                      <Undo2 size={14} aria-hidden="true" /> Оформить возврат
                                    </button>
                                    <button
                                      type="button"
                                      className="cashier-overflow-item"
                                      onClick={() => handlePrintReceipt(row)}
                                      disabled={!hasBackendPaymentAction(row, 'print_receipt')}
                                      role="menuitem"
                                      aria-label="Распечатать чек">
                                      <Receipt size={14} aria-hidden="true" /> Печать чека
                                    </button>
                                  </div>
                                </details>
                              </td>
                            </tr>
                    ) :

                    <tr className="cashier-empty-row">
                            <td colSpan="7" className="cashier-text-sm cashier-text-secondary">
                              Нет данных для отображения
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

                          ← Назад
                        </Button>
                        <span className="cashier-pagination-info">
                          Страница {currentPage} из {totalPages} (Всего: {totalItems})
                        </span>
                        <Button
                    size="sm"
                    variant="outline"
                    disabled={currentPage === totalPages || historyLoading}
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}>

                          Вперёд →
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

            <DialogTitle>Отмена платежа</DialogTitle>
            <DialogContent>
              {cancelPaymentContext && (
                <div className="cashier-cancel-context" role="group" aria-label="Контекст отменяемого платежа">
                  <Typography variant="body2" color="textSecondary">
                    Платёж #{cancelPaymentContext.id}
                  </Typography>
                  {cancelPaymentContext.patient && (
                    <Typography variant="body1">
                      Пациент: <strong>{cancelPaymentContext.patient}</strong>
                    </Typography>
                  )}
                  {cancelPaymentContext.amount > 0 && (
                    <Typography variant="body1">
                      Сумма: <strong>{format(cancelPaymentContext.amount)}</strong>
                    </Typography>
                  )}
                </div>
              )}
              <Typography variant="body2" className="cashier-mb-4">
                Это действие нельзя отменить. Укажите причину для аудита.
              </Typography>
              <textarea
                aria-label="Причина отмены платежа (обязательно, минимум 10 символов)"
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                placeholder="Причина отмены (обязательно, минимум 10 символов)"
                required
                minLength={10}
                className="cashier-text-sm cashier-text-primary cashier-refund-textarea" />
              <Typography variant="caption" color="textSecondary">
                {cancelReason.trim().length}/10 символов
              </Typography>
            </DialogContent>
            <DialogActions>
              <Button variant="outline" onClick={() => setCancelDialogOpen(false)}>
                Закрыть
              </Button>
              <Button
                variant="danger"
                onClick={handleCancelPayment}
                disabled={cancelReason.trim().length < 10}>
                Отменить платёж
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
                Онлайн-оплата
              </Typography>
              {paymentWidget.selectedItem &&
              <Typography variant="body2" color="textSecondary">
                  Пациент: {paymentWidget.selectedItem.patient_name} • {paymentWidget.selectedItem.department}
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
                description={`Оплата за ${paymentWidget.selectedItem.department || 'медицинские услуги'}`}
                onSuccess={handlePaymentSuccess}
                onError={handlePaymentError}
                onCancel={handlePaymentCancel} />

              }
            </DialogContent>

            <DialogActions>
              <Button onClick={handlePaymentCancel}>
                Закрыть
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
                Оплата успешна!
              </Box>
            </DialogTitle>

            <DialogContent>
              {paymentSuccess &&
              <Box>
                  <Typography variant="body1" gutterBottom>
                    Платёж успешно обработан
                  </Typography>
                  {paymentSuccess.amount !== undefined &&
                  <Typography variant="body2" color="textSecondary">
                    Сумма: {format(Number(paymentSuccess.amount) || 0)}
                  </Typography>
                  }
                  {paymentSuccess.change_due > 0 &&
                  <Typography variant="body2" color="textSecondary">
                    Сдача: {format(Number(paymentSuccess.change_due))}
                  </Typography>
                  }
                  <Typography variant="body2" color="textSecondary">
                    ID платежа: {paymentSuccess.payment_id}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Провайдер: {paymentSuccess.provider}
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
                Возврат средств
              </Box>
            </DialogTitle>
            <DialogContent>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Typography variant="body2" color="textSecondary">
                  Исходная сумма платежа: {refundPaymentAmount?.toLocaleString()} UZS
                </Typography>
                <Box>
                  <Typography variant="body2" gutterBottom>Сумма возврата:</Typography>
                  <input
                    type="number"
                    aria-label="Сумма возврата"
                    value={refundAmount}
                    onChange={(e) => setRefundAmount(e.target.value)}
                    className="cashier-refund-input"
                    max={refundPaymentAmount}
                    min={1} />

                </Box>
                <Box>
                  <Typography variant="body2" gutterBottom>Причина возврата:</Typography>
                  <textarea
                    aria-label="Причина возврата"
                    value={refundReason}
                    onChange={(e) => setRefundReason(e.target.value)}
                    placeholder="Укажите причину возврата (минимум 3 символа)"
                    rows={3}
                    className="cashier-refund-textarea" />

                </Box>
              </Box>
            </DialogContent>
            <DialogActions>
              <Button variant="outline" onClick={() => setRefundDialogOpen(false)}>
                Отмена
              </Button>
              <Button variant="danger" onClick={handleRefund}>
                Выполнить возврат
              </Button>
            </DialogActions>
          </Dialog>

          {/* ✅ v2.0: Диалог почасовой статистики */}
          <Dialog open={showHourlyChart} onClose={() => setShowHourlyChart(false)}>
            <DialogTitle>
              Почасовая статистика за {selectedDate}
            </DialogTitle>
            <DialogContent>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {hourlyStats.filter((h) => h.count > 0).length > 0 ?
                hourlyStats.filter((h) => h.count > 0).map((h) =>
                <Box key={h.hour} sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                      <Typography sx={{ width: 60, fontWeight: 600 }}>{h.hour}:00</Typography>
                      <Box sx={{
                    flex: 1,
                    height: 24,
                    backgroundColor: 'rgba(52, 199, 89, 0.2)',
                    borderRadius: 4,
                    position: 'relative'
                  }}>
                        <Box sx={{
                      width: `${Math.min(100, h.count / Math.max(...hourlyStats.map((s) => s.count)) * 100)}%`,
                      height: '100%',
                      backgroundColor: 'var(--mac-success)',
                      borderRadius: 4
                    }} />
                      </Box>
                      <Typography sx={{ width: 80, textAlign: 'right' }}>
                        {h.count} / {Number(h.amount).toLocaleString()}
                      </Typography>
                    </Box>
                ) :

                <Typography color="textSecondary">Нет платежей за этот день</Typography>
                }
              </Box>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setShowHourlyChart(false)}>Закрыть</Button>
            </DialogActions>
          </Dialog>
        </div>
      </div>
      {/* Session timeout warning dialog */}
      {sessionWarning && (
        <div
          role="alertdialog"
          aria-label="Предупреждение об истечении сессии"
          style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0,0,0,0.5)', display: 'flex',
            alignItems: 'center', justifyContent: 'center', zIndex: 10000,
          }}
        >
          <div style={{
            background: 'var(--mac-surface, white)', border: '1px solid var(--mac-border, #d8dde8)',
            borderRadius: '12px', padding: '24px', maxWidth: '420px', width: '90%',
          }}>
            <h3 style={{ margin: '0 0 12px 0', fontSize: '18px', color: 'var(--mac-text-primary, #1a1d29)' }}>
              Сессия скоро истечёт
            </h3>
            <p style={{ margin: '0 0 16px 0', fontSize: '14px', color: 'var(--mac-text-secondary, #6b7280)', lineHeight: 1.5 }}>
              Ваша сессия истекает. Несохранённые данные могут быть потеряны.
              Сохраните текущий платёж или продлите сессию.
            </p>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button onClick={() => setSessionWarning(null)} style={{ padding: '8px 16px', border: '1px solid var(--mac-border, #d8dde8)', borderRadius: '6px', background: 'transparent', cursor: 'pointer', fontSize: '14px' }}>
                Позже
              </button>
              <button onClick={() => { setSessionWarning(null); notify.info('Продлеваем сессию...'); }} style={{ padding: '8px 16px', border: 'none', borderRadius: '6px', background: 'var(--mac-accent, #dc2626)', color: 'white', cursor: 'pointer', fontSize: '14px' }}>
                Продлить сессию
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
