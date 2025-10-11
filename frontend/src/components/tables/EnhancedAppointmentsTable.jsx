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
  Home,  // ✅ Добавлена иконка дома
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
import { colors } from '../../theme/tokens';

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
  outerBorder = true,
  showCheckboxes = true,  // ✅ Новый проп для отключения чекбоксов
  view = 'registrar'      // 'registrar' | 'doctor' — режим отображения
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
  const isDoctorView = String(view).toLowerCase() === 'doctor';
  
  // Цвета для темы
  // Используем консолидированную цветовую систему из tokens.js
  const themeColors = {
    bg: isDark ? '#1f2937' : '#ffffff',
    bgSecondary: isDark ? '#374151' : '#f8fafc',
    border: isDark ? '#4b5563' : '#e2e8f0',
    text: isDark ? '#f9fafb' : '#1e293b',
    textSecondary: isDark ? '#d1d5db' : '#64748b',
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
      
      // ✅ Специальная обработка для номера очереди
      if (sortConfig.key === 'queue_number') {
        // Извлекаем первый номер очереди из массива queue_numbers
        aVal = (a.queue_numbers && a.queue_numbers.length > 0) ? a.queue_numbers[0].number : 999999;
        bVal = (b.queue_numbers && b.queue_numbers.length > 0) ? b.queue_numbers[0].number : 999999;
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

  // ✅ Улучшенный рендер статуса (полный контекстный)
  const renderStatus = useCallback((status) => {
    const statusConfig = {
      // Статусы записи
      scheduled: { 
        color: themeColors.accent, 
        bg: `${themeColors.accent}20`, 
        icon: Calendar, 
        text: 'Запланирован',
        emoji: '📅'
      },
      confirmed: { 
        color: themeColors.success, 
        bg: `${themeColors.success}20`, 
        icon: CheckCircle, 
        text: 'Подтверждён',
        emoji: '✅'
      },
      
      // Статусы очереди
      waiting: {
        color: themeColors.warning,
        bg: `${themeColors.warning}20`,
        icon: Clock,
        text: 'В очереди',
        emoji: '⏳'
      },
      queued: { 
        color: themeColors.warning, 
        bg: `${themeColors.warning}20`, 
        icon: Clock, 
        text: 'В очереди',
        emoji: '⏳'
      },
      called: {
        color: themeColors.accent,
        bg: `${themeColors.accent}20`,
        icon: User,
        text: 'Вызван',
        emoji: '📢'
      },
      in_progress: {
        color: themeColors.accent,
        bg: `${themeColors.accent}20`,
        icon: User,
        text: 'На приёме',
        emoji: '👨‍⚕️'
      },
      in_cabinet: { 
        color: themeColors.accent, 
        bg: `${themeColors.accent}20`, 
        icon: User, 
        text: 'В кабинете',
        emoji: '👤'
      },
      in_visit: { 
        color: themeColors.accent, 
        bg: `${themeColors.accent}20`, 
        icon: User, 
        text: 'На приёме',
        emoji: '👨‍⚕️'
      },
      
      // Завершённые статусы
      served: {
        color: themeColors.success,
        bg: `${themeColors.success}20`,
        icon: CheckCircle,
        text: 'Обслужен',
        emoji: '✅'
      },
      done: { 
        color: themeColors.success, 
        bg: `${themeColors.success}20`, 
        icon: CheckCircle, 
        text: 'Обслужен',
        emoji: '✅'
      },
      
      // Статусы оплаты
      paid_pending: { 
        color: themeColors.warning, 
        bg: `${themeColors.warning}20`, 
        icon: CreditCard, 
        text: 'Ожидает оплаты',
        emoji: '⏳'
      },
      payment_paid: { 
        color: themeColors.success, 
        bg: `${themeColors.success}20`, 
        icon: CheckCircle, 
        text: 'Оплачен',
        emoji: '✅'
      },
      paid: { 
        color: themeColors.success, 
        bg: `${themeColors.success}20`, 
        icon: CheckCircle, 
        text: 'Оплачен',
        emoji: '✅'
      },
      
      // Отрицательные статусы
      cancelled: { 
        color: themeColors.error, 
        bg: `${themeColors.error}20`, 
        icon: XCircle, 
        text: 'Отменён',
        emoji: '❌'
      },
      no_show: { 
        color: themeColors.textSecondary, 
        bg: `${themeColors.textSecondary}20`, 
        icon: AlertCircle, 
        text: 'Не явился',
        emoji: '👻'
      },
      
      // Старые статусы (для совместимости)
      plan: { 
        color: themeColors.accent, 
        bg: `${themeColors.accent}20`, 
        icon: Calendar, 
        text: 'Запланирован',
        emoji: '📅'
      }
    };

    const config = statusConfig[status] || statusConfig.scheduled;
    const Icon = config.icon;

    return (
      <div 
        className="status-badge"
        title={config.text}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          padding: '4px 8px',
          borderRadius: '6px',
          backgroundColor: config.bg,
          color: config.color,
          fontSize: '12px',
          fontWeight: '500',
          cursor: 'help',
          border: `1px solid ${config.color}30`
        }}>
        <span style={{ fontSize: '14px' }}>{config.emoji}</span>
        <span>{config.text}</span>
      </div>
    );
  }, [colors]);

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
              backgroundColor: themeColors.accent + '20',
              color: themeColors.accent,
              border: `1px solid ${themeColors.accent}40`
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
      paid: themeColors.accent,
      repeat: themeColors.success,
      free: themeColors.warning
    };

    const typeText = t[visitType] || visitType;
    const color = typeColors[visitType] || themeColors.textSecondary;

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
      cash: themeColors.success,
      card: themeColors.accent,
      online: '#8b5cf6'
    };

    const statusColors = {
      paid: themeColors.success,
      pending: themeColors.warning,
      failed: themeColors.error
    };

    const typeText = t[paymentType] || paymentType;
    const icon = paymentIcons[paymentType] || '💰';
    const color = paymentColors[paymentType] || themeColors.textSecondary;
    const statusColor = statusColors[paymentStatus] || themeColors.textSecondary;

    // ✅ Упрощённый вид: вид оплаты + иконка статуса
    return (
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '6px',
        justifyContent: 'center'
      }}>
        <span style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          padding: '3px 8px',
          borderRadius: '6px',
          fontSize: '12px',
          fontWeight: '500',
          backgroundColor: `${color}15`,
          color: color,
          border: `1px solid ${color}30`
        }}>
          <span>{icon}</span>
          <span>{typeText}</span>
        </span>
        {paymentStatus && (
          <span style={{
            fontSize: '16px',
            lineHeight: 1
          }}>
            {paymentStatus === 'paid' ? '✅' : 
             paymentStatus === 'pending' ? '⏳' : 
             paymentStatus === 'failed' ? '❌' : ''}
          </span>
        )}
      </div>
    );
    }, [colors, t]);

  // Функция для форматирования номера телефона
  const formatPhoneNumber = useCallback((phone) => {
    if (!phone) return '—';
    
    // Убираем все нецифровые символы
    const digits = phone.replace(/\D/g, '');
    
    // Если номер начинается с 998, добавляем +
    if (digits.startsWith('998')) {
      const formatted = `+998 (${digits.slice(3, 5)}) ${digits.slice(5, 8)}-${digits.slice(8, 10)}-${digits.slice(10, 12)}`;
      return formatted;
    }
    
    // Если номер начинается с 9 (без кода страны)
    if (digits.startsWith('9') && digits.length >= 9) {
      const formatted = `+998 (${digits.slice(0, 2)}) ${digits.slice(2, 5)}-${digits.slice(5, 7)}-${digits.slice(7, 9)}`;
      return formatted;
    }
    
    // Если номер короткий или нестандартный, возвращаем как есть
    return phone;
  }, []);

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
      // Заголовки - для doctor view убираем телефон и адрес
      isDoctorView 
        ? [t.number, t.patient, t.birthYear, t.visitType, t.services, t.paymentType, t.date, t.time, t.status, t.cost].join(',')
        : [t.number, t.patient, t.phone, t.birthYear, t.address, t.visitType, t.services, t.paymentType, t.date, t.time, t.status, t.cost].join(','),
      // Данные
      ...filteredData.map((row, index) => {
        const baseData = [
          // Номера очередей для CSV
          row.queue_numbers && row.queue_numbers.length > 0 
            ? row.queue_numbers.map(q => `${q.queue_name}: №${q.number}`).join('; ')
            : index + 1,
          row.patient_fio || '',
        ];
        
        // Для doctor view не включаем телефон и адрес
        if (!isDoctorView) {
          baseData.push(
            formatPhoneNumber(row.patient_phone),
            row.patient_birth_year || '',
            row.address || ''
          );
        } else {
          baseData.push(row.patient_birth_year || '');
        }
        
        return baseData.concat([
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
          row.total_amount || row.cost || row.payment_amount || ''
        ]).join(',');
      })
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `appointments_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
  }, [filteredData, t]);

  // Преждевременный возврат перенесён ниже, чтобы не нарушать порядок хуков

  // Функция для отображения номеров очередей
  const renderQueueNumbers = useCallback((row) => {
    // Получаем текущую дату
    const today = new Date().toISOString().split('T')[0];

    // Если запись на текущий день - показываем номер в очереди
    if (row.date === today || row.appointment_date === today) {
      // Если есть номера очередей из нового API
      if (row.queue_numbers && Array.isArray(row.queue_numbers) && row.queue_numbers.length > 0) {
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
            {row.queue_numbers.map((queue, index) => {
              // Определяем цвета и иконки для статусов
              const statusConfig = {
                waiting: {
                  bg: themeColors.warning,
                  icon: '⏳',
                  text: 'Ожидает',
                  pulse: true
                },
                called: {
                  bg: themeColors.accent,
                  icon: '📢',
                  text: 'Вызван',
                  pulse: true
                },
                served: {
                  bg: themeColors.success,
                  icon: '✅',
                  text: 'Обслужен',
                  pulse: false
                },
                no_show: {
                  bg: themeColors.error,
                  icon: '❌',
                  text: 'Не явился',
                  pulse: false
                }
              };

              const config = statusConfig[queue.status] || statusConfig.waiting;

              // ✅ Показываем только номер очереди (без названия и статуса)
              return (
                <span 
                  key={index}
                  style={{
                    padding: '4px 8px',
                    backgroundColor: config.bg,
                    color: 'white',
                    borderRadius: '6px',
                    fontSize: '14px',
                    fontWeight: '700',
                    minWidth: '32px',
                    textAlign: 'center',
                    display: 'inline-block',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                  }}
                  title={`${queue.queue_name}: №${queue.number}`}
                >
                  {queue.number}
                </span>
              );
            })}
          </div>
        );
      }

      // Если нет номеров очередей, но запись на сегодня - показываем порядковый номер
      // Для этого нужно найти позицию записи среди всех записей на сегодня
      const todayAppointments = data.filter(item =>
        item.date === today || item.appointment_date === today
      );
      const todayIndex = todayAppointments.findIndex(item => item.id === row.id) + 1;

      return (
        <span style={{
          padding: '4px 8px',
          backgroundColor: themeColors.accent,
          color: 'white',
          borderRadius: '6px',
          fontSize: '14px',
          fontWeight: '700',
          minWidth: '32px',
          textAlign: 'center',
          display: 'inline-block',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        }}>
          {todayIndex}
        </span>
      );
    }

    // Для записей не на сегодня показываем дефолтный номер
    const fallbackIndex = data.findIndex(item => item.id === row.id) + 1;
    return (
      <span style={{
        color: themeColors.textSecondary,
        fontSize: '12px',
        padding: '2px 6px',
        backgroundColor: themeColors.textSecondary + '10',
        borderRadius: '4px'
      }}>
        #{fallbackIndex}
      </span>
    );
  }, [data, colors]);


  // Инлайновый лоадер без раннего возврата
  const loaderNode = (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '60px',
      color: themeColors.textSecondary
    }}>
      <div style={{ textAlign: 'center' }}>
        <div 
          className="loading-spinner"
          style={{
            width: '40px',
            height: '40px',
            border: `3px solid ${themeColors.border}`,
            borderTop: `3px solid ${themeColors.accent}`,
            borderRadius: '50%',
            margin: '0 auto 16px'
          }} />
        {t.loading}
      </div>
    </div>
  );

  return (
    <div 
      className={`enhanced-table ${isDark ? 'dark-theme' : ''}`}
      style={{
        backgroundColor: themeColors.bg,
        overflow: 'hidden',
        border: outerBorder ? `1px solid ${themeColors.border}` : 'none',
        borderRadius: outerBorder ? '12px' : '0'
      }}>
      {/* Панель инструментов */}
      <div style={{
        padding: '16px',
        borderBottom: `1px solid ${themeColors.border}`,
        backgroundColor: themeColors.bgSecondary
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
                color: themeColors.textSecondary
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
                border: `1px solid ${themeColors.border}`,
                borderRadius: '6px',
                backgroundColor: themeColors.bg,
                color: themeColors.text,
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
              border: `1px solid ${themeColors.border}`,
              borderRadius: '6px',
              backgroundColor: themeColors.bg,
              color: themeColors.text,
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
              border: `1px solid ${themeColors.border}`,
              borderRadius: '6px',
              backgroundColor: themeColors.bg,
              color: themeColors.text,
              fontSize: '14px',
              cursor: 'pointer'
            }}
          >
            <Download size={16} />
            {t.export}
          </button>

          {/* Информация о выбранных */}
          {showCheckboxes && selectedRows.size > 0 && (
            <div style={{
              padding: '8px 12px',
              backgroundColor: themeColors.accent + '20',
              color: themeColors.accent,
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
      {loading ? loaderNode : null}
      <div style={{
        width: '100%',
        maxWidth: '100%',
        overflowX: 'auto',
        overflowY: 'visible',
        boxSizing: 'border-box',
        position: 'relative',
        zIndex: 1
      }}>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          tableLayout: 'auto',
          minWidth: isDoctorView ? '100%' : '1400px',
          position: 'relative',
          zIndex: 1,
          maxWidth: '100%',
          boxSizing: 'border-box'
        }}>
          <thead>
            <tr style={{ backgroundColor: themeColors.bgSecondary }}>
              {/* Чекбокс для выбора всех */}
              {showCheckboxes && (
                <th style={{
                  padding: '12px 8px',
                  textAlign: 'left',
                  borderBottom: `1px solid ${themeColors.border}`,
                  width: '40px'
                }}>
                  <input
                    type="checkbox"
                    checked={selectedRows.size === paginatedData.length && paginatedData.length > 0}
                    onChange={(e) => handleSelectAll(e.target.checked)}
                    style={{ cursor: 'pointer' }}
                  />
                </th>
              )}

              {/* Номер */}
              <th 
                onClick={() => handleSort('queue_number')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'center',
                  borderBottom: `1px solid ${themeColors.border}`,
                  color: themeColors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  width: '60px',
                  cursor: 'pointer',  // ✅ Указатель при наведении
                  userSelect: 'none'  // ✅ Запрет выделения текста
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                  {t.number}
                  {sortConfig.key === 'queue_number' && (
                    sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>

              {/* Пациент */}
              <th 
                onClick={() => handleSort('patient_fio')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'left',
                  borderBottom: `1px solid ${themeColors.border}`,
                  color: themeColors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  cursor: 'pointer',
                  minWidth: isDoctorView ? '15%' : '200px',
                  width: isDoctorView ? '15%' : 'auto'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  {t.patient}
                  {sortConfig.key === 'patient_fio' && (
                    sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>

              {/* Телефон - скрыт для doctor view */}
              {!isDoctorView && (
                <th style={{
                  padding: '12px 8px',
                  textAlign: 'left',
                  borderBottom: `1px solid ${themeColors.border}`,
                  color: themeColors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                    minWidth: '170px'
                  }}>
                    {t.phone}
                </th>
              )}

              {/* Год рождения */}
              <th 
                onClick={() => handleSort('patient_birth_year')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'center',
                  borderBottom: `1px solid ${themeColors.border}`,
                  color: themeColors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  cursor: 'pointer',
                  width: isDoctorView ? '5%' : '60px',
                  minWidth: isDoctorView ? '5%' : '60px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                  {t.birthYear}
                  {sortConfig.key === 'patient_birth_year' && (
                    sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>

              {/* Адрес - скрыт для doctor view */}
              {!isDoctorView && (
                <th style={{
                  padding: '12px 8px',
                  textAlign: 'left',
                  borderBottom: `1px solid ${themeColors.border}`,
                  color: themeColors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                    minWidth: '140px'
                  }}
                  className="hide-on-mobile"
                >
                  {t.address}
                </th>
              )}

              {/* Тип обращения */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'center',
                borderBottom: `1px solid ${themeColors.border}`,
                color: themeColors.text,
                fontWeight: '600',
                fontSize: '14px',
                minWidth: isDoctorView ? '70px' : '80px',
                width: isDoctorView ? '70px' : 'auto'
              }}>
                  {t.visitType}
              </th>

              {/* Услуги */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'left',
                borderBottom: `1px solid ${themeColors.border}`,
                color: themeColors.text,
                fontWeight: '600',
                fontSize: '14px',
                  minWidth: isDoctorView ? '12%' : '180px',
                  width: isDoctorView ? '12%' : 'auto'
              }}>
                  {t.services}
              </th>

              {/* Вид оплаты */}
              <th style={{
                padding: '12px 8px',
                textAlign: 'center',
                borderBottom: `1px solid ${themeColors.border}`,
                color: themeColors.text,
                fontWeight: '600',
                fontSize: '14px',
                  minWidth: isDoctorView ? '8%' : '100px',
                  width: isDoctorView ? '8%' : 'auto'
              }}>
                  {t.paymentType}
              </th>

              {/* Дата и время */}
              <th 
                onClick={() => handleSort('appointment_date')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'center',
                  borderBottom: `1px solid ${themeColors.border}`,
                  color: themeColors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  cursor: 'pointer',
                  minWidth: isDoctorView ? '9%' : '100px',
                  width: isDoctorView ? '9%' : 'auto'
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
                  borderBottom: `1px solid ${themeColors.border}`,
                  color: themeColors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  cursor: 'pointer',
                  minWidth: isDoctorView ? '7%' : '80px',
                  width: isDoctorView ? '7%' : 'auto'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                  {t.status}
                  {sortConfig.key === 'status' && (
                    sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />
                  )}
                </div>
              </th>


              {/* Стоимость */}
              <th 
                onClick={() => handleSort('cost')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'right',
                  borderBottom: `1px solid ${themeColors.border}`,
                  color: themeColors.text,
                  fontWeight: '600',
                  fontSize: '14px',
                  cursor: 'pointer',
                  minWidth: isDoctorView ? '8%' : '90px',
                  width: isDoctorView ? '8%' : 'auto'
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
                borderBottom: `1px solid ${themeColors.border}`,
                color: themeColors.text,
                fontWeight: '600',
                fontSize: '14px',
                width: isDoctorView ? '15%' : 'auto',
                  minWidth: isDoctorView ? '15%' : '200px'
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
                    color: themeColors.textSecondary,
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
                    backgroundColor: selectedRows.has(row.id) ? themeColors.accent + '10' : 'transparent',
                    borderBottom: `1px solid ${themeColors.border}`,
                    cursor: 'pointer'
                  }}
                  onMouseEnter={(e) => {
                    if (!selectedRows.has(row.id)) {
                      e.target.closest('tr').style.backgroundColor = themeColors.bgSecondary;
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
                  {showCheckboxes && (
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
                  )}

                  {/* Номер */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    color: themeColors.textSecondary,
                    fontSize: '14px'
                  }}>
                    {renderQueueNumbers(row)}
                  </td>

                  {/* Пациент */}
                  <td style={{
                    padding: '12px 8px',
                    color: themeColors.text,
                    fontSize: '14px',
                    fontWeight: '500',
                    minWidth: isDoctorView ? '15%' : '200px',
                    width: isDoctorView ? '15%' : 'auto',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}
                  title={isDoctorView ? `${row.patient_fio || '—'}\n📞 ${formatPhoneNumber(row.patient_phone)}\n🏠 ${row.address || '—'}` : undefined}
                  >
                    <div>
                      <div>{row.patient_fio || '—'}</div>
                      {row.patient_birth_year && (
                        <div style={{
                          fontSize: '12px',
                          color: themeColors.textSecondary,
                          marginTop: '2px'
                        }}>
                          {new Date().getFullYear() - row.patient_birth_year} лет
                        </div>
                      )}
                    </div>
                  </td>

                  {/* Телефон - скрыт для doctor view */}
                  {!isDoctorView && (
                    <td style={{
                      padding: '12px 8px',
                      color: themeColors.text,
                      fontSize: '14px',
                      minWidth: '170px',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}>
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                      }}>
                        <Phone size={18} style={{ color: themeColors.accent, fontWeight: 'bold', filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.1))' }} />
                        {formatPhoneNumber(row.patient_phone)}
                      </div>
                    </td>
                  )}

                  {/* Год рождения */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    color: themeColors.text,
                    fontSize: '14px',
                    width: isDoctorView ? '50px' : '60px',
                    minWidth: isDoctorView ? '50px' : '60px',
                    maxWidth: isDoctorView ? '50px' : '60px'
                  }}>
                    {row.patient_birth_year || '—'}
                  </td>

                  {/* Адрес - скрыт для doctor view */}
                  {!isDoctorView && (
                    <td style={{
                      padding: '12px 8px',
                      color: themeColors.text,
                      fontSize: '14px',
                      minWidth: '140px',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'normal',
                      lineHeight: '1.4'
                    }}
                    className="hide-on-mobile"
                    title={row.address}
                    >
                      {row.address ? (
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px'
                        }}>
                          <Home size={18} style={{ 
                            color: themeColors.accent, 
                            fontWeight: 'bold', 
                            filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.1))',
                            flexShrink: 0  // ✅ Иконка не сжимается
                          }} />
                          <span style={{ 
                            overflow: 'hidden', 
                            textOverflow: 'ellipsis',
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical'
                          }}>
                            {row.address}
                          </span>
                        </div>
                      ) : '—'}
                    </td>
                  )}

                  {/* Тип обращения */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    minWidth: '80px'
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
                  <td style={{ 
                    padding: '12px 8px',
                    minWidth: '180px'
                  }}>
                    {renderServices(row.services)}
                  </td>

                  {/* Вид оплаты */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    minWidth: '100px'
                  }}>
                    {renderPaymentType(row.payment_type || 'cash', row.payment_status)}
                  </td>

                  {/* Дата и время регистрации */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    color: themeColors.text,
                    fontSize: '14px',
                    minWidth: '100px'
                  }}>
                    <div>
                      {/* Дата и время регистрации */}
                      {row.created_at ? (
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                            <Calendar size={12} style={{ color: themeColors.textSecondary }} />
                            {new Date(row.created_at).toLocaleDateString('ru-RU')}
                          </div>
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            justifyContent: 'center',
                            marginTop: '2px',
                            fontSize: '12px',
                            color: themeColors.textSecondary
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
                            <Calendar size={12} style={{ color: themeColors.textSecondary }} />
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
                              color: themeColors.textSecondary
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
                    minWidth: '80px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}>
                    {renderStatus(row.status)}
                  </td>


                  {/* Стоимость */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'right',
                    color: themeColors.success,
                    fontSize: '14px',
                    fontWeight: '600',
                    minWidth: '90px'
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
                    width: '200px',
                    minWidth: '200px',
                    maxWidth: '200px'
                  }}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '4px',
                      flexWrap: 'wrap'
                    }}>
                      {/* В режиме панели врача кнопки оплаты не показываем */}
                      {!isDoctorView && (() => {
                        const status = (row.status || '').toLowerCase();
                        const paymentStatus = (row.payment_status || '').toLowerCase();
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
                            backgroundColor: themeColors.success,
                            color: 'white',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '500'
                          }}
                          title="Оплата"
                        >
                          💸 Оплата
                        </button>
                      )}
                      
                      {/* Вызвать */}
                      {(isDoctorView ? (row.status === 'queued' || row.payment_status === 'paid') : row.status === 'queued') && (
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
                            backgroundColor: themeColors.success,
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
                            color: themeColors.primary,
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
                            backgroundColor: themeColors.success,
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
                          color: themeColors.textSecondary,
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
                          color: themeColors.textSecondary,
                          cursor: 'pointer',
                          pointerEvents: 'auto'
                        }}
                        title="Еще"
                      >
                        <MoreHorizontal size={14} />
                      </button>

                      {/* Назначить следующий визит */}
                      {isDoctorView && row.status === 'done' && (
                        <button
                          className="action-button"
                          onMouseDown={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            onActionClick?.('schedule_next', row, e);
                          }}
                          style={{
                            padding: '4px 8px',
                            border: 'none',
                            borderRadius: '4px',
                            backgroundColor: themeColors.info,
                            color: 'white',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: '500'
                          }}
                          title="Назначить следующий визит"
                        >
                          📅 Следующий
                        </button>
                      )}
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
          borderTop: `1px solid ${themeColors.border}`,
          backgroundColor: themeColors.bgSecondary,
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
            color: themeColors.textSecondary,
            fontSize: '14px'
          }}>
            <span>{t.page}</span>
            <select
              value={currentPage}
              onChange={(e) => setCurrentPage(parseInt(e.target.value))}
              style={{
                padding: '4px 8px',
                border: `1px solid ${themeColors.border}`,
                borderRadius: '4px',
                backgroundColor: themeColors.bg,
                color: themeColors.text,
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
            color: themeColors.textSecondary,
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
                border: `1px solid ${themeColors.border}`,
                borderRadius: '6px',
                backgroundColor: themeColors.bg,
                color: currentPage === 1 ? themeColors.textSecondary : themeColors.text,
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
                border: `1px solid ${themeColors.border}`,
                borderRadius: '6px',
                backgroundColor: themeColors.bg,
                color: currentPage === totalPages ? themeColors.textSecondary : themeColors.text,
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

