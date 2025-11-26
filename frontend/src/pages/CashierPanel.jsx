import React, { useEffect, useState } from 'react';
import { CreditCard, Calendar, Download, Search, Filter, CheckCircle, XCircle, DollarSign, User, Stethoscope, Clock, Receipt } from 'lucide-react';
import { Card, Badge, Button, Progress, Icon } from '../components/ui/macos';
import Tooltip from '../components/ui/macos/Tooltip';
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import PaymentWidget from '../components/payment/PaymentWidget';
import MacOSTab from '../components/ui/macos/MacOSTab';
import SegmentedControl from '../components/ui/macos/SegmentedControl';
import Input from '../components/ui/macos/Input';

// ✅ УЛУЧШЕНИЕ: Универсальные хуки для устранения дублирования
import useModal from '../hooks/useModal.jsx';
import { usePayments } from '../hooks/usePayments';
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

const CashierPanel = () => {
  const { isMobile } = useBreakpoint();
  const paymentsHook = usePayments();
  const [isLoading, setIsLoading] = useState(true);
  const [query, setQuery] = useState('');
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


  // ✅ УЛУЧШЕНИЕ: Универсальные хуки вместо дублированных состояний
  const paymentModal = useModal();
  const paymentWidget = useModal();

  // Вычисляем параметры даты для запроса
  const getDateParams = () => {
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
  };

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      
      const { date_from, date_to } = getDateParams();
      const API_BASE = (import.meta?.env?.VITE_API_BASE_URL) || 'http://localhost:8000';
      
      console.log('📅 Параметры даты для запроса:', { date_from, date_to, dateMode, selectedDate, dateFrom, dateTo });
      
      // Загружаем записи ожидающие оплаты через SSOT hook
      try {
        const pendingResult = await paymentsHook.getPendingPayments({
          date_from: date_from || undefined,  // Не передаем пустые строки
          date_to: date_to || undefined,
          limit: 100
        });
        if (pendingResult.success) {
          // Данные уже включают и appointments, и visits с правильными услугами и суммами
          const appointmentsData = Array.isArray(pendingResult.data) ? pendingResult.data : [];
          console.log('📋 Загружено записей ожидающих оплаты:', appointmentsData.length);
          console.log('📋 Первая запись (пример):', appointmentsData[0]);
          setAppointments(appointmentsData);
        } else {
          console.warn('⚠️ Ошибка загрузки записей:', pendingResult.error);
          setAppointments([]);
        }
      } catch (error) {
        console.error('Ошибка загрузки записей:', error);
      }

      // Загружаем историю платежей через SSOT hook
      try {
        const paymentsResult = await paymentsHook.getPayments({
          date_from: date_from || undefined,  // Не передаем пустые строки
          date_to: date_to || undefined,
          limit: 50
        });
        if (paymentsResult.success) {
          const paymentsData = Array.isArray(paymentsResult.data) ? paymentsResult.data : [];
          console.log('💰 Загружено платежей:', paymentsData.length);
          console.log('💰 Первый платеж (пример):', paymentsData[0]);
          
          // Данные уже отформатированы на backend (SSOT)
          // Используем данные как есть, без дополнительного форматирования
          setPayments(paymentsData);
        } else {
          console.warn('⚠️ Ошибка загрузки платежей:', paymentsResult.error);
          // ✅ УЛУЧШЕНИЕ: Убраны демо данные (согласно плану - только реальные данные с backend)
          setPayments([]);
        }
      } catch (error) {
        console.error('Ошибка загрузки платежей:', error);
        // ✅ УЛУЧШЕНИЕ: Убраны демо данные (согласно плану - только реальные данные с backend)
        setPayments([]);
      }
      
      setIsLoading(false);
    };
    load();
  }, [dateMode, selectedDate, dateFrom, dateTo]);

  const format = (n) => new Intl.NumberFormat('ru-RU').format(n) + ' сум';

  // ✅ УЛУЧШЕНИЕ: Обработчики с универсальными хуками
  const handlePaymentSuccess = (paymentData) => {
    setPaymentSuccess(paymentData);
    paymentWidget.closeModal();
    
    // Обновляем список записей
    setAppointments(prev => prev.map(apt => 
      apt.id === paymentWidget.selectedItem?.id 
        ? { ...apt, status: 'paid', payment_id: paymentData.payment_id }
        : apt
    ));
    
    // Добавляем платеж в историю
    setPayments(prev => [{
      id: paymentData.payment_id,
      time: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
      patient: paymentWidget.selectedItem?.patient_name || 'Неизвестно',
      service: paymentWidget.selectedItem?.department || 'Услуга',
      amount: paymentData.amount || paymentWidget.selectedItem?.cost,
      method: paymentData.provider || 'Онлайн',
      status: 'paid'
    }, ...prev]);
  };

  const handlePaymentError = (error) => {
    setPaymentError(error);
    console.error('Ошибка платежа:', error);
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
  const processPayment = async (appointment, paymentData) => {
    try {
      const recordType = appointment.record_type || (appointment.id >= 20000 ? 'visit' : 'appointment');
      
      // Если это visit с несколькими visit_ids (группированные)
      if (recordType === 'visit' && appointment.visit_ids && appointment.visit_ids.length > 0) {
        // ✅ ИСПРАВЛЕНО: Создаем платежи для всех визитов с правильной суммой и методом
        // Затем markVisitAsPaid проверит существование платежа и обновит статус
        const paymentPromises = appointment.visit_ids.map(visitId => 
          paymentsHook.createPayment({
            visit_id: visitId,
            amount: paymentData.amount / appointment.visit_ids.length, // Распределяем сумму между визитами
            method: paymentData.method,
            note: paymentData.note || `Оплата за ${appointment.department || 'услугу'}`
          })
        );
        
        const paymentResults = await Promise.all(paymentPromises);
        const failedPayments = paymentResults.filter(r => !r.success);
        if (failedPayments.length > 0) {
          throw new Error(`Ошибка создания платежей: ${failedPayments.map(f => f.error).join(', ')}`);
        }
        
        // Отмечаем все visits как оплаченные (markVisitAsPaid проверит существование платежа)
        const markPaidPromises = appointment.visit_ids.map(visitId => 
          paymentsHook.markVisitAsPaid(visitId)
        );
        
        const results = await Promise.all(markPaidPromises);
        
        // Проверяем, что все визиты успешно отмечены
        const failed = results.filter(r => !r.success);
        if (failed.length > 0) {
          throw new Error(`Ошибка при отметке визитов как оплаченных: ${failed.map(f => f.error).join(', ')}`);
        }
        
        setAppointments(prev => prev.filter(apt => apt.id !== appointment.id));
        
        // ✅ ИСПРАВЛЕНО: Перезагружаем историю платежей после успешного создания
        const { date_from, date_to } = getDateParams();
        const paymentsResult = await paymentsHook.getPayments({
          date_from: date_from || undefined,
          date_to: date_to || undefined,
          limit: 50
        });
        if (paymentsResult.success) {
          const paymentsData = Array.isArray(paymentsResult.data) ? paymentsResult.data : [];
          setPayments(paymentsData);
          console.log('💰 История платежей перезагружена после создания платежа:', paymentsData.length);
        }
        
        paymentModal.closeModal();
        alert('Оплата успешно обработана!');
      } else {
        // Остальной код для одиночных записей...
        const recordId = recordType === 'visit' ? appointment.id - 20000 : appointment.id;
        
        // ✅ ИСПРАВЛЕНО: Для visit используем markVisitAsPaid, который сам создаст платеж
        // Для appointment создаем платеж вручную
        if (recordType === 'visit') {
          // markVisitAsPaid создаст платеж автоматически, если его еще нет
          const markPaidResult = await paymentsHook.markVisitAsPaid(recordId);
          if (!markPaidResult.success) {
            throw new Error(markPaidResult.error || 'Ошибка при обновлении статуса визита');
          }
        } else {
          // Для appointment создаем платеж вручную
          const paymentResult = await paymentsHook.createPayment({
            appointment_id: recordId,
            visit_id: null,
            amount: paymentData.amount,
            method: paymentData.method,
            note: paymentData.note || `Оплата за ${appointment.department || 'услугу'}`
          });
          
          if (!paymentResult.success) {
            throw new Error(paymentResult.error || 'Ошибка создания платежа');
          }
        }
        
        // Обновляем списки
        setAppointments(prev => prev.filter(apt => apt.id !== appointment.id));
        
        // ✅ ИСПРАВЛЕНО: Перезагружаем историю платежей после успешного создания
        const { date_from, date_to } = getDateParams();
        const paymentsResult = await paymentsHook.getPayments({
          date_from: date_from || undefined,
          date_to: date_to || undefined,
          limit: 50
        });
        if (paymentsResult.success) {
          const paymentsData = Array.isArray(paymentsResult.data) ? paymentsResult.data : [];
          setPayments(paymentsData);
          console.log('💰 История платежей перезагружена после создания платежа:', paymentsData.length);
        }
        
        paymentModal.closeModal();
        alert('Оплата успешно обработана!');
      }
    } catch (error) {
      console.error('Ошибка обработки платежа:', error);
      setPaymentError(error.message || 'Ошибка обработки платежа. Попробуйте позже.');
      // ✅ УЛУЧШЕНИЕ: Убран демо режим (согласно плану - только реальные данные с backend)
      // Показываем ошибку пользователю, не создаем локальные данные
      alert(`Ошибка обработки платежа: ${error.message || 'Попробуйте позже'}`);
    }
  };

  // ✅ ОТОБРАЖЕНИЕ УСЛУГ: Рендерим коды услуг с бейджами и tooltip (как в RegistrarPanel)
  const renderServiceBadges = (serviceCodes, serviceNames) => {
    // Если нет кодов, возвращаем пустой элемент
    if (!serviceCodes || !Array.isArray(serviceCodes) || serviceCodes.length === 0) {
      return <span style={{ color: 'var(--mac-text-tertiary)' }}>—</span>;
    }

    // Создаем tooltip с полными названиями услуг
    const tooltipContent = (
      <div style={{ padding: '4px 0', maxWidth: '300px' }}>
        {serviceNames && Array.isArray(serviceNames) && serviceNames.length === serviceCodes.length
          ? serviceNames.map((name, idx) => (
              <div key={idx} style={{
                marginBottom: idx < serviceNames.length - 1 ? '6px' : '0',
                lineHeight: '1.4',
                fontSize: '12px'
              }}>
                {name}
              </div>
            ))
          : serviceCodes.map((code, idx) => (
              <div key={idx} style={{
                marginBottom: idx < serviceCodes.length - 1 ? '6px' : '0',
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
          {serviceCodes.map((code, idx) => (
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
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
              }}
            >
              {code}
            </span>
          ))}
        </div>
      </Tooltip>
    );
  };

  // ✅ ГРУППИРОВКА: Объединяем платежи одного пациента, созданных в одно время
  const groupPaymentsByPatientAndTime = (paymentsList) => {
    const grouped = {};

    paymentsList.forEach(payment => {
      // Ключ: пациент + дата + время (с точностью до минуты)
      const dateKey = payment.date || '—';
      const timeKey = payment.time || '00:00';
      const groupKey = `${payment.patient}_${dateKey}_${timeKey}`;

      if (!grouped[groupKey]) {
        // Создаём новую группу
        grouped[groupKey] = {
          ...payment,
          services: payment.services || [payment.service],
          services_names: payment.services_names || [payment.service],
          grouped_payments: [payment.id],
          total_amount: payment.amount
        };
      } else {
        // Добавляем к существующей группе
        if (payment.services && payment.services.length > 0) {
          grouped[groupKey].services.push(...payment.services);
          if (payment.services_names) {
            grouped[groupKey].services_names.push(...payment.services_names);
          }
        } else {
          grouped[groupKey].services.push(payment.service);
          grouped[groupKey].services_names.push(payment.service);
        }
        grouped[groupKey].grouped_payments.push(payment.id);
        grouped[groupKey].total_amount += payment.amount;
      }
    });

    // ✅ Удаляем дубликаты услуг и обновляем строки
    Object.values(grouped).forEach(group => {
      // Создаём уникальные массивы кодов и названий
      const uniqueServices = [...new Set(group.services)];
      const uniqueServicesMap = new Map();

      // Создаём мапу код → название (берём первое попавшееся название для каждого кода)
      group.services.forEach((code, idx) => {
        if (!uniqueServicesMap.has(code) && group.services_names && group.services_names[idx]) {
          uniqueServicesMap.set(code, group.services_names[idx]);
        }
      });

      group.services = uniqueServices;
      group.services_names = uniqueServices.map(code => uniqueServicesMap.get(code) || code);
      group.service = uniqueServices.join(', ');
      group.amount = group.total_amount;
    });

    return Object.values(grouped);
  };

  // Сначала фильтруем, затем группируем
  const filteredBeforeGrouping = payments.filter(p => {
    const matchesText = [p.patient, p.service, p.method].join(' ').toLowerCase().includes(query.toLowerCase());
    const matchesStatus = status === 'all' || p.status === status;
    return matchesText && matchesStatus;
  });

  // Группируем платежи
  const filtered = groupPaymentsByPatientAndTime(filteredBeforeGrouping);

  console.log('💰 Отфильтровано платежей (UI фильтр):', filteredBeforeGrouping.length, 'из', payments.length);
  console.log('💰 После группировки:', filtered.length, 'строк');

  // ✅ УЛУЧШЕНИЕ: Убрана клиентская фильтрация по датам (данные уже отфильтрованы на backend согласно SSOT)
  // Фильтрация только по текстовому запросу и статусу (UI логика)
  const filteredAppointments = appointments.filter(apt => {
    // Только UI фильтрация (текст, статус) - бизнес-логика фильтрации дат на backend
    if (query) {
      const searchText = [apt.patient_name, apt.patient_last_name, apt.patient_first_name, apt.department]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      if (!searchText.includes(query.toLowerCase())) {
        return false;
      }
    }
    return true;
  });
  
  console.log('🔍 Отфильтровано записей (UI фильтр):', filteredAppointments.length, 'из', appointments.length);
  console.log('🔍 filteredAppointments[0]:', filteredAppointments[0]);
  console.log('🔍 isLoading:', isLoading, 'activeTab:', activeTab);

  return (
    <div style={{ 
      padding: '0',
      minHeight: '100vh',
      background: 'var(--mac-gradient-window)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
      color: 'var(--mac-text-primary)',
      transition: 'background var(--mac-duration-normal) var(--mac-ease)'
    }}>

      <div style={{ padding: '0px' }}> {/* Убираем padding, так как он уже есть в main контейнере */}
        <div className="max-w-7xl mx-auto space-y-6">
          {/* Старый header удален - теперь используется macOS Header */}

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
                onChange={(e)=>setQuery(e.target.value)}
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
                placeholder="Поиск по пациенту, услуге, способу оплаты"
              />
            </div>

            {/* Статус */}
            <select
              value={status}
              onChange={(e)=>setStatus(e.target.value)}
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
                <Button 
                  size="sm" 
                  variant="outline"
                  onClick={() => {
                    const yesterday = new Date();
                    yesterday.setDate(yesterday.getDate() - 1);
                    setSelectedDate(getLocalDateString(yesterday));
                  }}
                >
                  Вчера
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
                <Button 
                  size="sm" 
                  variant="outline"
                  onClick={() => {
                    const today = new Date();
                    const weekAgo = new Date();
                    weekAgo.setDate(weekAgo.getDate() - 7);
                    setDateFrom(getLocalDateString(weekAgo));
                    setDateTo(getLocalDateString(today));
                  }}
                >
                  Неделя
                </Button>
                <Button 
                  size="sm" 
                  variant="outline"
                  onClick={() => {
                    const today = new Date();
                    const monthAgo = new Date();
                    monthAgo.setMonth(monthAgo.getMonth() - 1);
                    setDateFrom(getLocalDateString(monthAgo));
                    setDateTo(getLocalDateString(today));
                  }}
                >
                  Месяц
                </Button>
              </>
            )}
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
                badge: filteredAppointments.length > 0 ? filteredAppointments.length : undefined
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
              ) : filteredAppointments.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {filteredAppointments.map((appointment, index) => (
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
                        {/* Первый ряд: Фамилия - Имя, затем Дата-Время */}
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
                        
                        {/* Второй ряд: Коды услуг с tooltip и сумма оплаты */}
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
                          {appointment.payment_amount && (
                            <div style={{ 
                              fontSize: '12px', 
                              color: 'var(--mac-text-tertiary)',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px'
                            }}>
                              <Receipt style={{ width: '12px', height: '12px', color: 'var(--mac-text-tertiary)' }} />
                              {format(appointment.payment_amount || 0)}
                            </div>
                          )}
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
                            <CreditCard style={{ width: '16px', height: '16px', marginRight: '4px' }} />
                            Онлайн
                          </Button>
                          <Button 
                            size="sm" 
                            onClick={() => {
                              paymentModal.openModal(appointment);
                            }}
                          >
                            <DollarSign style={{ width: '16px', height: '16px', marginRight: '4px' }} />
                            Касса
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
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
                        <th style={{
                          textAlign: 'left',
                          padding: '12px 16px',
                          color: 'var(--mac-text-primary)',
                          fontWeight: '500',
                          fontSize: '14px'
                        }}>Дата/Время</th>
                        <th style={{ 
                          textAlign: 'left', 
                          padding: '12px 16px', 
                          color: 'var(--mac-text-primary)', 
                          fontWeight: '500',
                          fontSize: '14px'
                        }}>Пациент</th>
                        <th style={{ 
                          textAlign: 'left', 
                          padding: '12px 16px', 
                          color: 'var(--mac-text-primary)', 
                          fontWeight: '500',
                          fontSize: '14px'
                        }}>Услуга</th>
                        <th style={{ 
                          textAlign: 'left', 
                          padding: '12px 16px', 
                          color: 'var(--mac-text-primary)', 
                          fontWeight: '500',
                          fontSize: '14px'
                        }}>Способ</th>
                        <th style={{ 
                          textAlign: 'left', 
                          padding: '12px 16px', 
                          color: 'var(--mac-text-primary)', 
                          fontWeight: '500',
                          fontSize: '14px'
                        }}>Сумма</th>
                        <th style={{ 
                          textAlign: 'left', 
                          padding: '12px 16px', 
                          color: 'var(--mac-text-primary)', 
                          fontWeight: '500',
                          fontSize: '14px'
                        }}>Статус</th>
                        <th style={{ 
                          textAlign: 'left', 
                          padding: '12px 16px', 
                          color: 'var(--mac-text-primary)', 
                          fontWeight: '500',
                          fontSize: '14px'
                        }}>Действия</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.length > 0 ? (
                        filtered.map((row, index) => (
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
                              {renderServiceBadges(row.services, row.services_names)}
                            </td>
                            <td style={{ padding: '12px 16px', color: 'var(--mac-text-primary)', fontSize: '14px' }}>
                              {row.method}
                            </td>
                            <td style={{ padding: '12px 16px', color: 'var(--mac-text-primary)', fontSize: '14px', fontWeight: '500' }}>
                              {format(row.amount)}
                            </td>
                            <td style={{ padding: '12px 16px' }}>
                              <Badge variant={row.status === 'paid' ? 'success' : 'warning'}>
                                {row.status === 'paid' ? 'Оплачено' : 'Ожидает'}
                              </Badge>
                            </td>
                            <td style={{ padding: '12px 16px', display: 'flex', gap: '8px' }}>
                              <Button size="sm" variant="success">
                                <CheckCircle style={{ width: '16px', height: '16px', marginRight: '4px' }}/>
                                Принять
                              </Button>
                              <Button size="sm" variant="danger">
                                <XCircle style={{ width: '16px', height: '16px', marginRight: '4px' }}/>
                                Отмена
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
                </div>
              )}
            </div>
          )}
        </Card>

        {/* ✅ УЛУЧШЕНИЕ: Модальное окно оплаты с универсальным хуком */}
        {paymentModal.isOpen && paymentModal.selectedItem && (
          <PaymentModal
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
                visitId={paymentWidget.selectedItem.id}
                amount={paymentWidget.selectedItem.cost || 100000}
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
      </div>
      </div>
    </div>
  );
};

export default CashierPanel;

// Компонент модального окна оплаты
const PaymentModal = ({ appointment, onProcessPayment, onClose }) => {
  const [paymentData, setPaymentData] = useState({
    amount: '',
    method: 'cash',
    note: ''
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!paymentData.amount || paymentData.amount <= 0) {
      alert('Введите корректную сумму');
      return;
    }
    onProcessPayment(appointment, paymentData);
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999
    }}>
      <div style={{
        backgroundColor: 'var(--mac-bg-secondary)',
        borderRadius: 'var(--mac-radius-md)',
        padding: '24px',
        width: '100%',
        maxWidth: '400px',
        margin: '16px',
        border: '1px solid var(--mac-border)',
        boxShadow: 'var(--mac-shadow-lg)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--mac-text-primary)' }}>Обработка оплаты</h3>
          <button onClick={onClose} style={{ color: 'var(--mac-text-secondary)', cursor: 'pointer', border: 'none', background: 'none' }}>
            <XCircle className="w-6 h-6" />
          </button>
        </div>
        
        <div style={{ marginBottom: '16px' }}>
          <p style={{ fontSize: '14px', color: 'var(--mac-text-secondary)', marginBottom: '8px' }}>Пациент:</p>
          <p style={{ fontSize: '16px', fontWeight: '500', color: 'var(--mac-text-primary)' }}>
            {appointment?.patient_name || `Пациент #${appointment?.patient_id}`}
          </p>
          <p style={{ fontSize: '14px', color: 'var(--mac-text-secondary)' }}>
            {appointment?.department} • {appointment?.appointment_date} {appointment?.appointment_time}
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: 'var(--mac-text-primary)', marginBottom: '4px' }}>
              Сумма (сум)
            </label>
            <input
              type="number"
              value={paymentData.amount}
              onChange={(e) => setPaymentData(prev => ({ ...prev, amount: e.target.value }))}
              style={{
                width: '100%',
                padding: '8px 12px',
                border: '1px solid var(--mac-border)',
                borderRadius: 'var(--mac-radius-sm)',
                fontSize: '16px',
                backgroundColor: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)'
              }}
              placeholder="Введите сумму"
              required
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: 'var(--mac-text-primary)', marginBottom: '4px' }}>
              Способ оплаты
            </label>
            <select
              value={paymentData.method}
              onChange={(e) => setPaymentData(prev => ({ ...prev, method: e.target.value }))}
              style={{
                width: '100%',
                padding: '8px 12px',
                border: '1px solid var(--mac-border)',
                borderRadius: 'var(--mac-radius-sm)',
                fontSize: '16px',
                backgroundColor: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)'
              }}
            >
              <option value="cash">Наличные</option>
              <option value="card">Карта</option>
            </select>
          </div>

          <div style={{ marginBottom: '24px' }}>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: 'var(--mac-text-primary)', marginBottom: '4px' }}>
              Примечание (необязательно)
            </label>
            <textarea
              value={paymentData.note}
              onChange={(e) => setPaymentData(prev => ({ ...prev, note: e.target.value }))}
              style={{
                width: '100%',
                padding: '8px 12px',
                border: '1px solid var(--mac-border)',
                borderRadius: 'var(--mac-radius-sm)',
                fontSize: '16px',
                minHeight: '80px',
                resize: 'vertical',
                backgroundColor: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)'
              }}
              placeholder="Дополнительная информация"
            />
          </div>

          <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
            <Button type="submit" variant="primary">
              <CheckCircle className="w-4 h-4 mr-2" />
              Обработать оплату
            </Button>
            <Button type="button" variant="outline" onClick={onClose}>
              Отмена
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

