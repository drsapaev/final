// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import {
  Search,

  Download,
  ChevronUp,
  ChevronDown,
  Calendar,
  Clock,
  CalendarClock,
  User,
  Phone,
  Home, // ✅ Добавлена иконка дома
  CreditCard,
  FileText,
  MoreHorizontal,
  Eye,
  Edit,
  X,

  CheckCircle,
  XCircle,
  AlertCircle } from


'lucide-react';
import {
  Input,
  Button,
  Badge,
  Select,
  Checkbox } from '../ui/macos';
import './EnhancedAppointmentsTable.css';

import { QueueActionButtons } from '../queue/QueueManagementCard';

import logger from '../../utils/logger';
import {
  parseRegistrarTimestamp,
  getRegistrarTimestampDisplay,
  formatRegistrarDate,
  formatRegistrarTime,
  getLocalDateString,
} from '../../utils/dateUtils';

// ⭐ SSOT: Centralized service code resolver
import { LEGACY_CODE_TO_NAME, ID_TO_NAME, getServiceDisplayName } from '../../utils/serviceCodeResolver';
import PropTypes from 'prop-types';
import AppointmentPagination from './AppointmentPagination';  // PR-75
// UX Audit R-3.1: единая CSV-функция с PHI masking.
import { generateCSV, downloadCSV } from '../../pages/registrar/registrarCsv';
import { useTranslation } from '../../i18n/useTranslation';

const SESSION_COLORS = [
  'var(--mac-accent-blue)', // blue
  'var(--mac-success)', // emerald
  'var(--mac-warning)', // amber
  'var(--mac-error)', // red
  '#8B5CF6', // violet
  '#EC4899', // pink
  'var(--mac-accent-blue-light)', // cyan
  '#84CC16' // lime
];

const ACTION_ALIASES = {
  payment: ['payment', 'mark_paid', 'mark-paid'],
  call: ['call', 'start_visit', 'start-visit'],
  print: ['print', 'print_ticket', 'print-ticket'],
  complete: ['complete', 'complete_visit', 'complete-visit'],
  view_emr: ['view_emr', 'view-emr'],
  schedule_next: ['schedule_next', 'schedule-next']
};

const getBackendActionAvailability = (row, action, flagName) => {
  if (row && flagName && Object.prototype.hasOwnProperty.call(row, flagName)) {
    return Boolean(row[flagName]);
  }

  if (!Array.isArray(row?.available_actions)) {
    return null;
  }

  const actions = new Set(row.available_actions.map((item) => String(item).trim().toLowerCase()));
  const aliases = ACTION_ALIASES[action] || [action];
  return aliases.some((alias) => actions.has(alias));
};

const getEnhancedAppointmentRowKey = (row, index) => {
  const parts = [
    row?.record_type || row?.source_type || row?.source || row?.entity_type || 'appointment',
    row?.appointment_id ?? row?.visit_id ?? row?.queue_entry_id ?? row?.queue_id ?? row?.payment_id ?? row?.id ?? 'no-id',
    row?.session_id || row?.queue_number || row?.number || '',
    row?.doctor_id || row?.specialist_id || row?.department_id || row?.department || '',
    row?.appointment_time || row?.visit_time || row?.time || row?.start_time || '',
    index
  ];

  return parts.map((part) => String(part)).join(':');
};

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
  showCheckboxes = true, // ✅ Новый проп для отключения чекбоксов
  view = 'registrar' // 'registrar' | 'doctor' — режим отображения
}) => {
  const containerRef = useRef(null);
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
  const [pageSize] = useState(20);
  // Используем внешнее состояние, если передано, иначе внутреннее
  const [internalSelectedRows, setInternalSelectedRows] = useState(new Set());
  const selectedRows = externalSelectedRows || internalSelectedRows;

  const isDark = theme === 'dark';
  const isDoctorView = String(view).toLowerCase() === 'doctor';

  // Локально дублируем активную схему на контейнер таблицы, чтобы CSS [data-color-scheme]
  // сработал даже при временной потере атрибута на <html>
  useEffect(() => {
    const applyLocalScheme = () => {
      try {
        const customScheme = localStorage.getItem('customColorScheme');
        const schemeId = localStorage.getItem('activeColorSchemeId');
        const el = containerRef.current;
        if (!el) return;
        if (customScheme === 'true' && schemeId) {
          el.setAttribute('data-color-scheme', schemeId);
        } else {
          el.removeAttribute('data-color-scheme');
        }
      } catch {






        // ignore
      }};applyLocalScheme();const handler = () => applyLocalScheme();window.addEventListener('colorSchemeChanged', handler);window.addEventListener('storage', handler);return () => {
      window.removeEventListener('colorSchemeChanged', handler);
      window.removeEventListener('storage', handler);
    };
  }, []);

  // Вспомогательная функция для добавления прозрачности к CSS переменной
  const withOpacity = useCallback((cssVar, opacity) => {
    // Используем color-mix если доступен, иначе fallback
    return `color-mix(in srgb, ${cssVar} ${opacity * 100}%, transparent)`;
  }, []);

  // ✅ FIX 17: Helper для безопасного парсинга даты
  // Контракт: backend должен отдавать ISO 8601 с корректным timezone.
  // Для исторических naive строк считаем, что это время клиники Asia/Tashkent.
  const safeParseDate = useCallback((dateStr) => {
    return parseRegistrarTimestamp(dateStr);
  }, []);

  const getSessionColor = useCallback((sessionId) => {
    if (!sessionId) return null;
    // Simple hash to get consistent color for same session_id
    let hash = 0;
    for (let i = 0; i < sessionId.length; i++) {
      hash = (hash << 5) - hash + sessionId.charCodeAt(i);
      hash = hash & hash; // Convert to 32bit integer
    }
    return SESSION_COLORS[Math.abs(hash) % SESSION_COLORS.length];
  }, []);

  // ⭐ SSOT: Display helper for services with queue numbers
  // Format: "K01 (1), D01 (2), L10 (3)"
  void useCallback((rows) => {
    if (!rows || rows.length === 0) return '—';

    return rows.map((row) => {
      let serviceDisplay = '—';
      if (Array.isArray(row.services) && row.services.length > 0) {
        const svc = row.services[0];
        serviceDisplay = typeof svc === 'object' ? svc.code || svc.name || '—' : String(svc);
      } else if (row.service_codes && row.service_codes.length > 0) {
        serviceDisplay = row.service_codes[0];
      }

      const queueNum = row.queue_number ?? row.number ?? '?';
      return `${serviceDisplay} (${queueNum})`;
    }).join(', ');
  }, []);

  // ⭐ SSOT: Display helper for queue numbers
  // Format: "1, 2, 3"
  void useCallback((rows) => {
    if (!rows || rows.length === 0) return '—';
    return rows.map((r) => r.queue_number ?? r.number ?? '?').join(', ');
  }, []);

  // Переводы — i18next unified.
  const { t } = useTranslation();
  void language; // legacy prop, kept for backward compat; translations come from i18next.

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
        aVal = a.queue_numbers && a.queue_numbers.length > 0 ? a.queue_numbers[0].number : 999999;
        bVal = b.queue_numbers && b.queue_numbers.length > 0 ? b.queue_numbers[0].number : 999999;
      }

      if (aVal < bVal) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortConfig]);

  // Фильтрация данных
  const filteredData = useMemo(() => {
    return sortedData.filter((row) => {
      const searchMatch = !filterConfig.search ||
      Object.values(row).some((val) =>
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

  const getDisplayAmount = useCallback((row) => {
    if (row?.has_shared_invoice) {
      return Number(row?.cost || 0);
    }
    return Number(row?.cost || row?.invoice_amount || row?.payment_amount || 0);
  }, []);

  // Обработчик сортировки
  const handleSort = useCallback((key) => {
    setSortConfig((prev) => ({
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
      setInternalSelectedRows((prev) => {
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
      paginatedData.forEach((row) => {
        onRowSelect(row.id, checked);
      });
    } else {
      // Используем внутреннее состояние
      if (checked) {
        setInternalSelectedRows(new Set(paginatedData.map((row) => row.id)));
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
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: Calendar,
        text: t('misc.eat_status_scheduled'),
        emoji: '📅'
      },
      confirmed: {
        color: 'var(--mac-success)',
        bg: withOpacity('var(--mac-success)', 0.12),
        icon: CheckCircle,
        text: t('misc.eat_status_confirmed'),
        emoji: '✅'
      },

      // Статусы очереди
      waiting: {
        color: 'var(--mac-warning)',
        bg: withOpacity('var(--mac-warning)', 0.12),
        icon: Clock,
        text: t('misc.eat_status_waiting'),
        emoji: '⏳'
      },
      queued: {
        color: 'var(--mac-warning)',
        bg: withOpacity('var(--mac-warning)', 0.12),
        icon: Clock,
        text: t('misc.eat_status_queued'),
        emoji: '⏳'
      },
      called: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: User,
        text: t('misc.eat_status_called'),
        emoji: '📢'
      },
      in_progress: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: User,
        text: t('misc.eat_status_in_progress'),
        emoji: '👨‍⚕️'
      },
      in_cabinet: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: User,
        text: t('misc.eat_status_in_cabinet'),
        emoji: '👤'
      },
      in_visit: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: User,
        text: t('misc.eat_status_in_visit'),
        emoji: '👨‍⚕️'
      },

      // Завершённые статусы
      served: {
        color: 'var(--mac-success)',
        bg: withOpacity('var(--mac-success)', 0.12),
        icon: CheckCircle,
        text: t('misc.eat_status_served'),
        emoji: '✅'
      },
      done: {
        color: 'var(--mac-success)',
        bg: withOpacity('var(--mac-success)', 0.12),
        icon: CheckCircle,
        text: t('misc.eat_status_done'),
        emoji: '✅'
      },

      // Статусы оплаты
      paid_pending: {
        color: 'var(--mac-warning)',
        bg: withOpacity('var(--mac-warning)', 0.12),
        icon: CreditCard,
        text: t('misc.eat_status_paid_pending'),
        emoji: '⏳'
      },
      payment_paid: {
        color: 'var(--mac-success)',
        bg: withOpacity('var(--mac-success)', 0.12),
        icon: CheckCircle,
        text: t('misc.eat_status_payment_paid'),
        emoji: '✅'
      },
      paid: {
        color: 'var(--mac-success)',
        bg: withOpacity('var(--mac-success)', 0.12),
        icon: CheckCircle,
        text: t('misc.eat_status_paid'),
        emoji: '✅'
      },

      // Отрицательные статусы
      cancelled: {
        color: 'var(--mac-error)',
        bg: withOpacity('var(--mac-error)', 0.12),
        icon: XCircle,
        text: t('misc.eat_status_cancelled'),
        emoji: '❌'
      },
      // ✅ Исправлено: поддержка написания с одной l (как на бэкенде)
      canceled: {
        color: 'var(--mac-error)',
        bg: withOpacity('var(--mac-error)', 0.12),
        icon: XCircle,
        text: t('misc.eat_status_canceled'),
        emoji: '❌'
      },
      no_show: {
        color: 'var(--mac-text-secondary)',
        bg: withOpacity('var(--mac-text-secondary)', 0.12),
        icon: AlertCircle,
        text: t('misc.eat_status_no_show'),
        emoji: '👻'
      },

      // Старые статусы (для совместимости)
      plan: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: Calendar,
        text: t('misc.eat_status_plan'),
        emoji: '📅'
      }
    };

    const config = statusConfig[status] || statusConfig.scheduled;
    config.icon;

    return (
      <div
        className="status-badge"
        title={config.text}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-1)',
          padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
          borderRadius: 'var(--mac-radius-sm)',
          backgroundColor: config.bg,
          color: config.color,
          fontSize: 'var(--mac-font-size-xs)',
          fontWeight: 'var(--mac-font-weight-medium)',
          cursor: 'help',
          border: `1px solid ${withOpacity(config.color, 0.2)}`
        }}>
        <span className="eat-status-emoji">{config.emoji}</span>
        <span>{config.text}</span>
      </div>);

  }, [withOpacity, t]);

  // ✅ УНИВЕРСАЛЬНЫЙ МАППИНГ УСЛУГ (работает с любыми данными из админ панели)
  const createServiceMapping = useCallback(() => {
    const mapping = {};
    const categoryMapping = {};

    // Преобразуем структуру services в плоские маппинги
    Object.entries(services).forEach(([category, group]) => {
      if (Array.isArray(group)) {
        group.forEach((service) => {
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
  const renderServices = useCallback((appointmentServices, allPatientServices = null) => {
    if (!appointmentServices) {
      return '—';
    }

    const { mapping: serviceMapping } = createServiceMapping();

    // Поддерживаем как массив строк, так и массив объектов
    let servicesList = [];
    if (Array.isArray(appointmentServices)) {
      servicesList = appointmentServices.map((service) => {
        // Обрабатываем строки-числа (ID услуг)
        if (typeof service === 'string' && /^\d+$/.test(service)) {
          return serviceMapping[service] || t('misc.eat_service_label', { service });
        }
        // Если это просто число
        if (typeof service === 'number') {
          return serviceMapping[service] || serviceMapping[String(service)] || t('misc.eat_service_label', { service });
        }
        // Потом обычные строки
        if (typeof service === 'string') return service;
        // ⭐ ИСПРАВЛЕНО: Если объект имеет code - возвращаем код напрямую (не name!)
        // Это важно, чтобы K11 не превратился в K01 при поиске по name
        if (typeof service === 'object' && service.code) {
          return String(service.code).toUpperCase();
        }
        if (typeof service === 'object' && service.name) return service.name;
        return String(service);
      });
    } else if (typeof appointmentServices === 'string') {
      servicesList = [appointmentServices];
    } else {
      return String(appointmentServices);
    }

    if (servicesList.length === 0) {
      return '—';
    }

    // ✅ Функция проверки, является ли строка кодом (а не названием)
    const isServiceCode = (str) => {
      if (!str || typeof str !== 'string') return false;
      // Коды обычно короткие (до 20 символов), без пробелов, могут содержать подчеркивания, дефисы, буквы и цифры
      // Названия обычно длинные (более 20 символов), содержат пробелы и русские буквы
      if (str.length > 30) return false; // Длинные строки - скорее названия
      if (/\s/.test(str)) return false; // Содержит пробелы - скорее название
      // Паттерны кодов: K01, D02, D_PROC03, ECG-001, C01 и т.д.
      return /^[A-Z][A-Z0-9_-]*\d+$/i.test(str) || /^[A-Z]\d{2}$/.test(str);
    };

    // ✅ ИСПОЛЬЗУЕМ НОВЫЕ КОДЫ ИЗ БАЗЫ ДАННЫХ
    const compactCodes = servicesList.map((serviceName) => {
      // Если это уже код (K01, D02, D_PROC03, etc), возвращаем в верхнем регистре
      if (isServiceCode(serviceName)) {
        return String(serviceName).toUpperCase();
      }

      // Если это название, ищем услугу и получаем её код
      for (const group of Object.values(services)) {
        if (Array.isArray(group)) {
          const foundService = group.find((s) => s.name === serviceName);
          if (foundService) {
            // Используем service_code если есть, иначе генерируем из category_code
            if (foundService.service_code) {
              return String(foundService.service_code).toUpperCase();
            }
            // Если есть category_code но нет service_code, генерируем временный код
            if (foundService.category_code) {
              return `${String(foundService.category_code).toUpperCase()}${String(foundService.id).padStart(2, '0')}`;
            }
          }
        }
      }

      // Если ничего не найдено и это не код, возвращаем как есть (название)
      return serviceName;
    });

    // ✅ Преобразуем коды обратно в названия для tooltip
    // ⭐ SSOT: Используем централизованную функцию getServiceDisplayName
    const serviceNamesForTooltip = compactCodes.map((code) => {
      // Если это код, ищем полное название через SSOT
      if (isServiceCode(code)) {
        // ⭐ SSOT: Сначала используем централизованный маппинг
        const ssotName = getServiceDisplayName(code);
        if (ssotName && ssotName !== code) {
          return ssotName;
        }

        // Fallback: Ищем в services prop по service_code (точное совпадение)
        for (const group of Object.values(services)) {
          if (Array.isArray(group)) {
            const foundService = group.find((s) =>
            (s.service_code || '').toUpperCase() === code ||
            (s.code || '').toUpperCase() === code
            );
            if (foundService) {
              return foundService.name;
            }
          }
        }

        // Если не нашли название для кода, возвращаем код как есть
        return code;
      }

      // Если это не код (уже название), возвращаем как есть
      return code;
    });

    // Создаем tooltip с полным списком услуг пациента
    let tooltipText = '';

    if (allPatientServices && allPatientServices.length > 0) {
      // ✅ Преобразуем коды всех услуг в названия
      const allPatientServiceNames = allPatientServices.map((service) => {
        // Если это уже название (длинное, с пробелами), возвращаем как есть
        if (typeof service === 'string' && service.length > 20 && /\s/.test(service)) {
          return service;
        }

        // Если это код, ищем название
        if (isServiceCode(service)) {
          // Ищем по service_code
          for (const group of Object.values(services)) {
            if (Array.isArray(group)) {
              const foundService = group.find((s) => s.service_code === service);
              if (foundService) {
                return foundService.name;
              }
            }
          }

          // Ищем по старому полю code
          for (const group of Object.values(services)) {
            if (Array.isArray(group)) {
              const foundService = group.find((s) => s.code === service);
              if (foundService) {
                return foundService.name;
              }
            }
          }

          // Если не нашли, возвращаем код
          return service;
        }

        // Иначе возвращаем как есть
        return service;
      });

      // Показываем все услуги пациента из всех отделений
      tooltipText = `${t('misc.eat_all_services_tooltip', { count: allPatientServiceNames.length })}\n\n`;
      allPatientServiceNames.forEach((service, idx) => {
        tooltipText += `${idx + 1}. ${service}\n`;
      });

      // Добавляем информацию о текущих услугах с полными названиями
      if (serviceNamesForTooltip.length > 0) {
        tooltipText += `\n${t('misc.eat_current_services_tooltip', { count: serviceNamesForTooltip.length })}\n`;
        serviceNamesForTooltip.forEach((serviceName) => {
          tooltipText += `• ${serviceName}\n`;
        });
      }
    } else {
      // Fallback: показываем только текущие услуги с полными названиями
      tooltipText = serviceNamesForTooltip.length > 1 ?
      `${t('misc.eat_services_tooltip')}\n${serviceNamesForTooltip.map((serviceName, idx) => `${idx + 1}. ${serviceName}`).join('\n')}` :
      serviceNamesForTooltip[0] || '';
    }

    return (
      <div
        className="eat-service-code-wrap"
        title={tooltipText}>

        {compactCodes.map((code, idx) =>
        <span
          key={idx}
          style={{
            padding: '2px 6px',
            borderRadius: 'var(--mac-radius-sm)',
            fontSize: 'var(--mac-font-size-xs)',
            fontWeight: 'var(--mac-font-weight-bold)',
            backgroundColor: withOpacity('var(--mac-accent-blue)', 0.12),
            color: 'var(--mac-accent-blue)',
            border: `1px solid ${withOpacity('var(--mac-accent-blue)', 0.25)}`
          }}>

            {code}
          </span>
        )}
      </div>);

  }, [withOpacity, createServiceMapping, services, t]);

  // Рендер типа обращения
  const renderVisitType = useCallback((visitType) => {
    const typeColors = {
      paid: 'var(--mac-accent-blue)',
      repeat: 'var(--mac-success)',
      free: 'var(--mac-warning)',
      allfree: '#ff6b35',
      mixed: 'var(--mac-text-secondary)'
    };

    const typeText = t(`misc.eat_${visitType}`, { defaultValue: visitType });
    const color = typeColors[visitType] || 'var(--mac-text-secondary)';

    // ✅ ИСПРАВЛЕНО: Для allfree используем rgba напрямую, так как withOpacity работает только с CSS переменными
    const isAllFree = visitType === 'allfree';
    const isMixed = visitType === 'mixed';
    const backgroundColor = isAllFree ?
    'rgba(255, 107, 53, 0.08)' :
    isMixed ?
    'rgba(142, 142, 147, 0.10)' :
    withOpacity(color, 0.08);
    const borderColor = isAllFree ?
    'rgba(255, 107, 53, 0.2)' :
    isMixed ?
    'rgba(142, 142, 147, 0.25)' :
    withOpacity(color, 0.2);

    return (
      <span style={{
        padding: '3px 6px',
        borderRadius: 'var(--mac-radius-md)',
        fontSize: 'var(--mac-font-size-xs)',
        fontWeight: 'var(--mac-font-weight-semibold)',
        backgroundColor: backgroundColor,
        color: color,
        border: `1px solid ${borderColor}`
      }}>
        {typeText}
      </span>);

  }, [withOpacity, t]);

  // Рендер вида оплаты (i18next migration)
  const renderPaymentType = useCallback((paymentType, paymentStatus) => {
    const paymentIcons = {
      cash: '💵',
      card: '💳',
      online: '🌐',
      free: '🆓',
      approval_pending: '📝',
      pending_payment: '⌛',
      unknown_payment: '💰',
      mixed_payment: '🔀'
    };

    const paymentColors = {
      cash: 'var(--mac-success)',
      card: 'var(--mac-accent-blue)',
      online: 'var(--mac-accent-blue)',
      free: 'var(--mac-warning)',
      approval_pending: 'var(--mac-warning)',
      pending_payment: 'var(--mac-warning)',
      unknown_payment: 'var(--mac-text-secondary)',
      mixed_payment: 'var(--mac-text-secondary)'
    };

    const statusColors = {
      paid: 'var(--mac-success)',
      pending: 'var(--mac-warning)',
      failed: 'var(--mac-error)'
    };

    const paymentLabels = {
      free: t('misc.eat_payment_free'),
      approval_pending: t('misc.eat_approval_pending'),
      pending_payment: t('misc.eat_pending_payment'),
      unknown_payment: t('misc.eat_unknown_payment'),
      mixed_payment: t('misc.eat_mixed_payment')
    };
    const typeText = paymentLabels[paymentType] || t(`misc.eat_${paymentType}`, { defaultValue: paymentType });
    const icon = paymentIcons[paymentType] || '💰';
    const color = paymentColors[paymentType] || 'var(--mac-text-secondary)';void (
    statusColors[paymentStatus] || 'var(--mac-text-secondary)');

    // ✅ Упрощённый вид: вид оплаты + иконка статуса
    return (
      <div className="eat-payment-type-wrap">
        <span style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-1)',
          padding: '3px 8px',
          borderRadius: 'var(--mac-radius-sm)',
          fontSize: 'var(--mac-font-size-xs)',
          fontWeight: 'var(--mac-font-weight-medium)',
          backgroundColor: withOpacity(color, 0.08),
          color: color,
          border: `1px solid ${withOpacity(color, 0.2)}`
        }}>
          <span>{icon}</span>
          <span>{typeText}</span>
        </span>
        {paymentStatus &&
        <span className="eat-payment-status-icon">
            {paymentStatus === 'paid' ? '✅' :
          paymentStatus === 'pending' ? '⏳' :
          paymentStatus === 'failed' ? '❌' : ''}
          </span>
        }
      </div>);

  }, [withOpacity, t]);

  // Функция для форматирования номера телефона (i18next migration)
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
  // UX Audit R-3.1: используем единую generateCSV из registrarCsv.js с PHI masking.
  // Раньше: inline handleExport с formatPhoneNumber (БЕЗ маски) — PHI leak.
  // Теперь: единая функция с maskPhone=true по умолчанию + опции для extra columns.
  const handleExport = useCallback(() => {
    const csvContent = generateCSV(filteredData, {
      maskPhone: true, // R-05 fix: всегда маскируем телефон в CSV-экспорте
      includeAddress: !isDoctorView, // адрес только для registrar view
      includeTimestamps: true, // дата/время/изменено
    });
    const filename = `appointments_${getLocalDateString()}.csv`;
    downloadCSV(csvContent, filename);
  }, [filteredData, isDoctorView]);

  // Преждевременный возврат перенесён ниже, чтобы не нарушать порядок хуков

  // Функция для отображения номеров очередей
  const renderQueueNumbers = useCallback((row) => {
    // Получаем текущую дату
    const today = getLocalDateString();

    // Helper для форматирования времени





    // Если запись на текущий день - показываем номер в очереди
    if (row.date === today || row.appointment_date === today) {
      // ✅ ИСПРАВЛЕНО: Используем queue_number (уже выбран для текущей вкладки в RegistrarPanel)
      // вместо отображения всех номеров из queue_numbers, что вызывало дублирование
      if (row.queue_number !== undefined && row.queue_number !== null) {
        // ✅ ИСПРАВЛЕНО: Используем статус из queue_number_status (соответствует текущей вкладке)
        // или ищем соответствующий queue_number в queue_numbers для получения его статуса
        let queueStatus = row.queue_number_status;
        if (!queueStatus && row.queue_numbers && Array.isArray(row.queue_numbers)) {
          // Ищем queue_number в queue_numbers и берём его статус
          const matchingQueue = row.queue_numbers.find((q) => q.number === row.queue_number);
          if (matchingQueue) {
            queueStatus = matchingQueue.status;
          } else if (row.queue_numbers.length > 0) {
            // ✅ ИСПРАВЛЕНО: Если не нашли точное совпадение, используем статус из первого queue_number
            // вместо общего row.status, так как статусы отдельных очередей могут отличаться
            queueStatus = row.queue_numbers[0].status;
          }
        }
        queueStatus = queueStatus || null;
        const statusConfig = {
          waiting: {
            bg: 'var(--mac-warning, #ff9500)',
            icon: '⏳',
            text: t('misc.eat_q_status_waiting'),
            pulse: true
          },
          called: {
            bg: 'var(--mac-accent-blue, #007aff)',
            icon: '📢',
            text: t('misc.eat_status_called'),
            pulse: true
          },
          served: {
            bg: 'var(--mac-success, #34c759)',
            icon: '✅',
            text: t('misc.eat_status_served'),
            pulse: false
          },
          no_show: {
            bg: 'var(--mac-error, #ff3b30)',
            icon: '❌',
            text: t('misc.eat_status_no_show'),
            pulse: false
          },
          unknown: {
            bg: 'var(--mac-text-secondary, #8e8e93)',
            icon: '?',
            text: t('misc.eat_q_status_unknown'),
            pulse: false
          }
        };

        const config = statusConfig[queueStatus] || statusConfig.unknown;

        return (
          <>
          <span
            style={{
              padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
              backgroundColor: config.bg,
              color: 'var(--mac-text-primary)',
              borderRadius: 'var(--mac-radius-sm)',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-bold)',
              minWidth: '32px',
              textAlign: 'center',
              display: 'inline-block',
              boxShadow: 'var(--mac-shadow-sm, 0 2px 4px rgba(0,0,0,0.1))'
            }}
            title={`№${row.queue_number}`}>

            {row.queue_number}
          </span>

          {/* UX Audit Registrar #8: показываем дополнительные queue numbers
              если у пациента несколько талонов (multi-service запись).
              Раньше показывался только первый номер — остальные игнорировались. */}
          {Array.isArray(row.queue_numbers) && row.queue_numbers.length > 1 && (
            <span
              style={{
                marginLeft: 'var(--mac-spacing-1)',
                padding: '2px 6px',
                backgroundColor: 'color-mix(in srgb, var(--mac-accent-blue, #007aff), transparent 85%)',
                color: 'var(--mac-accent-blue, #007aff)',
                borderRadius: 'var(--mac-radius-sm)',
                fontSize: 'var(--mac-font-size-xs)',
                fontWeight: 'var(--mac-font-weight-semibold)',
              }}
              title={row.queue_numbers.map((q) => t('misc.eat_queue_label', { queueName: q.queue_name || t('misc.eat_queue_default'), number: q.number })).join('\n')}
            >
              +{row.queue_numbers.length - 1}
            </span>
          )}
          </>
      );
      }

      // Fallback: Если есть номера очередей, но нет queue_number - показываем первый
      if (row.queue_numbers && Array.isArray(row.queue_numbers) && row.queue_numbers.length > 0) {
        const firstQueue = row.queue_numbers[0];
        const queueStatus = firstQueue.status || null;
        const statusConfig = {
          waiting: {
            bg: 'var(--mac-warning, #ff9500)',
            icon: '⏳',
            text: t('misc.eat_q_status_waiting'),
            pulse: true
          },
          called: {
            bg: 'var(--mac-accent-blue, #007aff)',
            icon: '📢',
            text: t('misc.eat_status_called'),
            pulse: true
          },
          served: {
            bg: 'var(--mac-success, #34c759)',
            icon: '✅',
            text: t('misc.eat_status_served'),
            pulse: false
          },
          no_show: {
            bg: 'var(--mac-error, #ff3b30)',
            icon: '❌',
            text: t('misc.eat_status_no_show'),
            pulse: false
          },
          unknown: {
            bg: 'var(--mac-text-secondary, #8e8e93)',
            icon: '?',
            text: t('misc.eat_q_status_unknown'),
            pulse: false
          }
        };

        const config = statusConfig[queueStatus] || statusConfig.unknown;

        return (
          <>
          <span
            style={{
              padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
              backgroundColor: config.bg,
              color: 'var(--mac-text-primary)',
              borderRadius: 'var(--mac-radius-sm)',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-bold)',
              minWidth: '32px',
              textAlign: 'center',
              display: 'inline-block',
              boxShadow: 'var(--mac-shadow-sm, 0 2px 4px rgba(0,0,0,0.1))'
            }}
            title={t('misc.eat_queue_label', { queueName: firstQueue.queue_name || t('misc.eat_queue_default'), number: firstQueue.number })}>

            {firstQueue.number}
          </span>

          {/* UX Audit Registrar #8: multi-badge в fallback тоже. */}
          {row.queue_numbers.length > 1 && (
            <span
              style={{
                marginLeft: 'var(--mac-spacing-1)',
                padding: '2px 6px',
                backgroundColor: 'color-mix(in srgb, var(--mac-accent-blue, #007aff), transparent 85%)',
                color: 'var(--mac-accent-blue, #007aff)',
                borderRadius: 'var(--mac-radius-sm)',
                fontSize: 'var(--mac-font-size-xs)',
                fontWeight: 'var(--mac-font-weight-semibold)',
              }}
              title={row.queue_numbers.map((q) => t('misc.eat_queue_label', { queueName: q.queue_name || t('misc.eat_queue_default'), number: q.number })).join('\n')}
            >
              +{row.queue_numbers.length - 1}
            </span>
          )}
          </>
      );
      }

      // Если нет номеров очередей, но запись на сегодня - показываем порядковый номер
      // Для этого нужно найти позицию записи среди всех записей на сегодня
      const todayAppointments = data.filter((item) =>
      item.date === today || item.appointment_date === today
      );
      const todayIndex = todayAppointments.findIndex((item) => item.id === row.id) + 1;

      return (
        <span style={{
          padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
          backgroundColor: 'var(--mac-accent-blue)',
          color: 'var(--mac-text-primary)',
          borderRadius: 'var(--mac-radius-sm)',
          fontSize: 'var(--mac-font-size-base)',
          fontWeight: 'var(--mac-font-weight-bold)',
          minWidth: '32px',
          textAlign: 'center',
          display: 'inline-block',
          boxShadow: 'var(--mac-shadow-sm, 0 2px 4px rgba(0,0,0,0.1))'
        }}>
          {todayIndex}
        </span>);

    }

    // Для записей не на сегодня показываем дефолтный номер
    const fallbackIndex = data.findIndex((item) => item.id === row.id) + 1;
    return (
      <span style={{
        color: 'var(--mac-text-secondary)',
        fontSize: 'var(--mac-font-size-xs)',
        padding: '2px 6px',
        backgroundColor: withOpacity('var(--mac-text-secondary)', 0.06),
        borderRadius: 'var(--mac-radius-sm)'
      }}>
        #{fallbackIndex}
      </span>);

  }, [data, withOpacity, t]);


  // Инлайновый лоадер без раннего возврата
  const loaderNode =
  <div className="eat-loader">
      <div className="eat-td">
        <div
        className="loading-spinner eat-loader-spinner" />
        {t('misc.eat_loading')}
      </div>
    </div>;


  return (
    <div
      ref={containerRef}
      className={`enhanced-table ${isDark ? 'dark-theme' : ''}`}
      style={{
        overflow: 'hidden',
        border: outerBorder ? '1px solid var(--mac-border)' : 'none',
        borderRadius: outerBorder ? 'var(--mac-radius-lg)' : '0'
      }}>
      {/* Панель инструментов */}
      <div className="eat-toolbar">
        <div className="eat-toolbar-inner">
          {/* Поиск */}
          <div className="eat-search-input-wrap">
            <Input
              type="text"
              placeholder={t('misc.eat_search')}
              value={filterConfig.search}
              onChange={(e) => setFilterConfig((prev) => ({ ...prev, search: e.target.value }))}
              icon={Search}
              className="eat-search-input" />

          </div>

          {/* Фильтр по статусу */}
          <Select
            value={filterConfig.status}
            onChange={(e) => setFilterConfig((prev) => ({ ...prev, status: e.target.value }))}
            options={[
            { value: '', label: t('misc.eat_filter') },
            { value: 'scheduled', label: t('misc.eat_scheduled') },
            { value: 'confirmed', label: t('misc.eat_confirmed') },
            { value: 'queued', label: t('misc.eat_queued') },
            { value: 'in_cabinet', label: t('misc.eat_in_cabinet') },
            { value: 'done', label: t('misc.eat_done') },
            { value: 'cancelled', label: t('misc.eat_cancelled') },
            { value: 'paid_pending', label: t('misc.eat_paid_pending') },
            { value: 'paid', label: t('misc.eat_payment_paid') }]
            }
            className="eat-filter-select" />


          {/* Экспорт */}
          <Button
            variant="outline"
            onClick={handleExport}
            className="eat-export-btn">

            <Download size={16} />
            {t('misc.eat_export')}
          </Button>

          {/* Информация о выбранных */}
          {showCheckboxes && selectedRows.size > 0 &&
          <Badge variant="info">
              {t('misc.eat_selected')}: {selectedRows.size}
            </Badge>
          }
        </div>
      </div>

      {/* Таблица */}
      {loading ? loaderNode : null}
      <div className="eat-table-scroll">
        <div className="admin-table-wrapper">
<table className="eat-table-container" style={{
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
            <tr>
              {/* Чекбокс для выбора всех */}
              {showCheckboxes &&
              <th className="eat-th" style={{
                padding: '12px 8px',
                textAlign: 'left',
                borderBottom: '1px solid var(--mac-border)',
                width: '40px',
                color: 'var(--mac-text-primary)'
              }}
              aria-label={t('misc.eat_select_all')}>
                  <Checkbox aria-label={t('misc.eat_select_all')} checked={selectedRows.size === paginatedData.length && paginatedData.length > 0}
                  onChange={(e) => handleSelectAll(e.target.checked)}
                  />

                </th>
              }

              {/* Номер */}
              <th
                onClick={() => handleSort('queue_number')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'center',
                  borderBottom: '1px solid var(--mac-border)',
                  color: 'var(--mac-text-primary)',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  fontSize: 'var(--mac-font-size-base)',
                  width: '60px',
                  cursor: 'pointer',
                  userSelect: 'none'
                }}>

                <div className="eat-th-content">
                  {t('misc.eat_number')}
                  {sortConfig.key === 'queue_number' && (
                  sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />)
                  }
                </div>
              </th>

              {/* Пациент */}
              <th
                onClick={() => handleSort('patient_fio')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'left',
                  borderBottom: '1px solid var(--mac-border)',
                  color: 'var(--mac-text-primary)',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  fontSize: 'var(--mac-font-size-base)',
                  cursor: 'pointer',
                  minWidth: isDoctorView ? '15%' : '200px',
                  width: isDoctorView ? '15%' : 'auto'
                }}>

                <div className="eat-th-content">
                  {t('misc.eat_patient')}
                  {sortConfig.key === 'patient_fio' && (
                  sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />)
                  }
                </div>
              </th>

              {/* Телефон - скрыт для doctor view */}
              {!isDoctorView &&
              <th className="eat-th" style={{
                padding: '12px 8px',
                textAlign: 'left',
                borderBottom: '1px solid var(--mac-border)',
                color: 'var(--mac-text-primary)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                fontSize: 'var(--mac-font-size-base)',
                minWidth: '170px'
              }}>
                  {t('misc.eat_phone')}
                </th>
              }

              {/* Год рождения */}
              <th
                onClick={() => handleSort('patient_birth_year')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'center',
                  borderBottom: '1px solid var(--mac-border)',
                  color: 'var(--mac-text-primary)',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  fontSize: 'var(--mac-font-size-base)',
                  cursor: 'pointer',
                  width: isDoctorView ? '5%' : '60px',
                  minWidth: isDoctorView ? '5%' : '60px'
                }}>

                <div className="eat-th-content">
                  {t('misc.eat_birth_year')}
                  {sortConfig.key === 'patient_birth_year' && (
                  sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />)
                  }
                </div>
              </th>

              {/* Адрес - скрыт для doctor view */}
              {!isDoctorView &&
              <th className="eat-th hide-on-mobile" style={{
                padding: '12px 8px',
                textAlign: 'left',
                borderBottom: '1px solid var(--mac-border)',
                color: 'var(--mac-text-primary)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                fontSize: 'var(--mac-font-size-base)',
                minWidth: '140px'
              }}>

                  {t('misc.eat_address')}
                </th>
              }

              {/* Тип обращения */}
              <th className="eat-th" style={{
                padding: '12px 8px',
                textAlign: 'center',
                borderBottom: '1px solid var(--mac-border)',
                color: 'var(--mac-text-primary)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                fontSize: 'var(--mac-font-size-base)',
                minWidth: isDoctorView ? '70px' : '80px',
                width: isDoctorView ? '70px' : 'auto'
              }}>
                {t('misc.eat_visit_type')}
              </th>

              {/* Услуги */}
              <th className="eat-th" style={{
                padding: '12px 8px',
                textAlign: 'left',
                borderBottom: '1px solid var(--mac-border)',
                color: 'var(--mac-text-primary)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                fontSize: 'var(--mac-font-size-base)',
                minWidth: isDoctorView ? '12%' : '180px',
                width: isDoctorView ? '12%' : 'auto'
              }}>
                {t('misc.eat_services')}
              </th>

              {/* Вид оплаты */}
              <th className="eat-th" style={{
                padding: '12px 8px',
                textAlign: 'center',
                borderBottom: '1px solid var(--mac-border)',
                color: 'var(--mac-text-primary)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                fontSize: 'var(--mac-font-size-base)',
                minWidth: isDoctorView ? '8%' : '100px',
                width: isDoctorView ? '8%' : 'auto'
              }}>
                {t('misc.eat_payment_type')}
              </th>

              {/* Дата и время */}
              <th
                onClick={() => handleSort('appointment_date')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'center',
                  borderBottom: '1px solid var(--mac-border)',
                  color: 'var(--mac-text-primary)',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  fontSize: 'var(--mac-font-size-base)',
                  cursor: 'pointer',
                  minWidth: isDoctorView ? '9%' : '100px',
                  width: isDoctorView ? '9%' : 'auto'
                }}>

                <div className="eat-th-content">
                  {t('misc.eat_date')}
                  {sortConfig.key === 'appointment_date' && (
                  sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />)
                  }
                </div>
              </th>

              {/* Статус */}
              <th
                onClick={() => handleSort('status')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'center',
                  borderBottom: '1px solid var(--mac-border)',
                  color: 'var(--mac-text-primary)',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  fontSize: 'var(--mac-font-size-base)',
                  cursor: 'pointer',
                  minWidth: isDoctorView ? '7%' : '80px',
                  width: isDoctorView ? '7%' : 'auto'
                }}>

                <div className="eat-th-content">
                  {t('misc.eat_status')}
                  {sortConfig.key === 'status' && (
                  sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />)
                  }
                </div>
              </th>


              {/* Стоимость */}
              <th
                onClick={() => handleSort('cost')}
                style={{
                  padding: '12px 8px',
                  textAlign: 'right',
                  borderBottom: '1px solid var(--mac-border)',
                  color: 'var(--mac-text-primary)',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  fontSize: 'var(--mac-font-size-base)',
                  cursor: 'pointer',
                  minWidth: isDoctorView ? '8%' : '90px',
                  width: isDoctorView ? '8%' : 'auto'
                }}>

                <div className="eat-th-content--end">
                  {t('misc.eat_cost')}
                  {sortConfig.key === 'cost' && (
                  sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />)
                  }
                </div>
              </th>

              {/* Действия */}
              <th className="eat-th" style={{
                padding: '12px 8px',
                textAlign: 'center',
                borderBottom: '1px solid var(--mac-border)',
                color: 'var(--mac-text-primary)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                fontSize: 'var(--mac-font-size-base)',
                width: isDoctorView ? '15%' : 'auto',
                minWidth: isDoctorView ? '15%' : '200px'
              }}>
                {t('misc.eat_actions')}
              </th>
            </tr>
          </thead>
          <tbody>
            {paginatedData.length === 0 ?
            <tr>
                <td
                colSpan="10"
                className="eat-empty-row">

                  {t('misc.eat_no_data')}
                </td>
              </tr> :

            paginatedData.map((row, index) => {
              // ⭐ SSOT: Get session color for visual grouping (presentation only)
              const sessionColor = getSessionColor(row.session_id);
              const backendCanPay = getBackendActionAvailability(row, 'payment', 'can_mark_paid');
              const backendCanCall = getBackendActionAvailability(row, 'call', 'can_start_visit');
              const backendCanPrint = getBackendActionAvailability(row, 'print', 'can_print_ticket');
              const backendCanComplete = getBackendActionAvailability(row, 'complete', 'can_complete');
              const backendCanViewEmr = getBackendActionAvailability(row, 'view_emr', 'can_view_emr');
              const backendCanScheduleNext = getBackendActionAvailability(row, 'schedule_next', 'can_schedule_next');
              const canPay = !isDoctorView && backendCanPay === true;
              const canCall = isDoctorView && backendCanCall === true;
              const canPrint = backendCanPrint === true;
              const canComplete = isDoctorView && backendCanComplete === true;
              const canViewEmr = isDoctorView && backendCanViewEmr === true;
              const canScheduleNext = isDoctorView && backendCanScheduleNext === true;
              // UX Audit Registrar #4: inline кнопки Cancel и Reschedule для registrar view.
              // Раньше были доступны только через context menu (правый клик),
              // что не работало на touch-устройствах (планшеты в регистратуре).
              const canCancel = !isDoctorView && (
                row?.status === 'waiting' ||
                row?.status === 'called' ||
                row?.status === 'pending' ||
                row?.status === 'confirmed'
              );
              const canReschedule = !isDoctorView && (
                row?.status === 'waiting' ||
                row?.status === 'pending' ||
                row?.status === 'confirmed'
              );

              return (
                <tr
                  key={getEnhancedAppointmentRowKey(row, index)}
                  className="enhanced-table-row"
                  style={{
                    backgroundColor: selectedRows.has(row.id) ?
                    withOpacity('var(--mac-accent-blue)', 0.06) :
                    index % 2 === 0 ? 'var(--mac-bg-primary)' : 'var(--mac-bg-secondary)',
                    borderBottom: '1px solid var(--mac-border)',
                    cursor: 'pointer',
                    // ⭐ SSOT: Visual session grouping indicator
                    borderLeft: sessionColor ? `4px solid ${sessionColor}` : 'none',
                    position: 'relative'
                  }}
                  onMouseEnter={(e) => {
                    if (!selectedRows.has(row.id)) {
                      e.target.closest('tr').style.backgroundColor = 'var(--mac-bg-secondary)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!selectedRows.has(row.id)) {
                      // Восстанавливаем фон на основе индекса (для полосатой таблицы)
                      const tr = e.target.closest('tr');
                      if (tr) {
                        tr.style.backgroundColor = index % 2 === 0 ? 'var(--mac-bg-primary)' : 'var(--mac-bg-secondary)';
                      }
                    }
                  }}
                  onClick={() => onRowClick?.(row)}
                  title={row.session_id ? t('misc.eat_session_label', { sessionId: row.session_id }) : undefined}>

                    {/* Чекбокс */}
                    {showCheckboxes &&
                  <td
                    className="eat-td-base"
                    aria-label={`${t('misc.eat_select_all')}: ${row.patient_fio || row.patient_name || row.id}`}>
                        <Checkbox aria-label={`${t('misc.eat_select_all')}: ${row.patient_fio || row.patient_name || row.id}`} checked={selectedRows.has(row.id)} onChange={(e) => {
                        e.stopPropagation();
                        handleRowSelect(row.id, e.target.checked);
                      }}
                      />

                      </td>
                  }

                    {/* Номер */}
                    <td className="eat-td" style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    color: 'var(--mac-text-secondary)',
                    fontSize: 'var(--mac-font-size-base)'
                  }}>
                      {renderQueueNumbers(row)}
                    </td>

                    {/* Пациент */}
                    <td className="eat-td" style={{
                    padding: '12px 8px',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-base)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    minWidth: isDoctorView ? '15%' : '200px',
                    width: isDoctorView ? '15%' : 'auto',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}
                  title={isDoctorView ? `${row.patient_fio || '—'}\n📞 ${formatPhoneNumber(row.patient_phone)}\n🏠 ${row.address || '—'}` : undefined}>

                      <div>
                        <div className="eat-td-flex">
                          <span>{row.patient_fio || '—'}</span>
                          {/* Ярлыки источника/приоритета */}
                          {/* ✅ SSOT: Только source='online' показывает QR badge */}
                          {row.source === 'online' &&
                        <span
                          style={{
                            fontSize: 'var(--mac-font-size-xs)',
                            padding: '2px 6px',
                            borderRadius: 'var(--mac-radius-sm)',
                            background: 'linear-gradient(135deg, var(--mac-accent-purple) 0%, var(--mac-accent-purple) 100%)',
                            color: 'white',
                            fontWeight: 'var(--mac-font-weight-semibold)',
                            whiteSpace: 'nowrap'
                          }}
                          title={t('misc.eat_qr_priority_title')}>

                              QR
                            </span>
                        }
                          {row.source === 'desk' &&
                        <span
                          style={{
                            fontSize: 'var(--mac-font-size-xs)',
                            padding: '2px 6px',
                            borderRadius: 'var(--mac-radius-sm)',
                            background: 'var(--mac-separator)',
                            color: 'var(--mac-text-secondary)',
                            fontWeight: 'var(--mac-font-weight-semibold)',
                            whiteSpace: 'nowrap'
                          }}>

                              Manual
                            </span>
                        }
                        </div>
                        {row.patient_birth_year &&
                      <div className="eat-patient-age">
                            {t('misc.eat_years_old', { count: new Date().getFullYear() - row.patient_birth_year })}
                          </div>
                      }
                      </div>
                    </td>

                    {/* Телефон - скрыт для doctor view */}
                    {!isDoctorView &&
                  <td className="eat-td" style={{
                    padding: '12px 8px',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-base)',
                    minWidth: '170px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}>
                        <div className="eat-phone-cell">
                          <Phone size={18} className="eat-phone-icon" />
                          {formatPhoneNumber(row.patient_phone)}
                        </div>
                      </td>
                  }

                    {/* Год рождения */}
                    <td className="eat-td" style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-base)',
                    width: isDoctorView ? '50px' : '60px',
                    minWidth: isDoctorView ? '50px' : '60px',
                    maxWidth: isDoctorView ? '50px' : '60px'
                  }}>
                      {row.patient_birth_year || '—'}
                    </td>

                    {/* Адрес - скрыт для doctor view */}
                    {!isDoctorView &&
                  <td className="eat-td hide-on-mobile" style={{
                    padding: '12px 8px',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-base)',
                    minWidth: '140px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'normal',
                    lineHeight: '1.4'
                  }}
                  title={row.address}>

                        {row.address ?
                    <div className="eat-phone-cell">
                            <Home size={18} style={{
                        color: 'var(--mac-accent-blue)',
                        fontWeight: 'var(--mac-font-weight-bold)',
                        filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.1))',
                        flexShrink: 0
                      }} />
                            <span className="eat-address-text">
                              {row.address}
                            </span>
                          </div> :
                    '—'}
                      </td>
                  }

                    {/* Тип обращения */}
                    <td className="eat-td" style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    minWidth: '80px'
                  }}>
                      {renderVisitType((() => {
                      // ✅ ИСПРАВЛЕНО: Проверяем и discount_mode, и approval_status для all_free
                      const discountMode = row.discount_mode;
                      if (discountMode === 'mixed') return 'mixed';
                      const isAllFreeApproved = discountMode === 'all_free' && row.approval_status === 'approved';

                      if (discountMode === 'benefit') return 'free';
                      if (discountMode === 'repeat') return 'repeat';
                      // ✅ ИСПРАВЛЕНО: Для AllFree возвращаем 'allfree' вместо 'free'
                      if (isAllFreeApproved || discountMode === 'all_free') return 'allfree';
                      return 'paid';
                    })())}
                    </td>

                    {/* Услуги */}
                    <td className="eat-td" style={{
                    padding: '12px 8px',
                    minWidth: '180px'
                  }}>
                      {/* ✅ ИСПРАВЛЕНО: Fallback для QR-записей (через service_name или queue_numbers) */}
                      {renderServices(
                      (() => {
                        // Если есть services, используем их
                        if (row.services && (Array.isArray(row.services) ? row.services.length > 0 : true)) {
                          return row.services;
                        }
                        // Fallback 1: service_name из записи
                        if (row.service_name) {
                          return [row.service_name];
                        }
                        // Fallback 2: service_name из queue_numbers
                        if (row.queue_numbers && row.queue_numbers.length > 0 && row.queue_numbers[0].service_name) {
                          return [row.queue_numbers[0].service_name];
                        }
                        // Fallback 3: specialty из queue_numbers (для совместимости)
                        if (row.queue_numbers && row.queue_numbers.length > 0 && row.queue_numbers[0].specialty) {
                          return [row.queue_numbers[0].specialty];
                        }
                        return row.services;
                      })(),
                      row.all_patient_services
                    )}
                    </td>

                    {/* Вид оплаты */}
                    <td className="eat-td" style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    minWidth: '100px'
                  }}>
                      {renderPaymentType(
                      (() => {
                        if (row.payment_type === 'mixed_payment') {
                          return 'mixed_payment';
                        }
                        if (row.payment_type === 'approval_pending') {
                          return 'approval_pending';
                        }
                        if (row.payment_type === 'free') {
                          return 'free';
                        }
                        const discountMode = row.discount_mode;
                        const paymentStatus = (row.payment_status || '').toLowerCase();
                        const amount = getDisplayAmount(row);
                        const isApprovedAllFree = discountMode === 'all_free' && row.approval_status === 'approved';
                        const isPendingAllFree = discountMode === 'all_free' && row.approval_status !== 'approved';
                        const isZeroCostDiscount = ['repeat', 'benefit'].includes(discountMode) && amount <= 0 && paymentStatus !== 'paid';

                        if (isPendingAllFree) {
                          return 'approval_pending';
                        }
                        if (isApprovedAllFree || isZeroCostDiscount) {
                          return 'free';
                        }
                        return row.payment_type || (paymentStatus === 'paid' ? 'unknown_payment' : 'pending_payment');
                      })(),
                      row.payment_status
                    )}
                    </td>

                    {/* P1 fix: Lab results badge — shows if lab results are ready */}
                    {row.latest_lab_report && (
                      <td className="eat-td" style={{
                        padding: '12px 8px',
                        textAlign: 'center',
                        fontSize: '12px',
                      }}>
                        {(() => {
                          const labStatus = row.latest_lab_report.status || '';
                          const isReady = labStatus === 'FINALIZED' || labStatus === 'PRINTED';
                          const flagCount = row.latest_lab_report.flagged_findings_count || 0;
                          return (
                            <span
                              title={`${row.latest_lab_report.template_name || t('misc.eat_lab_report_default')} — ${isReady ? t('misc.eat_lab_ready') : t('misc.eat_lab_in_progress')}${flagCount > 0 ? t('misc.eat_lab_flagged', { count: flagCount }) : ''}`}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '2px 8px',
                                borderRadius: '10px',
                                fontSize: '11px',
                                fontWeight: 600,
                                background: isReady ? 'rgba(52, 199, 89, 0.12)' : 'rgba(255, 149, 0, 0.12)',
                                color: isReady ? 'var(--mac-success)' : 'var(--mac-warning)',
                              }}>
                              {isReady ? t('misc.eat_lab_ready_badge') : t('misc.eat_lab_in_progress_badge')}
                              {flagCount > 0 && ` ⚠${flagCount}`}
                            </span>
                          );
                        })()}
                      </td>
                    )}

                    {/* Дата и время регистрации */}
                    <td className="eat-td" style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-base)',
                    minWidth: '100px'
                  }}>
                      <div>
                        {/* Дата и время регистрации */}
                        {/* ✅ SSOT FIX: ONLY use queue_time. Compute earliest from all patient entries if needed. */}
                        {(() => {
                        // ⭐ SSOT: Use row.queue_time directly - no aggregation
                        const timeDisplay = getRegistrarTimestampDisplay(row);

                        if (timeDisplay.primaryDate || timeDisplay.primaryTime) {
                          return (
                            <div title={t('misc.eat_timezone_label', { timeZone: timeDisplay.timeZone })}>
                                <div className="eat-time-label">
                                  {timeDisplay.primaryLabel}
                                </div>
                                <div className="eat-th-content">
                                  <Calendar size={12} className="eat-calendar-icon" />
                                  {timeDisplay.primaryDate}
                                </div>
                                <div className="eat-time-row">
                                  <Clock size={10} />
                                  {timeDisplay.primaryTime}
                                </div>
                                {timeDisplay.showChanged &&
                              <div className="eat-time-changed">
                                    {timeDisplay.changedLabel}: {timeDisplay.changedDate} {timeDisplay.changedTime}
                                  </div>
                              }
                              </div>);

                        }

                        // Fallback: use appointment_date/time for legacy records without queue_time
                        if (row.appointment_date || row.appointment_time) {
                          return (
                            <div>
                                <div className="eat-th-content">
                                  <Calendar size={12} className="eat-calendar-icon" />
                                  {row.appointment_date || '—'}
                                </div>
                                {row.appointment_time &&
                              <div className="eat-time-row">
                                    <Clock size={10} />
                                    {row.appointment_time}
                                  </div>
                              }
                              </div>);

                        }

                        return '-';
                      })()}
                      </div>
                    </td>

                    {/* Статус */}
                    <td className="eat-td" style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    minWidth: '80px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}>
                      {/* UX Audit R-4.4: показываем visit status + payment status.
                          Раньше: 15 статусов в одной колонке, включая paid_pending/payment_paid.
                          Теперь: visit status (основной) + payment badge (если есть). */}
                      {renderStatus(row.status)}
                      {row.payment_status && row.payment_status !== 'paid' && (
                        <div style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '2px',
                          marginTop: '2px',
                          padding: '1px 4px',
                          borderRadius: 'var(--mac-radius-sm)',
                          backgroundColor: 'var(--mac-accent-orange-soft, rgba(255, 149, 0, 0.12))',
                          color: 'var(--mac-accent-orange, #ff9500)',
                          fontSize: '9px',
                          fontWeight: 'var(--mac-font-weight-medium)',
                        }}>
                          💰 {row.payment_status === 'paid_pending' ? t('misc.eat_pending_payment') : row.payment_status}
                        </div>
                      )}
                    </td>


                    {/* Стоимость */}
                    <td className="eat-td" style={{
                    padding: '12px 8px',
                    textAlign: 'right',
                    color: (() => {
                      if (row.cost_display === 'free') return 'var(--mac-warning)';
                      const discountMode = row.discount_mode;
                      const amount = getDisplayAmount(row);
                      const isZeroCostRegistration = ['all_free', 'repeat', 'benefit', 'mixed'].includes(discountMode) && amount <= 0;
                      if (isZeroCostRegistration) return 'var(--mac-warning)';

                      return amount > 0 ? 'var(--mac-success, #34c759)' : 'var(--mac-text-secondary)';
                    })(),
                    fontSize: 'var(--mac-font-size-base)',
                    fontWeight: 'var(--mac-font-weight-semibold)',
                    minWidth: '90px'
                  }}>
                      {(() => {
                      if (row.cost_display === 'free') {
                        return t('misc.eat_payment_free');
                      }
                      const discountMode = row.discount_mode;
                      const amount = getDisplayAmount(row);
                      const isZeroCostRegistration = ['all_free', 'repeat', 'benefit', 'mixed'].includes(discountMode) && amount <= 0;
                      if (isZeroCostRegistration) {
                        return t('misc.eat_payment_free');
                      }
                      return amount > 0 ? t('misc.eat_amount_with_currency', { amount: amount.toLocaleString() }) : '—';
                    })()}
                    </td>

                    {/* Действия */}
                    <td
                    style={{
                      padding: '12px 8px',
                      textAlign: 'center',
                      width: '200px',
                      minWidth: '200px',
                      maxWidth: '200px',
                      position: 'relative',
                      zIndex: 100
                    }}
                    onClick={(e) => {
                      // Блокируем клик на строку при клике в ячейке действий
                      e.stopPropagation();
                    }}
                    onMouseDown={(e) => {
                      // Блокируем mousedown на строку при клике в ячейке действий
                      e.stopPropagation();
                    }}>

                      <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: 'var(--mac-spacing-1)',
                        flexWrap: 'wrap',
                        position: 'relative',
                        zIndex: 100
                      }}>

                        {/* В режиме панели врача кнопки оплаты не показываем */}
                        {canPay &&
                      <button
                        className="action-button action-button--success"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                        }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onActionClick?.('payment', row, e);
                        }}
                        title={t('misc.eat_payment')}>

                              {t('misc.eat_payment')}
                            </button>
                      }

                        {/* Вызвать */}
                        {canCall &&
                      <button
                        className="action-button action-button--primary"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                        }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onActionClick?.('call', row, e);
                        }}
                        title={t('misc.eat_call_action')}>

                            {t('misc.eat_call_action')}
                          </button>
                      }

                        {/* Печать */}
                        {canPrint &&
                      <button
                        className="action-button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                        }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onActionClick?.('print', row, e);
                        }}
                        title={t('misc.eat_print')}
                        aria-label={t('misc.eat_print')}>

                            <FileText size={14} />
                          </button>
                      }

                        {/* Завершить */}
                        {canComplete &&
                      <button
                        className="action-button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                        }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onActionClick?.('complete', row, e);
                        }}
                        title={t('misc.eat_complete')}>

                            {t('misc.eat_complete')}
                          </button>
                      }

                        {/* ✅ НОВОЕ: Кнопки управления статусами очереди (для режима врача) */}
                          {isDoctorView && row.queue_entry_id &&
                        <QueueActionButtons
                          entry={{
                            queue_entry_id: row.queue_entry_id,
                            status: row.status,
                            queue_status: row.queue_status,
                            available_actions: row.available_actions,
                            can_no_show: row.can_no_show,
                            can_send_to_diagnostics: row.can_send_to_diagnostics,
                            can_notify_diagnostics_return: row.can_notify_diagnostics_return,
                            can_restore_next: row.can_restore_next,
                            can_incomplete: row.can_incomplete,
                            can_complete: getBackendActionAvailability(row, 'complete', 'can_complete')
                          }}
                          onStatusChange={(action, entry, result) => {
                            logger.log(`[EnhancedAppointmentsTable] Queue action: ${action}`, entry, result);
                            // Передаём событие наружу для обновления списка
                            onActionClick?.(`queue_${action}`, row, null);
                          }}
                          compact={true} />

                        }

                        {/* Просмотр */}
                        <button
                        className="action-button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          logger.log('[EnhancedAppointmentsTable] Кнопка Просмотр нажата:', row);
                        }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onActionClick?.('view', row, e);
                        }}
                        title={t('misc.eat_view')}
                        aria-label={t('misc.eat_view')}>

                          <Eye size={14} />
                        </button>

                        {/* Редактировать */}
                        <button
                        className="action-button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          logger.log('[EnhancedAppointmentsTable] Кнопка Редактировать нажата:', row);
                        }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onActionClick?.('edit', row, e);
                        }}
                        title={t('misc.eat_edit')}
                        aria-label={t('misc.eat_edit')}>

                          <Edit size={14} />
                        </button>

                        {/* Просмотр EMR (только для завершённых записей) */}
                        {canViewEmr &&
                        <button
                        className="action-button action-button--primary"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                        }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onActionClick?.('view_emr', row, e);
                        }}
                        title={t('misc.eat_view_emr')}
                        aria-label={t('misc.eat_view_emr')}>

                              <FileText size={14} />
                            </button>
                      }

                        {/* UX Audit Registrar #4: inline кнопки Cancel и Reschedule.
                            Раньше только через context menu — недоступно на touch-устройствах. */}
                        {canReschedule &&
                      <button
                        className="action-button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                        }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onActionClick?.('reschedule', row, e);
                        }}
                        title={t('misc.eat_reschedule')}
                        aria-label={t('misc.eat_reschedule_aria')}>
                          <CalendarClock size={14} />
                        </button>
                      }

                        {canCancel &&
                      <button
                        className="action-button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                        }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onActionClick?.('cancel', row, e);
                        }}
                        title={t('misc.eat_cancel')}
                        aria-label={t('misc.eat_cancel_aria')}>
                          <X size={14} />
                        </button>
                      }

                        {/* Еще */}
                      <button
                        className="action-button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                        }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onActionClick?.('more', row, e);
                        }}
                        title={t('misc.eat_more')}
                        aria-label={t('misc.eat_more')}>

                          <MoreHorizontal size={14} />
                        </button>

                        {/* Назначить следующий визит */}
                        {canScheduleNext &&
                      <button
                        className="action-button action-button--primary"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                        }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          onActionClick?.('schedule_next', row, e);
                        }}
                        title={t('misc.eat_schedule_next_title')}>

                            {t('misc.eat_schedule_next')}
                          </button>
                      }
                      </div>
                    </td>
                  </tr>);
              // ⭐ End of return statement
            }) // ⭐ End of paginatedData.map
            }
          </tbody>
        </table>
</div>
      </div>

      {/* Пагинация */}
      {totalPages > 1 &&
      <div className="eat-pagination">
          <div className="eat-pagination-info">
            <span>{t('misc.eat_page')}</span>
            <select
            value={currentPage}
            onChange={(e) => setCurrentPage(parseInt(e.target.value))}
            className="eat-pagination-select">

              {Array.from({ length: totalPages }, (_, i) =>
            <option key={i + 1} value={i + 1}>
                  {i + 1}
                </option>
            )}
            </select>
            <span>{t('misc.eat_of')} {totalPages}</span>
          </div>

          <div className="eat-pagination-info">
            <span>{t('misc.eat_shown_of', { shown: paginatedData.length, total: filteredData.length })}</span>
          </div>

          <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <button
            className="pagination-button"
            onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
            disabled={currentPage === 1}
            style={{
              padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-sm)',
              backgroundColor: 'var(--mac-bg-primary)',
              color: currentPage === 1 ? 'var(--mac-text-secondary)' : 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-base)',
              cursor: currentPage === 1 ? 'not-allowed' : 'pointer'
            }}>

              {t('misc.eat_back')}
            </button>
            <button
            className="pagination-button"
            onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
            disabled={currentPage === totalPages}
            style={{
              padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-sm)',
              backgroundColor: 'var(--mac-bg-primary)',
              color: currentPage === totalPages ? 'var(--mac-text-secondary)' : 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-base)',
              cursor: currentPage === totalPages ? 'not-allowed' : 'pointer'
            }}>

              {t('misc.eat_next')}
            </button>
          </div>
        </div>
      }

    </div>);

};


EnhancedAppointmentsTable.propTypes = {
  ...(EnhancedAppointmentsTable.propTypes || {}),
  data: PropTypes.any,
  language: PropTypes.any,
  loading: PropTypes.any,
  onActionClick: PropTypes.any,
  onRowClick: PropTypes.any,
  onRowSelect: PropTypes.any,
  outerBorder: PropTypes.any,
  selectedRows: PropTypes.any,
  services: PropTypes.any,
  showCheckboxes: PropTypes.any,
  theme: PropTypes.any,
  view: PropTypes.any,
};

export default EnhancedAppointmentsTable;
