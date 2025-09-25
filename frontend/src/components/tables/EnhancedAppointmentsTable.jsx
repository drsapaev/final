import React, { useState, useMemo, useCallback } from 'react';
import { 
  Search, 
  Filter, 
  Download, 
  ChevronUp, 
  ChevronDown, 
  Calendar, 
  Clock, 
  User, 
  Phone, 
  CreditCard,
  FileText,
  MoreHorizontal,
  Eye,
  Edit,
  Trash2,
  CheckCircle,
  XCircle,
  AlertCircle
} from 'lucide-react';
import './EnhancedAppointmentsTable.css';

const EnhancedAppointmentsTable = ({ 
  data = [], 
  loading = false, 
  onRowClick, 
  onActionClick,
  theme = 'light',
  language = 'ru',
  selectedRows: externalSelectedRows,
  onRowSelect,
  services = {},
  outerBorder = true
}) => {
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [filterConfig, setFilterConfig] = useState({
    search: '',
    status: '',
    dateFrom: '',
    dateTo: '',
    doctor: '',
    department: ''
  });
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  // Используем внешнее состояние, если передано, иначе внутреннее
  const [internalSelectedRows, setInternalSelectedRows] = useState(new Set());
  const selectedRows = externalSelectedRows || internalSelectedRows;

  const isDark = theme === 'dark';
  
  // Цвета для темы
  const colors = {
    bg: isDark ? '#1f2937' : '#ffffff',
    bgSecondary: isDark ? '#374151' : '#f9fafb',
    border: isDark ? '#4b5563' : '#e5e7eb',
    text: isDark ? '#f9fafb' : '#111827',
    textSecondary: isDark ? '#d1d5db' : '#6b7280',
    accent: '#3b82f6',
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444'
  };

  // Переводы
  const t = {
    ru: {
      search: 'Поиск',
      filter: 'Фильтр',
      export: 'Экспорт',
      selectAll: 'Выбрать все',
      selected: 'Выбрано',
      actions: 'Действия',
      noData: 'Нет данных',
      loading: 'Загрузка...',
      page: 'Страница',
      of: 'из',
      rows: 'строк',
      // Колонки
      number: '№',
      patient: 'Пациент',
      phone: 'Телефон',
      birthYear: 'Г.р.',
      address: 'Адрес',
      visitType: 'Тип',
      services: 'Услуги',
      paymentType: 'Оплата',
      doctor: 'Врач',
      date: 'Дата',
      time: 'Время',
      status: 'Статус',
      confirmation: 'Подтверждение',
      cost: 'Стоимость',
      payment: 'Оплата',
      // Типы обращения
      paid: 'Платный',
      repeat: 'Повторный',
      free: 'Льготный',
      // Виды оплаты
      cash: 'Наличные',
      card: 'Карта',
      online: 'Онлайн',
      // Статусы
      scheduled: 'Запланирован',
      confirmed: 'Подтвержден',
      queued: 'В очереди',
      in_cabinet: 'В кабинете',
      done: 'Завершен',
      cancelled: 'Отменен',
      no_show: 'Неявка',
      paid_pending: 'Ожидает оплаты',
      payment_paid: 'Оплачен'
    }
  }[language] || {};

  // Сортировка данных
  const sortedData = useMemo(() => {
    if (!sortConfig.key) return data;
    
    return [...data].sort((a, b) => {
      let aVal = a[sortConfig.key];
      let bVal = b[sortConfig.key];
      
      // Специальная обработка для стоимости
      if (sortConfig.key === 'cost') {
        aVal = a.cost || a.payment_amount || 0;
        bVal = b.cost || b.payment_amount || 0;
      }
      
      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortConfig]);

  // Фильтрация данных
  const filteredData = useMemo(() => {
    return sortedData.filter(row => {
      const searchMatch = !filterConfig.search || 
        Object.values(row).some(val => 
          String(val).toLowerCase().includes(filterConfig.search.toLowerCase())
        );
      
      const statusMatch = !filterConfig.status || row.status === filterConfig.status;
      const doctorMatch = !filterConfig.doctor || row.doctor_id === parseInt(filterConfig.doctor);
      const departmentMatch = !filterConfig.department || row.department === filterConfig.department;
      
      return searchMatch && statusMatch && doctorMatch && departmentMatch;
    });
  }, [sortedData, filterConfig]);

  // Пагинация
  const paginatedData = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredData.slice(start, start + pageSize);
  }, [filteredData, currentPage, pageSize]);

  const totalPages = Math.ceil(filteredData.length / pageSize);

  // Обработчик сортировки
  const handleSort = useCallback((key) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  }, []);

  // Обработчик выбора строк
  const handleRowSelect = useCallback((id, checked) => {
    if (onRowSelect) {
      // Используем внешний обработчик
      onRowSelect(id, checked);
    } else {
      // Используем внутреннее состояние
      setInternalSelectedRows(prev => {
      const newSet = new Set(prev);
      if (checked) {
        newSet.add(id);
      } else {
        newSet.delete(id);
      }
      return newSet;
    });
    }
  }, [onRowSelect]);

  // Обработчик выбора всех строк
  const handleSelectAll = useCallback((checked) => {
    if (onRowSelect) {
      // Используем внешний обработчик для каждой строки
      paginatedData.forEach(row => {
        onRowSelect(row.id, checked);
      });
    } else {
      // Используем внутреннее состояние
    if (checked) {
        setInternalSelectedRows(new Set(paginatedData.map(row => row.id)));
    } else {
        setInternalSelectedRows(new Set());
    }
    }
  }, [paginatedData, onRowSelect]);

  // Рендер статуса (компактный)
  const renderStatus = useCallback((status) => {
    const statusConfig = {
      scheduled: { color: colors.accent, bg: `${colors.accent}20`, icon: Calendar, short: 'План' },
      confirmed: { color: colors.success, bg: `${colors.success}20`, icon: CheckCircle, short: 'Подтв' },
      queued: { color: colors.warning, bg: `${colors.warning}20`, icon: Clock, short: 'Очер' },
      in_cabinet: { color: colors.accent, bg: `${colors.accent}20`, icon: User, short: 'Каб' },
      done: { color: colors.success, bg: `${colors.success}20`, icon: CheckCircle, short: 'Готов' },
      cancelled: { color: colors.error, bg: `${colors.error}20`, icon: XCircle, short: 'Отмен' },
      no_show: { color: colors.textSecondary, bg: `${colors.textSecondary}20`, icon: AlertCircle, short: 'Неявка' },
      paid_pending: { color: colors.warning, bg: `${colors.warning}20`, icon: CreditCard, short: 'Ожид' },
      payment_paid: { color: colors.success, bg: `${colors.success}20`, icon: CheckCircle, short: 'Оплач' },
      paid: { color: colors.success, bg: `${colors.success}20`, icon: CheckCircle, short: 'Оплач' },
      plan: { color: colors.accent, bg: `${colors.accent}20`, icon: Calendar, short: 'План' }
    };

    const config = statusConfig[status] || statusConfig.scheduled;
    const Icon = config.icon;

    return (
      <div 
        className="status-badge"
        title={t[status] || status} // Полное название в подсказке
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '2px',
          padding: '2px 6px',
          borderRadius: '4px',
          backgroundColor: config.bg,
          color: config.color,
          fontSize: '10px',
          fontWeight: '500',
          cursor: 'help'
        }}>
        <Icon size={10} />
        {config.short}
      </div>
    );
  }, [colors, t]);

  // ✅ УНИВЕРСАЛЬНЫЙ МАППИНГ УСЛУГ (работает с любыми данными из админ панели)
  const createServiceMapping = useCallback(() => {
    const mapping = {};
    const categoryMapping = {};
    
    // Преобразуем структуру services в плоские маппинги
    Object.entries(services).forEach(([category, group]) => {
      if (Array.isArray(group)) {
        group.forEach(service => {
          if (service.id && service.name) {
            const id = String(service.id);
            mapping[id] = service.name;
            categoryMapping[id] = category;
            
            // Дополнительные алиасы для совместимости
            if (service.service_id) {
              mapping[String(service.service_id)] = service.name;
              categoryMapping[String(service.service_id)] = category;
            }
          }
        });
      }
    });
    
    return { mapping, categoryMapping };
  }, [services]);

  // Рендер услуг с динамическим маппингом
  const renderServices = useCallback((appointmentServices) => {
    if (!appointmentServices) return '—';
    
    const { mapping: serviceMapping, categoryMapping } = createServiceMapping();
    
    // Поддерживаем как массив строк, так и массив объектов
    let servicesList = [];
    if (Array.isArray(appointmentServices)) {
      servicesList = appointmentServices.map(service => {
        // Обрабатываем строки-числа (ID услуг)
        if (typeof service === 'string' && /^\d+$/.test(service)) {
          return serviceMapping[service] || `Услуга ${service}`;
        }
        // Если это просто число
        if (typeof service === 'number') {
          return serviceMapping[service] || serviceMapping[String(service)] || `Услуга ${service}`;
        }
        // Потом обычные строки
        if (typeof service === 'string') return service;
        if (typeof service === 'object' && service.name) return service.name;
        if (typeof service === 'object' && service.code) {
          // Сначала пытаемся найти по коду в маппинге
          const foundByCode = Object.values(services).flat().find(s => s.code === service.code);
          if (foundByCode) return foundByCode.name;
          
          // Fallback названия по кодам
          const codeToName = {
            'consultation.cardiology': 'Консультация кардиолога',
            'echo.cardiography': 'ЭхоКГ',
            'ecg': 'ЭКГ',
            'consultation.dermatology': 'Консультация дерматолога',
            'derm.skin_diagnostics': 'Дерматоскопия',
            'cosmetology.botox': 'Ботулотоксин',
            'cosmetology.mesotherapy': 'Мезотерапия',
            'cosmetology.peel': 'Пилинг',
            'cosmetology.laser': 'Лазерные процедуры',
            'consultation.dentistry': 'Консультация стоматолога',
            'lab.cbc': 'ОАК',
            'lab.biochem': 'Биохимия',
            'lab.urine': 'ОАМ',
            'lab.coag': 'Коагулограмма',
            'lab.hormones': 'Гормоны',
            'lab.infection': 'Инфекции',
            'other.general': 'Прочее'
          };
          
          return codeToName[service.code] || service.code || service;
        }
        return String(service);
      });
    } else if (typeof appointmentServices === 'string') {
      servicesList = [appointmentServices];
    } else {
      return String(appointmentServices);
    }
    
    if (servicesList.length === 0) return '—';
    
    // ✅ ИСПОЛЬЗУЕМ НОВЫЕ КОДЫ ИЗ БАЗЫ ДАННЫХ
    const compactCodes = servicesList.map((serviceName, index) => {
      // Сначала проверяем, может это уже код (K01, D02, etc)
      if (/^[A-Z]\d{2}$/.test(serviceName)) {
        return serviceName;
      }
      
      // Найти услугу по названию и получить её код
      for (const group of Object.values(services)) {
        if (Array.isArray(group)) {
          const foundService = group.find(s => s.name === serviceName);
          if (foundService) {
            // Используем service_code если есть, иначе генерируем из category_code
            if (foundService.service_code) {
              return foundService.service_code;
            }
            // Если есть category_code но нет service_code, генерируем временный код
            if (foundService.category_code) {
              return `${foundService.category_code}${String(foundService.id).padStart(2, '0')}`;
            }
          }
        }
      }
      
      // Если ничего не найдено, возвращаем пустую строку для скрытия
      return '';
    }).filter(code => code); // Убираем пустые коды
    
    // Создаем tooltip в виде списка для лучшей читаемости
    const tooltipText = servicesList.length > 1 
      ? `Услуги:\n${servicesList.map((service, idx) => `${idx + 1}. ${service}`).join('\n')}`
      : servicesList[0] || '';
    
    return (
      <div 
        style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', cursor: 'help' }}
        title={tooltipText}
      >
        {compactCodes.map((code, idx) => (
          <span
            key={idx}
            style={{
              padding: '2px 6px',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 'bold',
              backgroundColor: colors.accent + '20',
              color: colors.accent,
              border: `1px solid ${colors.accent}40`
            }}
          >
            {code}
          </span>
        ))}
      </div>
    );
  }, [colors, createServiceMapping, services]);

  // Рендер типа обращения
  const renderVisitType = useCallback((visitType) => {
    const typeColors = {
      paid: colors.accent,
      repeat: colors.success,
      free: colors.warning
    };

    const typeText = t[visitType] || visitType;
    const color = typeColors[visitType] || colors.textSecondary;

    return (
      <span style={{
        padding: '3px 6px',
        borderRadius: '8px',
        fontSize: '11px',
        fontWeight: '600',
        backgroundColor: `${color}15`,
        color: color,
        border: `1px solid ${color}30`
      }}>
        {typeText}
      </span>
    );
  }, [colors, t]);

  // Рендер вида оплаты
  const renderPaymentType = useCallback((paymentType, paymentStatus) => {
    const paymentIcons = {
      cash: '💵',
      card: '💳',
      online: '🌐'
    };

    const paymentColors = {
      cash: colors.success,
      card: colors.accent,
      online: '#8b5cf6'
    };

    const statusColors = {
      paid: colors.success,
      pending: colors.warning,
      failed: colors.error
    };

    const typeText = t[paymentType] || paymentType;
    const icon = paymentIcons[paymentType] || '💰';
    const color = paymentColors[paymentType] || colors.textSecondary;
    const statusColor = statusColors[paymentStatus] || colors.textSecondary;

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        <span style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          padding: '2px 6px',
          borderRadius: '6px',
          fontSize: '11px',
          fontWeight: '500',
          backgroundColor: `${color}15`,
          color: color,
          border: `1px solid ${color}30`
        }}>
          <span>{icon}</span>
          {typeText}
        </span>
        {paymentStatus && (
          <span style={{
            fontSize: '10px',
            color: statusColor,
            fontWeight: '500'
          }}>
            {paymentStatus === 'paid' ? '✅ Оплачено' : 
             paymentStatus === 'pending' ? '⏳ Ожидает' : 
             paymentStatus === 'failed' ? '❌ Ошибка' : paymentStatus}
          </span>
        )}
      </div>
    );
  }, [colors, t]);

  // Экспорт данных
  const handleExport = useCallback(() => {
    // Функция для преобразования услуг в строку для CSV
    const formatServicesForCsv = (services) => {
      if (!services) return '';
      
      let servicesList = [];
      if (Array.isArray(services)) {
        servicesList = services.map(service => {
          if (typeof service === 'string') return service;
          if (typeof service === 'object' && service.name) return service.name;
          if (typeof service === 'object' && service.code) {
            const codeToName = {
              'consultation.cardiology': 'Консультация кардиолога',
              'echo.cardiography': 'ЭхоКГ',
              'ecg': 'ЭКГ',
              'consultation.dermatology': 'Консультация дерматолога',
              'derm.skin_diagnostics': 'Дерматоскопия',
              'cosmetology.botox': 'Ботулотоксин',
              'cosmetology.mesotherapy': 'Мезотерапия',
              'cosmetology.peel': 'Пилинг',
              'cosmetology.laser': 'Лазерные процедуры',
              'consultation.dentistry': 'Консультация стоматолога',
              'lab.cbc': 'ОАК',
              'lab.biochem': 'Биохимия',
              'lab.urine': 'ОАМ',
              'lab.coag': 'Коагулограмма',
              'lab.hormones': 'Гормоны',
              'lab.infection': 'Инфекции',
              'other.general': 'Прочее'
            };
            
            const idToName = {
              '1': 'Консультация кардиолога', '2': 'ЭхоКГ', '3': 'ЭКГ',
              '4': 'Консультация дерматолога', '5': 'Дерматоскопия',
              '6': 'Ботулотоксин', '7': 'Мезотерапия', '8': 'Пилинг',
              '9': 'Лазерные процедуры', '10': 'Консультация стоматолога',
              '11': 'ОАК', '12': 'Биохимия', '13': 'ОАМ',
              '14': 'Коагулограмма', '15': 'Гормоны', '16': 'Инфекции',
              '17': 'Прочее', '29': 'Процедура 29', '30': 'Процедура 30'
            };
            
            return codeToName[service.code] || idToName[service.code] || idToName[service] || service.code || service;
          }
          return String(service);
        });
      } else if (typeof services === 'string') {
        servicesList = [services];
      } else {
        return String(services);
      }
      
      return servicesList.join('; ');
    };

    const csvContent = [
      // Заголовки
      [t.number, t.patient, t.phone, t.birthYear, t.address, t.visitType, t.services, t.paymentType, t.date, t.time, t.status, t.confirmation, t.cost].join(','),
      // Данные
      ...filteredData.map((row, index) => [
        // Номера очередей для CSV
        row.queue_numbers && row.queue_numbers.length > 0 
          ? row.queue_numbers.map(q => `${q.queue_name}: №${q.number}`).join('; ')
          : index + 1,
        row.patient_fio || '',
        row.patient_phone || '',
        row.patient_birth_year || '',
        row.address || '',
        (() => {
          const discountMode = row.discount_mode;
          if (discountMode === 'benefit') return t.free;
          if (discountMode === 'repeat') return t.repeat;
          if (discountMode === 'all_free') return t.free;
          return t.paid;
        })(),
        formatServicesForCsv(row.services),
        t[row.payment_type] || row.payment_type || '',
        row.created_at ? new Date(row.created_at).toLocaleDateString('ru-RU') : (row.appointment_date || ''),
        row.created_at ? new Date(row.created_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : (row.appointment_time || ''),
        t[row.status] || row.status || '',
        row.confirmation_status === 'confirmed' ? 'Подтвержден' : 
        row.confirmation_status === 'pending' ? 'Ожидает' : 
        row.confirmation_status === 'expired' ? 'Истек' : '—',
        row.total_amount || row.cost || row.payment_amount || ''
      ].join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `appointments_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
  }, [filteredData, t]);

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '60px',
        color: colors.textSecondary
      }}>
        <div style={{ textAlign: 'center' }}>
          <div 
            className="loading-spinner"
            style={{
              width: '40px',
              height: '40px',
              border: `3px solid ${colors.border}`,
              borderTop: `3px solid ${colors.accent}`,
              borderRadius: '50%',
              margin: '0 auto 16px'
            }} />
          {t.loading}
        </div>
      </div>
    );
  }

  // Функция для отображения номеров очередей
  const renderQueueNumbers = useCallback((row) => {
    // Если есть номера очередей из нового API
    if (row.queue_numbers && Array.isArray(row.queue_numbers) && row.queue_numbers.length > 0) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
          {row.queue_numbers.map((queue, index) => {
            // Определяем цвета и иконки для статусов
            const statusConfig = {
              waiting: { 
                bg: colors.warning, 
                icon: '⏳', 
                text: 'Ожидает',
                pulse: true 
              },
              called: { 
                bg: colors.accent, 
                icon: '📢', 
                text: 'Вызван',
                pulse: true 
              },
              served: { 
                bg: colors.success, 
                icon: '✅', 
                text: 'Обслужен',
                pulse: false 
              },
              no_show: { 
                bg: colors.error, 
                icon: '❌', 
                text: 'Не явился',
                pulse: false 
              }
            };
            
            const config = statusConfig[queue.status] || statusConfig.waiting;
            
            return (
              <div 
                key={index} 
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '4px',
                  padding: '2px',
                  borderRadius: '6px',
                  backgroundColor: config.bg + '10',
                  border: `1px solid ${config.bg}30`
                }}
                title={`${queue.queue_name}: №${queue.number} (${config.text})`}
              >
                <span style={{
                  padding: '3px 6px',
                  backgroundColor: config.bg,
                  color: 'white',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontWeight: '700',
                  minWidth: '24px',
                  textAlign: 'center',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  animation: config.pulse ? 'pulse 2s infinite' : 'none'
                }}>
                  {queue.number}
                </span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
                  <span style={{
                    fontSize: '10px',
                    color: config.bg,
                    fontWeight: '600',
                    maxWidth: '70px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}>
                    {queue.queue_name}
                  </span>
                  <span style={{
                    fontSize: '9px',
                    color: colors.textSecondary,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '2px'
                  }}>
                    <span>{config.icon}</span>
                    <span>{config.text}</span>
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      );
    }
    
    // Fallback для старых записей - показываем порядковый номер
    const fallbackIndex = data.findIndex(item => item.id === row.id) + 1;
    return (
      <span style={{ 
        color: colors.textSecondary, 
        fontSize: '12px',
        padding: '2px 6px',
        backgroundColor: colors.textSecondary + '10',
        borderRadius: '4px'
      }}>
        #{fallbackIndex}
      </span>
    );
  }, [data, colors]);

  // Функция для отображения статуса подтверждения
  const renderConfirmationStatus = useCallback((row) => {
    const confirmationStatus = row.confirmation_status;
    
    if (!confirmationStatus || confirmationStatus === 'none') {
      return (
        <span style={{
          padding: '2px 6px',
          backgroundColor: colors.textSecondary + '20',
          color: colors.textSecondary,
          borderRadius: '4px',
          fontSize: '11px',
          fontWeight: '500'
        }}>
          —
        </span>
      );
    }
    
    const statusConfig = {
      pending: { 
        color: colors.warning, 
        bg: colors.warning + '20', 
        text: 'Ожидает',
        icon: '⏳'
      },
      confirmed: { 
        color: colors.success, 
        bg: colors.success + '20', 
        text: 'Подтвержден',
        icon: '✅'
      },
      expired: { 
        color: colors.error, 
        bg: colors.error + '20', 
        text: 'Истек',
        icon: '❌'
      }
    };
    
    const config = statusConfig[confirmationStatus] || statusConfig.pending;
    
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        <span style={{
          padding: '2px 6px',
          backgroundColor: config.bg,
          color: config.color,
          borderRadius: '4px',
          fontSize: '11px',
          fontWeight: '600',
          display: 'flex',
          alignItems: 'center',
          gap: '2px'
        }}>
          <span>{config.icon}</span>
          <span>{config.text}</span>
        </span>
        {row.confirmed_at && (
          <span style={{
            fontSize: '10px',
            color: colors.textSecondary
          }}>
            {new Date(row.confirmed_at).toLocaleTimeString('ru-RU', { 
              hour: '2-digit', 
              minute: '2-digit' 
            })}
          </span>
        )}
      </div>
    );
  }, [colors]);

  return (
    <div 
      className={`enhanced-table ${isDark ? 'dark-theme' : ''}`}
      style={{
        backgroundColor: colors.bg,
        overflow: 'hidden',
        border: outerBorder ? `1px solid ${colors.border}` : 'none',
        borderRadius: outerBorder ? '12px' : '0'
      }}>
      {/* Панель инструментов */}
      <div style={{
        padding: '16px',
        borderBottom: `1px solid ${colors.border}`,
        backgroundColor: colors.bgSecondary
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          flexWrap: 'wrap'
        }}>
          {/* Поиск */}
          <div style={{ position: 'relative', minWidth: '200px', flex: 1 }}>
            <Search 
              size={16} 
              style={{
                position: 'absolute',
                left: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: colors.textSecondary
              }}
            />
            <input
              type="text"
              placeholder={t.search}
              value={filterConfig.search}
              onChange={(e) => setFilterConfig(prev => ({ ...prev, search: e.target.value }))}
              style={{
                width: '100%',
                padding: '8px 12px 8px 36px',
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
                backgroundColor: colors.bg,
                color: colors.text,
                fontSize: '14px'
              }}
            />
          </div>

          {/* Фильтр по статусу */}
          <select
            value={filterConfig.status}
            onChange={(e) => setFilterConfig(prev => ({ ...prev, status: e.target.value }))}
            style={{
              padding: '8px 12px',
              border: `1px solid ${colors.border}`,
              borderRadius: '6px',
              backgroundColor: colors.bg,
              color: colors.text,
              fontSize: '14px'
            }}
          >
            <option value="">{t.filter}</option>
            <option value="scheduled">{t.scheduled}</option>
            <option value="confirmed">{t.confirmed}</option>
            <option value="queued">{t.queued}</option>
            <option value="in_cabinet">{t.in_cabinet}</option>
            <option value="done">{t.done}</option>
            <option value="cancelled">{t.cancelled}</option>
            <option value="paid_pending">{t.paid_pending}</option>
            <option value="paid">{t.paid}</option>
          </select>

          {/* Экспорт */}
          <button
            onClick={handleExport}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 12px',
              border: `1px solid ${colors.border}`,
              borderRadius: '6px',
              backgroundColor: colors.bg,
              color: colors.text,
              fontSize: '14px',
              cursor: 'pointer'
            }}
          >
            <Download size={16} />
            {t.export}
          </button>

          {/* Информация о выбранных */}
          {selectedRows.size > 0 && (
            <div style={{
              padding: '8px 12px',
              backgroundColor: colors.accent + '20',
              color: colors.accent,
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: '500'
            }}>
              {t.selected}: {selectedRows.size}
            </div>
          )}
        </div>
      </div>

      {/* Таблица */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          tableLayout: 'fixed',
          maxWidth: '100%'
        }}>
          <thead>
            <tr style={{ backgroundColor: colors.bgSecondary }}>
              {/* Чекбокс для выбора всех */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'left',
                borderBottom: `1px solid ${colors.border}`,
                width: '40px'
              }}>
                <input
                  type="checkbox"
                  checked={selectedRows.size === paginatedData.length && paginatedData.length > 0}
                  onChange={(e) => handleSelectAll(e.target.checked)}
                  style={{ cursor: 'pointer' }}
                />
              </th>

              {/* Номер */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'center',
                borderBottom: `1px solid ${colors.border}`,
                color: colors.text,
                fontWeight: '600',
                fontSize: '14px',
                width: '60px'
              }}>
                {t.number}
              </th>

              {/* Пациент */}
              <th 
                onClick={() => handleSort('patient_fio')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'left',
                  borderBottom: `1px solid ${colors.border}`,
                  color: colors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  cursor: 'pointer',
                  minWidth: '200px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  {t.patient}
                  {sortConfig.key === 'patient_fio' && (
                    sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>

              {/* Телефон */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'left',
                borderBottom: `1px solid ${colors.border}`,
                color: colors.text,
                fontWeight: '600',
                fontSize: '14px',
                minWidth: '140px'
              }}>
                {t.phone}
              </th>

              {/* Год рождения */}
              <th 
                onClick={() => handleSort('patient_birth_year')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'center',
                  borderBottom: `1px solid ${colors.border}`,
                  color: colors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  cursor: 'pointer',
                  width: '60px',
                  minWidth: '60px',
                  maxWidth: '60px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                  {t.birthYear}
                  {sortConfig.key === 'patient_birth_year' && (
                    sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>

              {/* Адрес */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'left',
                borderBottom: `1px solid ${colors.border}`,
                color: colors.text,
                fontWeight: '600',
                fontSize: '14px',
                minWidth: '150px'
              }}
              className="hide-on-mobile"
              >
                {t.address}
              </th>

              {/* Тип обращения */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'center',
                borderBottom: `1px solid ${colors.border}`,
                color: colors.text,
                fontWeight: '600',
                fontSize: '14px',
                minWidth: '100px'
              }}>
                {t.visitType}
              </th>

              {/* Услуги */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'left',
                borderBottom: `1px solid ${colors.border}`,
                color: colors.text,
                fontWeight: '600',
                fontSize: '14px',
                minWidth: '200px'
              }}>
                {t.services}
              </th>

              {/* Вид оплаты */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'center',
                borderBottom: `1px solid ${colors.border}`,
                color: colors.text,
                fontWeight: '600',
                fontSize: '14px',
                minWidth: '120px'
              }}>
                {t.paymentType}
              </th>

              {/* Дата и время */}
              <th 
                onClick={() => handleSort('appointment_date')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'center',
                  borderBottom: `1px solid ${colors.border}`,
                  color: colors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  cursor: 'pointer',
                  minWidth: '120px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                  {t.date}
                  {sortConfig.key === 'appointment_date' && (
                    sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>

              {/* Статус */}
              <th 
                onClick={() => handleSort('status')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'center',
                  borderBottom: `1px solid ${colors.border}`,
                  color: colors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  cursor: 'pointer',
                  minWidth: '90px',
                  maxWidth: '90px',
                  width: '90px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                  {t.status}
                  {sortConfig.key === 'status' && (
                    sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>

              {/* Подтверждение */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'center',
                borderBottom: `1px solid ${colors.border}`,
                color: colors.text,
                fontWeight: '600',
                fontSize: '14px',
                minWidth: '120px'
              }}>
                {t.confirmation}
              </th>

              {/* Стоимость */}
              <th 
                onClick={() => handleSort('cost')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'right',
                  borderBottom: `1px solid ${colors.border}`,
                  color: colors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  cursor: 'pointer',
                  minWidth: '100px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'flex-end' }}>
                  {t.cost}
                  {sortConfig.key === 'cost' && (
                    sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>

              {/* Действия */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'center',
                borderBottom: `1px solid ${colors.border}`,
                color: colors.text,
                fontWeight: '600',
                fontSize: '14px',
                width: '80px',
                minWidth: '80px',
                maxWidth: '80px'
              }}>
                {t.actions}
              </th>
            </tr>
          </thead>
          <tbody>
            {paginatedData.length === 0 ? (
              <tr>
                <td 
                  colSpan="10" 
                  style={{
                    padding: '40px',
                    textAlign: 'center',
                    color: colors.textSecondary,
                    fontSize: '16px'
                  }}
                >
                  {t.noData}
                </td>
              </tr>
            ) : (
              paginatedData.map((row, index) => (
                <tr 
                  key={row.id}
                  className="enhanced-table-row"
                  style={{
                    backgroundColor: selectedRows.has(row.id) ? colors.accent + '10' : 'transparent',
                    borderBottom: `1px solid ${colors.border}`,
                    cursor: 'pointer'
                  }}
                  onMouseEnter={(e) => {
                    if (!selectedRows.has(row.id)) {
                      e.target.closest('tr').style.backgroundColor = colors.bgSecondary;
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!selectedRows.has(row.id)) {
                      e.target.closest('tr').style.backgroundColor = 'transparent';
                    }
                  }}
                  onClick={() => onRowClick?.(row)}
                >
                  {/* Чекбокс */}
                  <td style={{ padding: '12px 8px' }}>
                    <input
                      type="checkbox"
                      checked={selectedRows.has(row.id)}
                      onChange={(e) => {
                        e.stopPropagation();
                        handleRowSelect(row.id, e.target.checked);
                      }}
                      style={{ cursor: 'pointer' }}
                    />
                  </td>

                  {/* Номер */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    color: colors.textSecondary,
                    fontSize: '14px'
                  }}>
                    {renderQueueNumbers(row)}
                  </td>

                  {/* Пациент */}
                  <td style={{
                    padding: '12px 8px',
                    color: colors.text,
                    fontSize: '14px',
                    fontWeight: '500'
                  }}>
                    <div>
                      <div>{row.patient_fio || '—'}</div>
                      {row.patient_birth_year && (
                        <div style={{
                          fontSize: '12px',
                          color: colors.textSecondary,
                          marginTop: '2px'
                        }}>
                          {new Date().getFullYear() - row.patient_birth_year} лет
                        </div>
                      )}
                    </div>
                  </td>

                  {/* Телефон */}
                  <td style={{
                    padding: '12px 8px',
                    color: colors.text,
                    fontSize: '14px'
                  }}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}>
                      <Phone size={14} style={{ color: colors.textSecondary }} />
                      {row.patient_phone || '—'}
                    </div>
                  </td>

                  {/* Год рождения */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    color: colors.text,
                    fontSize: '14px',
                    width: '60px',
                    minWidth: '60px',
                    maxWidth: '60px'
                  }}>
                    {row.patient_birth_year || '—'}
                  </td>

                  {/* Адрес */}
                  <td style={{
                    padding: '12px 8px',
                    color: colors.text,
                    fontSize: '14px',
                    maxWidth: '150px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}
                  className="hide-on-mobile"
                  title={row.address}
                  >
                    {row.address || '—'}
                  </td>

                  {/* Тип обращения */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center'
                  }}>
                    {renderVisitType((() => {
                      const discountMode = row.discount_mode;
                      if (discountMode === 'benefit') return 'free';
                      if (discountMode === 'repeat') return 'repeat';
                      if (discountMode === 'all_free') return 'free';
                      return 'paid';
                    })())}
                  </td>

                  {/* Услуги */}
                  <td style={{ padding: '12px 8px' }}>
                    {renderServices(row.services)}
                  </td>

                  {/* Вид оплаты */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center'
                  }}>
                    {renderPaymentType(row.payment_type || 'cash', row.payment_status)}
                  </td>

                  {/* Дата и время регистрации */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    color: colors.text,
                    fontSize: '14px'
                  }}>
                    <div>
                      {/* Дата и время регистрации */}
                      {row.created_at ? (
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                            <Calendar size={12} style={{ color: colors.textSecondary }} />
                            {new Date(row.created_at).toLocaleDateString('ru-RU')}
                          </div>
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            justifyContent: 'center',
                            marginTop: '2px',
                            fontSize: '12px',
                            color: colors.textSecondary
                          }}>
                            <Clock size={10} />
                            {new Date(row.created_at).toLocaleTimeString('ru-RU', { 
                              hour: '2-digit', 
                              minute: '2-digit',
                              second: '2-digit'
                            })}
                          </div>
                        </div>
                      ) : (
                        /* Fallback для старых записей без created_at */
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                            <Calendar size={12} style={{ color: colors.textSecondary }} />
                            {row.appointment_date || '—'}
                          </div>
                          {row.appointment_time && (
                            <div style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                              justifyContent: 'center',
                              marginTop: '2px',
                              fontSize: '12px',
                              color: colors.textSecondary
                            }}>
                              <Clock size={10} />
                              {row.appointment_time}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </td>

                  {/* Статус */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    minWidth: '90px',
                    maxWidth: '90px',
                    width: '90px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}>
                    {renderStatus(row.status)}
                  </td>

                  {/* Подтверждение */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    fontSize: '14px'
                  }}>
                    {renderConfirmationStatus(row)}
                  </td>

                  {/* Стоимость */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'right',
                    color: colors.success,
                    fontSize: '14px',
                    fontWeight: '600'
                  }}>
                    {(() => {
                      const amount = row.total_amount || row.cost || row.payment_amount || 0;
                      return amount > 0 ? `${amount.toLocaleString()} сум` : '—';
                    })()}
                  </td>

                  {/* Действия */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    width: '80px',
                    minWidth: '80px',
                    maxWidth: '80px'
                  }}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '4px',
                      flexWrap: 'wrap'
                    }}>
                      {/* Оплата */}
                      {(() => {
                        const status = (row.status || '').toLowerCase();
                        const paymentStatus = (row.payment_status || '').toLowerCase();
                        // Показываем кнопку оплаты если запись не оплачена
                        return (
                          status === 'paid_pending' || 
                          paymentStatus === 'pending' || 
                          (status === 'scheduled' && paymentStatus !== 'paid') ||
                          (status === 'confirmed' && paymentStatus !== 'paid') ||
                          (!paymentStatus && status !== 'paid' && status !== 'done' && status !== 'cancelled')
                        );
                      })() && (
                      <button
                        className="action-button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                          e.stopPropagation();
                            onActionClick?.('payment', row, e);
                          }}
                          style={{
                            padding: '4px 8px',
                            border: 'none',
                            borderRadius: '4px',
                            backgroundColor: colors.success,
                            color: 'white',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '500'
                          }}
                          title="Оплата"
                        >
                          💳 Оплата
                        </button>
                      )}
                      
                      {/* В кабинет */}
                      {(row.status === 'confirmed' || row.status === 'queued') && (
                        <button
                          className="action-button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            onActionClick?.('in_cabinet', row, e);
                          }}
                          style={{
                            padding: '4px 8px',
                            border: `1px solid ${colors.primary}`,
                            borderRadius: '4px',
                            backgroundColor: 'transparent',
                            color: colors.primary,
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '500'
                          }}
                          title="В кабинет"
                        >
                          🚪 В кабинет
                        </button>
                      )}
                      
                      {/* Вызвать */}
                      {row.status === 'queued' && (
                        <button
                          className="action-button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            onActionClick?.('call', row, e);
                          }}
                          style={{
                            padding: '4px 8px',
                            border: 'none',
                            borderRadius: '4px',
                            backgroundColor: colors.success,
                            color: 'white',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '500'
                          }}
                          title="Вызвать"
                        >
                          📢 Вызвать
                        </button>
                      )}
                      
                      {/* Печать */}
                      {(row.payment_status === 'paid' || row.status === 'queued') && (
                        <button
                          className="action-button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            onActionClick?.('print', row, e);
                        }}
                        style={{
                          padding: '4px',
                          border: 'none',
                          borderRadius: '4px',
                          backgroundColor: 'transparent',
                            color: colors.primary,
                            cursor: 'pointer',
                            pointerEvents: 'auto'
                        }}
                          title="Печать"
                      >
                          <FileText size={14} />
                      </button>
                      )}
                      
                      {/* Завершить */}
                      {row.status === 'in_cabinet' && (
                      <button
                        className="action-button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                          e.stopPropagation();
                            onActionClick?.('complete', row, e);
                          }}
                          style={{
                            padding: '4px 8px',
                            border: 'none',
                            borderRadius: '4px',
                            backgroundColor: colors.success,
                            color: 'white',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '500'
                          }}
                          title="Завершить"
                        >
                          ✅ Завершить
                        </button>
                      )}
                      
                      {/* Просмотр */}
                      <button
                        className="action-button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onActionClick?.('view', row, e);
                        }}
                        style={{
                          padding: '4px',
                          border: 'none',
                          borderRadius: '4px',
                          backgroundColor: 'transparent',
                          color: colors.textSecondary,
                          cursor: 'pointer',
                          pointerEvents: 'auto'
                        }}
                        title="Просмотр"
                      >
                        <Eye size={14} />
                      </button>
                      
                      {/* Еще */}
                      <button
                        className="action-button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onActionClick?.('more', row, e);
                        }}
                        style={{
                          padding: '4px',
                          border: 'none',
                          borderRadius: '4px',
                          backgroundColor: 'transparent',
                          color: colors.textSecondary,
                          cursor: 'pointer',
                          pointerEvents: 'auto'
                        }}
                        title="Еще"
                      >
                        <MoreHorizontal size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Пагинация */}
      {totalPages > 1 && (
        <div style={{
          padding: '16px',
          borderTop: `1px solid ${colors.border}`,
          backgroundColor: colors.bgSecondary,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'between',
          gap: '16px',
          flexWrap: 'wrap'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: colors.textSecondary,
            fontSize: '14px'
          }}>
            <span>{t.page}</span>
            <select
              value={currentPage}
              onChange={(e) => setCurrentPage(parseInt(e.target.value))}
              style={{
                padding: '4px 8px',
                border: `1px solid ${colors.border}`,
                borderRadius: '4px',
                backgroundColor: colors.bg,
                color: colors.text,
                fontSize: '14px'
              }}
            >
              {Array.from({ length: totalPages }, (_, i) => (
                <option key={i + 1} value={i + 1}>
                  {i + 1}
                </option>
              ))}
            </select>
            <span>{t.of} {totalPages}</span>
          </div>

          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            color: colors.textSecondary,
            fontSize: '14px'
          }}>
            <span>Показано: {paginatedData.length} из {filteredData.length}</span>
          </div>

          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <button
              className="pagination-button"
              onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
              style={{
                padding: '6px 12px',
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
                backgroundColor: colors.bg,
                color: currentPage === 1 ? colors.textSecondary : colors.text,
                fontSize: '14px',
                cursor: currentPage === 1 ? 'not-allowed' : 'pointer'
              }}
            >
              Назад
            </button>
            <button
              className="pagination-button"
              onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
              disabled={currentPage === totalPages}
              style={{
                padding: '6px 12px',
                border: `1px solid ${colors.border}`,
                borderRadius: '6px',
                backgroundColor: colors.bg,
                color: currentPage === totalPages ? colors.textSecondary : colors.text,
                fontSize: '14px',
                cursor: currentPage === totalPages ? 'not-allowed' : 'pointer'
              }}
            >
              Далее
            </button>
          </div>
        </div>
      )}

    </div>
  );
};

export default EnhancedAppointmentsTable;
