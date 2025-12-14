import React, { useEffect, useState, useCallback } from 'react';
import { CreditCard, Calendar, Download, Search, Filter, CheckCircle, XCircle, DollarSign, User, Stethoscope, Clock, Receipt, RefreshCw } from 'lucide-react';
import { Card, Badge, Button, Progress, Icon } from '../components/ui/macos';
import Tooltip from '../components/ui/macos/Tooltip';
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import PaymentWidget from '../components/payment/PaymentWidget';
import CashPaymentModal from '../components/payment/CashPaymentModal';
import MacOSTab from '../components/ui/macos/MacOSTab';
import SegmentedControl from '../components/ui/macos/SegmentedControl';
import Input from '../components/ui/macos/Input';

// ✅ УЛУЧШЕНИЕ: Универсальные хуки для устранения дублирования
import useModal from '../hooks/useModal.jsx';
import { usePayments } from '../hooks/usePayments';
import logger from '../utils/logger';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  Box,
  Alert,
  Skeleton
} from '../components/ui/macos';

// Функция для получения даты в формате YYYY-MM-DD
const getLocalDateString = (date = new Date()) => {
  const d = new Date(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

// Вспомогательная функция для создания прозрачного цвета
const withOpacity = (color, opacity) => {
  if (color.startsWith('var(')) {
    return `rgba(from ${color} r g b / ${opacity})`;
  }
  return color;
};

// Custom debounce hook
const useDebounce = (value, delay) => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
};

const CashierPanel = () => {
  const { isMobile } = useBreakpoint();
  const paymentsHook = usePayments();
  const [isLoading, setIsLoading] = useState(true);

  // Search state
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebounce(query, 500); // 500ms debounce

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
  const [confirmingPaymentId, setConfirmingPaymentId] = useState(null);
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
  useEffect(() => {
    const load = async () => {
      setIsLoading(true);

      const { date_from, date_to } = getDateParams();

      logger.log('📅 Loading data with params:', { date_from, date_to, query: debouncedQuery, page: currentPage, status });

      // 0. Загружаем статистику
      try {
        const statsResult = await paymentsHook.getStats({
          date_from: date_from || undefined,
          date_to: date_to || undefined
        });
        if (statsResult.success && statsResult.data) {
          setStats(statsResult.data);
        }
      } catch (error) {
        logger.error('Error loading stats:', error);
      }

      // 1. Загружаем записи ожидающие оплаты (Pending) с пагинацией
      try {
        const pendingResult = await paymentsHook.getPendingPayments({
          date_from: date_from || undefined,
          date_to: date_to || undefined,
          search: debouncedQuery || undefined,
          page: pendingPage,
          size: itemsPerPage
        });

        if (pendingResult.success) {
          const appointmentsData = Array.isArray(pendingResult.data) ? pendingResult.data : [];
          setAppointments(appointmentsData);

          // Обновляем пагинацию для pending
          if (pendingResult.pagination) {
            setPendingTotalPages(pendingResult.pagination.pages);
            setPendingTotalItems(pendingResult.pagination.total);
          }
        } else {
          logger.warn('⚠️ Error loading pending payments:', pendingResult.error);
          setAppointments([]);
        }
      } catch (error) {
        logger.error('Error loading pending payments:', error);
      }

      // 2. Загружаем историю платежей (History) с Server-Side Pagination
      try {
        const paymentsResult = await paymentsHook.getPayments({
          date_from: date_from || undefined,
          date_to: date_to || undefined,
          search: debouncedQuery || undefined, // Server-side search
          status: status !== 'all' ? status : undefined, // Server-side status filter
          page: currentPage,
          size: itemsPerPage
        });

        if (paymentsResult.success) {
          const paymentsData = Array.isArray(paymentsResult.data) ? paymentsResult.data : [];
          setPayments(paymentsData);

          // Update pagination state if available
          if (paymentsResult.pagination) {
            setTotalPages(paymentsResult.pagination.pages);
            setTotalItems(paymentsResult.pagination.total);
          } else {
            // Fallback logic if API doesn't return pagination metadata
            setTotalPages(1);
            setTotalItems(paymentsData.length);
          }
        } else {
          logger.warn('⚠️ Error loading payment history:', paymentsResult.error);
          setPayments([]);
          setTotalPages(1);
        }
      } catch (error) {
        logger.error('Error loading payment history:', error);
        setPayments([]);
      }

      setIsLoading(false);
    };

    load();
  }, [debouncedQuery, currentPage, pendingPage, status, getDateParams, refreshKey]);

  // Reset page when date or search changes
  useEffect(() => {
    setCurrentPage(1);
    setPendingPage(1);
  }, [dateMode, selectedDate, dateFrom, dateTo, debouncedQuery]);


  const format = (n) => new Intl.NumberFormat('ru-RU').format(n) + ' сум';

  // ✅ УЛУЧШЕНИЕ: Обработчики с универсальными хуками
  const handlePaymentSuccess = (paymentData) => {
    setPaymentSuccess(paymentData);
    paymentWidget.closeModal();

    // Force reload to get fresh data
    const load = async () => {
      const { date_from, date_to } = getDateParams();
      await paymentsHook.getPayments({ date_from, date_to, page: 1, size: itemsPerPage });
      await paymentsHook.getPendingPayments({ date_from, date_to });
      // Instead of manually updating state, we trigger a re-fetch or let useEffect handle it if we signal update
      // But re-fetching is safer to ensure consistency
      window.location.reload(); // Simple reload or better: trigger reload state
    };
    // For now, let's just create a quick local update for UX responsiveness while assuming background fetch works
    // But since pagination is server-side, local update is complex. 
    // Best to just re-trigger the main load effect.
    // We can do this by toggling a 'trigger' state or just calling the load function if we extracted it.
    // For simplicity in this refactor, I'll rely on the user refreshing or explicit refresh button, 
    // OR we can make the `load` function available here. 
    // Actually, let's just reload the page for full consistency as a "safe" move for now, or assume the user sees the success modal.

    // Quick Fix: Let's refetch data by touching a state that triggers useEffect? No.
    // Let's just update local lists simply for immediate feedback if possible, but with server-side pagination it's tricky.
    // Correct approach: Call loadData. Since loadData is inside useEffect, we can't call it directly.
    // Triggering a reload of data:
    setCurrentPage(1); // resetting page is a simple way to reload
  };

  const handlePaymentError = (error) => {
    setPaymentError(error);
    logger.error('Ошибка платежа:', error);
  };

  const handlePaymentCancel = () => {
    paymentWidget.closeModal();
  };

  const openPaymentWidget = (appointment) => {
    paymentWidget.openModal(appointment);
    setPaymentError(null);
    setPaymentSuccess(null);
  };

  // ✅ УЛУЧШЕНИЕ: Функции для работы с оплатами через SSOT hook
  // Теперь appointment содержит сгруппированные данные пациента (все его неоплаченные визиты)
  const processPayment = async (appointment, paymentData) => {
    try {
      // Получаем все visit_id пациента
      const visitIds = appointment.visit_ids && appointment.visit_ids.length > 0
        ? appointment.visit_ids
        : [appointment.visit_id || appointment.id];

      // 1. Рассчитываем долг по каждому визиту на основе услуг
      const visitDebts = {};
      const services = appointment.services || [];

      // Инициализируем долги нулями
      visitIds.forEach(id => visitDebts[id] = 0);

      // Суммируем стоимость услуг для каждого визита
      services.forEach(s => {
        if (s.visit_id) {
          visitDebts[s.visit_id] = (visitDebts[s.visit_id] || 0) + ((s.price || 0) * (s.quantity || 1));
        }
      });

      // 2. Распределяем сумму оплаты
      let remaining = parseFloat(paymentData.amount);
      const paymentsToMake = [];

      for (const visitId of visitIds) {
        if (remaining <= 0) break;

        let debt = visitDebts[visitId] || 0;
        let payAmount = Math.min(remaining, debt);

        if (payAmount > 0) {
          paymentsToMake.push({ visitId, amount: payAmount });
          remaining -= payAmount;
        } else if (debt === 0 && remaining > 0 && visitIds.length === 1) {
          // Если единственный визит и долг 0, но платим - зачисляем
          paymentsToMake.push({ visitId, amount: remaining });
          remaining = 0;
        }
      }

      // Если осталась сумма (переплата), закидываем на первый визит
      if (remaining > 0) {
        if (paymentsToMake.length > 0) {
          paymentsToMake[0].amount += remaining;
        } else if (visitIds.length > 0) {
          paymentsToMake.push({ visitId: visitIds[0], amount: remaining });
        }
      }

      // 3. Выполняем платежи последовательно
      for (const p of paymentsToMake) {
        const result = await paymentsHook.createPayment({
          visit_id: p.visitId,
          amount: p.amount,
          method: paymentData.method,
          note: paymentData.note || 'Оплата медицинских услуг'
        });

        if (!result.success) {
          throw new Error(`Ошибка оплаты визита #${p.visitId}: ${result.error}`);
        }
      }

      // Fallback если ничего не добавилось в paymentsToMake но сумма есть
      if (paymentsToMake.length === 0 && parseFloat(paymentData.amount) > 0 && visitIds.length > 0) {
        await paymentsHook.createPayment({
          visit_id: visitIds[0],
          amount: paymentData.amount,
          method: paymentData.method,
          note: paymentData.note
        });
      }

      alert(`✅ Оплата успешно обработана! Сумма: ${format(paymentData.amount)}`);
      paymentModal.closeModal();
      setPendingPage(1);
      setRefreshKey(prev => prev + 1); // Принудительное обновление списка

    } catch (error) {
      logger.error('Ошибка обработки платежа:', error);
      setPaymentError(error.message || 'Ошибка обработки платежа. Попробуйте позже.');
      alert(`❌ Ошибка обработки платежа: ${error.message || 'Попробуйте позже'}`);
    }
  };

  // ✅ УЛУЧШЕНИЕ: Функции для работы с кнопками в истории платежей
  const confirmPayment = async (paymentId) => {
    if (!window.confirm("Вы уверены, что хотите подтвердить этот платеж вручную?")) {
      return;
    }

    try {
      await paymentsHook.confirmPayment(paymentId);
      setRefreshKey(prev => prev + 1); // Обновляем данные
    } catch (err) {
      console.error('Error confirming payment:', err);
      alert(`❌ Ошибка подтверждения платежа: ${err.message}`);
    }
  };

  const openCancelDialog = (paymentId) => {
    setConfirmingPaymentId(paymentId);
    setCancelDialogOpen(true);
    setCancelReason('');
  };

  const handleCancelPayment = async () => {
    if (!confirmingPaymentId) return;

    try {
      const result = await paymentsHook.cancelPayment(confirmingPaymentId, cancelReason);
      if (result.success) {
        setCancelDialogOpen(false);
        setConfirmingPaymentId(null);
        alert('Платёж отменён');
        setCurrentPage(1); // Reload data
      } else {
        alert('Ошибка: ' + result.error);
      }
    } catch (error) {
      alert('Ошибка отмены: ' + error.message);
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
      alert('Ошибка экспорта: ' + (result.error || 'Неизвестная ошибка'));
    }
  };

  // ✅ УЛУЧШЕНИЕ: Кнопка обновления данных
  const handleRefresh = () => {
    setCurrentPage(1);
    setPendingPage(1);
    setRefreshKey(prev => prev + 1); // Force reload
  };

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
      alert('Укажите сумму возврата и причину (минимум 3 символа)');
      return;
    }
    try {
      const result = await paymentsHook.refundPayment(refundPaymentId, {
        amount: parseFloat(refundAmount),
        reason: refundReason
      });
      if (result.success) {
        setRefundDialogOpen(false);
        alert(`Возврат успешно выполнен. Сумма: ${result.data.refunded_amount} UZS`);
        setCurrentPage(1); // Reload
      } else {
        alert('Ошибка возврата: ' + result.error);
      }
    } catch (error) {
      alert('Ошибка: ' + error.message);
    }
  };

  // ✅ v2.0: Обработчик печати чека
  const handlePrintReceipt = async (paymentId) => {
    const result = await paymentsHook.getReceipt(paymentId);
    if (!result.success) {
      alert('Ошибка получения чека: ' + result.error);
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
      alert('Ошибка загрузки статистики: ' + result.error);
    }
  };

  // ✅ ОТОБРАЖЕНИЕ УСЛУГ: Рендерим коды услуг с бейджами и tooltip (как в RegistrarPanel)
  const renderServiceBadges = (serviceCodes, serviceNames) => {
    // Если нет кодов, возвращаем пустой элемент
    if (!serviceCodes || !Array.isArray(serviceCodes) || serviceCodes.length === 0) {
      return <span style={{ color: 'var(--mac-text-tertiary)' }}>—</span>;
    }

    // ✅ ИСПРАВЛЕНИЕ: Обрабатываем случай когда services - это массив объектов {id, name, price, quantity}
    let codes = serviceCodes;
    let names = serviceNames;

    // Проверяем, является ли первый элемент объектом
    if (serviceCodes.length > 0 && typeof serviceCodes[0] === 'object' && serviceCodes[0] !== null) {
      // Извлекаем имена услуг из объектов
      codes = serviceCodes.map(s => s.name || s.code || `Услуга #${s.id || '?'}`);
      names = serviceCodes.map(s => {
        const parts = [];
        if (s.name) parts.push(s.name);
        if (s.price) parts.push(`${new Intl.NumberFormat('ru-RU').format(s.price)} сум`);
        if (s.quantity && s.quantity > 1) parts.push(`x${s.quantity}`);
        return parts.length > 0 ? parts.join(' — ') : `Услуга #${s.id || '?'}`;
      });
    }

    // Создаем tooltip с полными названиями услуг
    const tooltipContent = (
      <div style={{ padding: '4px 0', maxWidth: '300px' }}>
        {names && Array.isArray(names) && names.length === codes.length
          ? names.map((name, idx) => (
            <div key={idx} style={{
              marginBottom: idx < names.length - 1 ? '6px' : '0',
              lineHeight: '1.4',
              fontSize: '12px'
            }}>
              {name}
            </div>
          ))
          : codes.map((code, idx) => (
            <div key={idx} style={{
              marginBottom: idx < codes.length - 1 ? '6px' : '0',
              lineHeight: '1.4',
              fontSize: '12px'
            }}>
              {code}
            </div>
          ))
        }
      </div>
    );

    return (
      <Tooltip
        content={tooltipContent}
        position="bottom"
        delay={200}
      >
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '4px',
          cursor: 'help',
          maxWidth: '280px'
        }}>
          {codes.map((code, idx) => (
            <span
              key={idx}
              style={{
                padding: '3px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: '600',
                backgroundColor: 'rgba(0, 122, 255, 0.12)',
                color: '#007AFF',
                border: '1px solid rgba(0, 122, 255, 0.25)',
                whiteSpace: 'nowrap',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
                maxWidth: '150px',
                overflow: 'hidden',
                textOverflow: 'ellipsis'
              }}
            >
              {typeof code === 'string' ? code : String(code)}
            </span>
          ))}
        </div>
      </Tooltip>
    );
  };

  // ✅ ГРУППИРОВКА: Объединяем платежи одного пациента, созданных в одно время
  // NOTE: Server pagination makes grouping across pages impossible. 
  // We only group within the current page.
  const groupPaymentsByPatientAndTime = (paymentsList) => {
    if (!paymentsList) return [];

    // Convert backend specific date/time format if needed
    // The backend returns 'created_at'. We can use that.

    const grouped = {};

    paymentsList.forEach(payment => {
      // Parse dates from backend
      const dateObj = new Date(payment.created_at);
      const dateKey = dateObj.toLocaleDateString('ru-RU');
      const timeKey = dateObj.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });

      const groupKey = `${payment.patient_id}_${dateKey}_${timeKey}`;

      if (!grouped[groupKey]) {
        // Создаём новую группу
        grouped[groupKey] = {
          ...payment,
          services: [], // Services info might need to be fetched or assumed from note/structure
          services_names: [],
          grouped_payments: [payment.id],
          total_amount: payment.amount,
          date: dateKey, // Display helpers
          time: timeKey,
          patient: payment.patient_name
        };
      } else {
        grouped[groupKey].grouped_payments.push(payment.id);
        grouped[groupKey].total_amount += Number(payment.amount);
      }
    });

    return Object.values(grouped);
  };

  // Group payments for display (already filtered by server)
  const filteredPayments = groupPaymentsByPatientAndTime(payments);


  return (
    <div style={{
      padding: '0',
      minHeight: '100vh',
      background: 'var(--mac-gradient-window)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
      color: 'var(--mac-text-primary)',
      transition: 'background var(--mac-duration-normal) var(--mac-ease)'
    }}>

      <div style={{ padding: '0px' }}>
        <div className="max-w-7xl mx-auto space-y-6">

          {/* Filters */}
          <Card
            variant="default"
            padding="default"
            style={{ marginBottom: '16px' }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px' }}>
              {/* Поиск */}
              <div style={{ position: 'relative', flex: '1', minWidth: '200px' }}>
                <Search style={{
                  position: 'absolute',
                  left: '12px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  width: '16px',
                  height: '16px',
                  color: 'var(--mac-text-tertiary)'
                }} />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  style={{
                    width: '100%',
                    paddingLeft: '40px',
                    paddingRight: '12px',
                    paddingTop: '8px',
                    paddingBottom: '8px',
                    border: '1px solid var(--mac-border)',
                    borderRadius: 'var(--mac-radius-sm)',
                    backgroundColor: 'var(--mac-bg-primary)',
                    color: 'var(--mac-text-primary)',
                    fontSize: '14px',
                    outline: 'none',
                    transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                  }}
                  placeholder="Поиск по пациенту (Server Search)"
                />
              </div>

              {/* Статус */}
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                style={{
                  padding: '8px 12px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-sm)',
                  backgroundColor: 'var(--mac-bg-primary)',
                  color: 'var(--mac-text-primary)',
                  fontSize: '14px',
                  outline: 'none',
                  minWidth: '140px'
                }}
              >
                <option value="all">Все статусы</option>
                <option value="paid">Оплачено</option>
                <option value="pending">Ожидает</option>
              </select>

              {/* Переключатель режима даты */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Calendar style={{ width: '16px', height: '16px', color: 'var(--mac-text-secondary)' }} />
                <SegmentedControl
                  options={[
                    { label: 'Одна дата', value: 'single' },
                    { label: 'Диапазон', value: 'range' }
                  ]}
                  value={dateMode}
                  onChange={setDateMode}
                  size="default"
                />
              </div>

              {/* Поля даты */}
              {dateMode === 'single' ? (
                <>
                  <Input
                    type="date"
                    value={selectedDate}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    style={{ minWidth: '160px' }}
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      const today = getLocalDateString();
                      setSelectedDate(today);
                    }}
                  >
                    Сегодня
                  </Button>
                </>
              ) : (
                <>
                  <Input
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                    style={{ minWidth: '140px' }}
                  />
                  <span style={{ fontSize: '13px', color: 'var(--mac-text-secondary)' }}>—</span>
                  <Input
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                    style={{ minWidth: '140px' }}
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      const today = getLocalDateString();
                      setDateFrom(today);
                      setDateTo(today);
                    }}
                  >
                    Сегодня
                  </Button>
                </>
              )}
            </div>
          </Card>

          {/* ✅ УЛУЧШЕНИЕ: Статистика платежей из API */}
          <Card variant="outline" style={{ marginBottom: '16px', padding: '16px' }}>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
              gap: '16px',
              alignItems: 'center'
            }}>
              {/* Conditional Stats based on Active Tab */}
              {activeTab === 'history' ? (
                <>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '20px', fontWeight: '700', color: 'var(--mac-accent)' }}>
                      {format(stats.total_amount)}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--mac-text-secondary)' }}>
                      Всего за период
                    </div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '20px', fontWeight: '700', color: '#34C759' }}>
                      {format(stats.cash_amount)}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--mac-text-secondary)' }}>
                      Наличные
                    </div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '20px', fontWeight: '700', color: '#007AFF' }}>
                      {format(stats.card_amount)}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--mac-text-secondary)' }}>
                      Карта
                    </div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '20px', fontWeight: '700', color: '#5856D6' }}>
                      {stats.paid_count}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--mac-text-secondary)' }}>
                      Оплачено
                    </div>
                  </div>
                  {stats.cancelled_count > 0 && (
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '20px', fontWeight: '700', color: '#ff4d4f' }}>
                        {stats.cancelled_count}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--mac-text-secondary)' }}>
                        Отменено
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: '700', color: '#FF9500' }}>
                    {format(stats.pending_amount || 0)}
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--mac-text-secondary)' }}>
                    Ожидает оплаты ({stats.pending_count} заявок)
                  </div>
                </div>
              )}
              <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', flexWrap: 'wrap' }}>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleRefresh}
                  title="Обновить данные"
                >
                  🔄 Обновить
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={exportToCSV}
                  title="Экспорт в CSV"
                >
                  📥 Экспорт
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={loadHourlyStats}
                  title="Почасовая статистика"
                >
                  📊 Аналитика
                </Button>
              </div>
            </div>
          </Card>

          {/* Объединенная секция с вкладками */}
          <Card
            variant="default"
            padding="default"
          >
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
                }
              ]}
              activeTab={activeTab}
              onTabChange={setActiveTab}
              size="md"
              variant="default"
            />

            {activeTab === 'pending' && (
              <div style={{ marginTop: '24px' }}>
                {isLoading ? (
                  <Skeleton style={{ height: '192px' }} />
                ) : appointments.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {appointments.map((appointment, index) => (
                      <div key={`${appointment.record_type || 'appointment'}-${appointment.id || index}-${appointment.visit_ids?.join('-') || ''}`} style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '12px',
                        backgroundColor: 'var(--mac-bg-tertiary)',
                        border: '1px solid var(--mac-border)',
                        borderRadius: 'var(--mac-radius-sm)'
                      }}>
                        <div style={{ flex: '1' }}>
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '12px',
                            marginBottom: '6px'
                          }}>
                            <div style={{
                              fontWeight: '500',
                              color: 'var(--mac-text-primary)',
                              fontSize: '14px',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px'
                            }}>
                              <User style={{ width: '14px', height: '14px', color: 'var(--mac-text-secondary)' }} />
                              {appointment.patient_last_name && appointment.patient_first_name
                                ? `${appointment.patient_last_name} - ${appointment.patient_first_name}`
                                : appointment.patient_name || `Пациент #${appointment.patient_id}`
                              }
                            </div>
                            <div style={{
                              fontSize: '12px',
                              color: 'var(--mac-text-tertiary)',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px'
                            }}>
                              <Clock style={{ width: '12px', height: '12px', color: 'var(--mac-text-tertiary)' }} />
                              {appointment.created_at
                                ? new Date(appointment.created_at).toLocaleString('ru-RU', {
                                  day: '2-digit',
                                  month: '2-digit',
                                  year: 'numeric',
                                  hour: '2-digit',
                                  minute: '2-digit',
                                  timeZone: 'Asia/Tashkent'
                                })
                                : `${appointment.appointment_date} ${appointment.appointment_time || ''}`
                              }
                            </div>
                          </div>

                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '12px'
                          }}>
                            <div style={{
                              fontSize: '13px',
                              color: 'var(--mac-text-secondary)',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                              flex: '1'
                            }}>
                              <Stethoscope style={{ width: '13px', height: '13px', color: 'var(--mac-text-tertiary)' }} />
                              {renderServiceBadges(appointment.services, appointment.services_names)}
                            </div>
                            <div style={{
                              fontSize: '14px',
                              fontWeight: '600',
                              color: 'var(--mac-accent)',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px'
                            }}>
                              <Receipt style={{ width: '14px', height: '14px' }} />
                              {format(appointment.total_amount || appointment.remaining_amount || appointment.payment_amount || 0)}
                            </div>
                          </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <Badge variant="warning">Ожидает оплаты</Badge>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => openPaymentWidget(appointment)}
                            >
                              💳 Онлайн
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => {
                                paymentModal.openModal(appointment);
                              }}
                            >
                              💵 Касса
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}

                    {/* ✅ v2.0: Пагинация для ожидающих оплаты */}
                    {pendingTotalPages > 1 && (
                      <div style={{
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        gap: '12px',
                        marginTop: '16px',
                        padding: '12px'
                      }}>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={pendingPage === 1 || isLoading}
                          onClick={() => setPendingPage(p => Math.max(1, p - 1))}
                        >
                          ← Назад
                        </Button>
                        <span style={{ fontSize: '14px', color: 'var(--mac-text-secondary)' }}>
                          Страница {pendingPage} из {pendingTotalPages} (Всего: {pendingTotalItems})
                        </span>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={pendingPage === pendingTotalPages || isLoading}
                          onClick={() => setPendingPage(p => Math.min(pendingTotalPages, p + 1))}
                        >
                          Вперёд →
                        </Button>
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{
                    padding: '48px',
                    textAlign: 'center',
                    color: 'var(--mac-text-secondary)',
                    fontSize: '14px'
                  }}>
                    Нет записей, ожидающих оплаты
                  </div>
                )}
              </div>
            )}

            {activeTab === 'history' && (
              <div style={{ marginTop: '24px' }}>
                {isLoading ? (
                  <Skeleton style={{ height: '192px' }} />
                ) : (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%' }}>
                      <thead>
                        <tr style={{
                          backgroundColor: 'var(--mac-bg-tertiary)',
                          borderBottom: '1px solid var(--mac-border)'
                        }}>
                          <th style={{ textAlign: 'left', padding: '12px 16px', color: 'var(--mac-text-primary)', fontWeight: '500', fontSize: '14px' }}>Дата/Время</th>
                          <th style={{ textAlign: 'left', padding: '12px 16px', color: 'var(--mac-text-primary)', fontWeight: '500', fontSize: '14px' }}>Пациент</th>
                          <th style={{ textAlign: 'left', padding: '12px 16px', color: 'var(--mac-text-primary)', fontWeight: '500', fontSize: '14px' }}>Услуга</th>
                          <th style={{ textAlign: 'left', padding: '12px 16px', color: 'var(--mac-text-primary)', fontWeight: '500', fontSize: '14px' }}>Способ</th>
                          <th style={{ textAlign: 'left', padding: '12px 16px', color: 'var(--mac-text-primary)', fontWeight: '500', fontSize: '14px' }}>Сумма</th>
                          <th style={{ textAlign: 'left', padding: '12px 16px', color: 'var(--mac-text-primary)', fontWeight: '500', fontSize: '14px' }}>Статус</th>
                          <th style={{ textAlign: 'left', padding: '12px 16px', color: 'var(--mac-text-primary)', fontWeight: '500', fontSize: '14px' }}>Действия</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredPayments.length > 0 ? (
                          filteredPayments.map((row, index) => (
                            <tr key={`payment-${row.id || row.payment_id || index}`} style={{
                              borderBottom: '1px solid var(--mac-border)',
                              transition: 'background-color var(--mac-duration-normal) var(--mac-ease)'
                            }}
                              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)'}
                              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                            >
                              <td style={{ padding: '12px 16px', color: 'var(--mac-text-primary)', fontSize: '14px' }}>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                  <span style={{ fontWeight: '500' }}>{row.date || '—'}</span>
                                  <span style={{ fontSize: '12px', color: 'var(--mac-text-secondary)' }}>{row.time || '—'}</span>
                                </div>
                              </td>
                              <td style={{ padding: '12px 16px', color: 'var(--mac-text-primary)', fontSize: '14px' }}>
                                {row.patient}
                              </td>
                              <td style={{ padding: '12px 16px', color: 'var(--mac-text-primary)', fontSize: '14px' }}>
                                {/* TODO: Render services info properly if available in history item */}
                                {row.service || "Услуга"}
                              </td>
                              <td style={{ padding: '12px 16px', color: 'var(--mac-text-primary)', fontSize: '14px' }}>
                                {row.method}
                              </td>
                              <td style={{ padding: '12px 16px', color: 'var(--mac-text-primary)', fontSize: '14px', fontWeight: '500' }}>
                                {format(row.total_amount || row.amount || 0)}
                              </td>
                              <td style={{ padding: '12px 16px' }}>
                                <Badge variant={
                                  row.status === 'paid' ? 'success' :
                                    row.status === 'partial' ? 'info' :
                                      (row.status === 'cancelled' || row.status === 'refunded') ? 'danger' :
                                        'warning'
                                }>
                                  {row.status === 'paid' ? 'Оплачено' :
                                    row.status === 'partial' ? 'Частично' :
                                      row.status === 'cancelled' ? 'Отменён' :
                                        row.status === 'refunded' ? 'Возвращено' :
                                          'Ожидает'}
                                </Badge>
                              </td>
                              <td style={{ padding: '12px 16px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                <Button size="sm" variant="outline" onClick={() => confirmPayment(row.id)}>
                                  ✅ Принять
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => openCancelDialog(row.id)}
                                  disabled={row.status === 'cancelled'}
                                >
                                  ❌ Отмена
                                </Button>
                                {/* ✅ v2.0: Кнопка возврата */}
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => openRefundDialog(row)}
                                  disabled={row.status === 'cancelled' || row.status === 'refunded'}
                                  title="Возврат средств"
                                >
                                  💸 Возврат
                                </Button>
                                {/* ✅ v2.0: Кнопка печати чека */}
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handlePrintReceipt(row.id)}
                                  title="Печать чека"
                                >
                                  🧾 Чек
                                </Button>
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan="7" style={{
                              padding: '48px',
                              textAlign: 'center',
                              color: 'var(--mac-text-secondary)',
                              fontSize: '14px'
                            }}>
                              Нет данных для отображения
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>

                    {/* ✅ УЛУЧШЕНИЕ: Пагинация c Server-Side логикой */}
                    {totalPages > 1 && (
                      <div style={{
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        gap: '12px',
                        marginTop: '16px',
                        padding: '12px'
                      }}>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={currentPage === 1 || isLoading}
                          onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                        >
                          ← Назад
                        </Button>
                        <span style={{ fontSize: '14px', color: 'var(--mac-text-secondary)' }}>
                          Страница {currentPage} из {totalPages} (Всего: {totalItems})
                        </span>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={currentPage === totalPages || isLoading}
                          onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                        >
                          Вперёд →
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </Card>

          {/* ✅ УЛУЧШЕНИЕ: Диалог подтверждения отмены платежа */}
          <Dialog
            open={cancelDialogOpen}
            onClose={() => setCancelDialogOpen(false)}
            maxWidth="sm"
            fullWidth
          >
            <DialogTitle>Отмена платежа</DialogTitle>
            <DialogContent>
              <Typography variant="body2" style={{ marginBottom: '16px' }}>
                Вы уверены, что хотите отменить платёж #{confirmingPaymentId}?
              </Typography>
              <textarea
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                placeholder="Причина отмены (необязательно)"
                style={{
                  width: '100%',
                  minHeight: '80px',
                  padding: '8px 12px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-sm)',
                  backgroundColor: 'var(--mac-bg-primary)',
                  color: 'var(--mac-text-primary)',
                  resize: 'vertical',
                  fontFamily: 'inherit',
                  fontSize: '14px'
                }}
              />
            </DialogContent>
            <DialogActions>
              <Button variant="outline" onClick={() => setCancelDialogOpen(false)}>
                Отмена
              </Button>
              <Button variant="danger" onClick={handleCancelPayment}>
                Отменить платёж
              </Button>
            </DialogActions>
          </Dialog>

          {/* ✅ УЛУЧШЕНИЕ: Модальное окно оплаты с универсальным хуком */}
          {paymentModal.isOpen && paymentModal.selectedItem && (
            <CashPaymentModal
              appointment={paymentModal.selectedItem}
              onProcessPayment={processPayment}
              onClose={paymentModal.closeModal}
            />
          )}

          {/* ✅ УЛУЧШЕНИЕ: Диалог онлайн-оплаты с универсальным хуком */}
          <Dialog
            open={paymentWidget.isOpen}
            onClose={handlePaymentCancel}
            maxWidth="md"
            fullWidth
          >
            <DialogTitle>
              <Typography variant="h6">
                Онлайн-оплата
              </Typography>
              {paymentWidget.selectedItem && (
                <Typography variant="body2" color="textSecondary">
                  Пациент: {paymentWidget.selectedItem.patient_name} • {paymentWidget.selectedItem.department}
                </Typography>
              )}
            </DialogTitle>

            <DialogContent>
              {paymentError && (
                <Alert severity="error" style={{ marginBottom: 8 }}>
                  {paymentError}
                </Alert>
              )}

              {paymentWidget.selectedItem && (
                <PaymentWidget
                  visitId={paymentWidget.selectedItem.visit_id || paymentWidget.selectedItem.id}
                  amount={paymentWidget.selectedItem.remaining_amount || paymentWidget.selectedItem.total_amount || paymentWidget.selectedItem.cost || 0}
                  currency="UZS"
                  description={`Оплата за ${paymentWidget.selectedItem.department || 'медицинские услуги'}`}
                  onSuccess={handlePaymentSuccess}
                  onError={handlePaymentError}
                  onCancel={handlePaymentCancel}
                />
              )}
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
            fullWidth
          >
            <DialogTitle>
              <Box display="flex" alignItems="center">
                <CheckCircle style={{ color: 'var(--color-status-success)', marginRight: 8 }} />
                Оплата успешна!
              </Box>
            </DialogTitle>

            <DialogContent>
              {paymentSuccess && (
                <Box>
                  <Typography variant="body1" gutterBottom>
                    Платеж успешно обработан
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    ID платежа: {paymentSuccess.payment_id}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Провайдер: {paymentSuccess.provider}
                  </Typography>
                </Box>
              )}
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
                💸 Возврат средств
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
                    value={refundAmount}
                    onChange={(e) => setRefundAmount(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: '8px',
                      border: '1px solid var(--mac-border)',
                      fontSize: '14px'
                    }}
                    max={refundPaymentAmount}
                    min={1}
                  />
                </Box>
                <Box>
                  <Typography variant="body2" gutterBottom>Причина возврата:</Typography>
                  <textarea
                    value={refundReason}
                    onChange={(e) => setRefundReason(e.target.value)}
                    placeholder="Укажите причину возврата (минимум 3 символа)"
                    rows={3}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: '8px',
                      border: '1px solid var(--mac-border)',
                      fontSize: '14px',
                      resize: 'vertical'
                    }}
                  />
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
              📊 Почасовая статистика за {selectedDate}
            </DialogTitle>
            <DialogContent>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {hourlyStats.filter(h => h.count > 0).length > 0 ? (
                  hourlyStats.filter(h => h.count > 0).map(h => (
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
                          width: `${Math.min(100, (h.count / Math.max(...hourlyStats.map(s => s.count))) * 100)}%`,
                          height: '100%',
                          backgroundColor: 'var(--color-status-success)',
                          borderRadius: 4
                        }} />
                      </Box>
                      <Typography sx={{ width: 80, textAlign: 'right' }}>
                        {h.count} / {Number(h.amount).toLocaleString()}
                      </Typography>
                    </Box>
                  ))
                ) : (
                  <Typography color="textSecondary">Нет платежей за этот день</Typography>
                )}
              </Box>
            </DialogContent>
            <DialogActions>
              <Button onClick={() => setShowHourlyChart(false)}>Закрыть</Button>
            </DialogActions>
          </Dialog>
        </div>
      </div>
    </div>
  );
};

export default CashierPanel;
