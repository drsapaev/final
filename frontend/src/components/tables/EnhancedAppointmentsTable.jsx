import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react';
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
import {
  MacOSInput,
  MacOSButton,
  MacOSBadge,
  MacOSSelect,
  MacOSCard
} from '../ui/macos';
import './EnhancedAppointmentsTable.css';
import { colors } from '../../theme/tokens';

import logger from '../../utils/logger';
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
  const [pageSize, setPageSize] = useState(20);
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
      } catch (_) {
        // ignore
      }
    };
    applyLocalScheme();
    const handler = () => applyLocalScheme();
    window.addEventListener('colorSchemeChanged', handler);
    window.addEventListener('storage', handler);
    return () => {
      window.removeEventListener('colorSchemeChanged', handler);
      window.removeEventListener('storage', handler);
    };
  }, []);

  // Цвета для темы - используем macOS CSS переменные
  const themeColors = {
    bg: 'var(--mac-bg-primary)',
    bgSecondary: 'var(--mac-bg-secondary)',
    border: 'var(--mac-border)',
    text: 'var(--mac-text-primary)',
    textSecondary: 'var(--mac-text-secondary)',
    accent: 'var(--mac-accent-blue, var(--mac-accent, #007aff))',
    success: 'var(--mac-success, #34c759)',
    warning: 'var(--mac-warning, #ff9500)',
    error: 'var(--mac-error, #ff3b30)',
    info: 'var(--mac-info, var(--mac-accent-blue, #007aff))'
  };

  // Вспомогательная функция для добавления прозрачности к CSS переменной
  const withOpacity = (cssVar, opacity) => {
    // Используем color-mix если доступен, иначе fallback
    return `color-mix(in srgb, ${cssVar} ${opacity * 100}%, transparent)`;
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
      allfree: 'AllFree',
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
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: Calendar,
        text: 'Запланирован',
        emoji: '📅'
      },
      confirmed: {
        color: 'var(--mac-success)',
        bg: withOpacity('var(--mac-success)', 0.12),
        icon: CheckCircle,
        text: 'Подтверждён',
        emoji: '✅'
      },

      // Статусы очереди
      waiting: {
        color: 'var(--mac-warning)',
        bg: withOpacity('var(--mac-warning)', 0.12),
        icon: Clock,
        text: 'В очереди',
        emoji: '⏳'
      },
      queued: {
        color: 'var(--mac-warning)',
        bg: withOpacity('var(--mac-warning)', 0.12),
        icon: Clock,
        text: 'В очереди',
        emoji: '⏳'
      },
      called: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: User,
        text: 'Вызван',
        emoji: '📢'
      },
      in_progress: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: User,
        text: 'На приёме',
        emoji: '👨‍⚕️'
      },
      in_cabinet: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: User,
        text: 'В кабинете',
        emoji: '👤'
      },
      in_visit: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
        icon: User,
        text: 'На приёме',
        emoji: '👨‍⚕️'
      },

      // Завершённые статусы
      served: {
        color: 'var(--mac-success)',
        bg: withOpacity('var(--mac-success)', 0.12),
        icon: CheckCircle,
        text: 'Обслужен',
        emoji: '✅'
      },
      done: {
        color: 'var(--mac-success)',
        bg: withOpacity('var(--mac-success)', 0.12),
        icon: CheckCircle,
        text: 'Обслужен',
        emoji: '✅'
      },

      // Статусы оплаты
      paid_pending: {
        color: 'var(--mac-warning)',
        bg: withOpacity('var(--mac-warning)', 0.12),
        icon: CreditCard,
        text: 'Ожидает оплаты',
        emoji: '⏳'
      },
      payment_paid: {
        color: 'var(--mac-success)',
        bg: withOpacity('var(--mac-success)', 0.12),
        icon: CheckCircle,
        text: 'Оплачен',
        emoji: '✅'
      },
      paid: {
        color: 'var(--mac-success)',
        bg: withOpacity('var(--mac-success)', 0.12),
        icon: CheckCircle,
        text: 'Оплачен',
        emoji: '✅'
      },

      // Отрицательные статусы
      cancelled: {
        color: 'var(--mac-error)',
        bg: withOpacity('var(--mac-error)', 0.12),
        icon: XCircle,
        text: 'Отменён',
        emoji: '❌'
      },
      // ✅ Исправлено: поддержка написания с одной l (как на бэкенде)
      canceled: {
        color: 'var(--mac-error)',
        bg: withOpacity('var(--mac-error)', 0.12),
        icon: XCircle,
        text: 'Отменён',
        emoji: '❌'
      },
      no_show: {
        color: 'var(--mac-text-secondary)',
        bg: withOpacity('var(--mac-text-secondary)', 0.12),
        icon: AlertCircle,
        text: 'Не явился',
        emoji: '👻'
      },

      // Старые статусы (для совместимости)
      plan: {
        color: 'var(--mac-accent-blue)',
        bg: withOpacity('var(--mac-accent-blue)', 0.12),
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
          border: `1px solid ${withOpacity(config.color, 0.2)}`
        }}>
        <span style={{ fontSize: '14px' }}>{config.emoji}</span>
        <span>{config.text}</span>
      </div>
    );
  }, [withOpacity]);

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
  const renderServices = useCallback((appointmentServices, allPatientServices = null) => {
    if (!appointmentServices) {
      return '—';
    }

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
    const compactCodes = servicesList.map((serviceName, index) => {
      // Если это уже код (K01, D02, D_PROC03, etc), возвращаем в верхнем регистре
      if (isServiceCode(serviceName)) {
        return String(serviceName).toUpperCase();
      }

      // Если это название, ищем услугу и получаем её код
      for (const group of Object.values(services)) {
        if (Array.isArray(group)) {
          const foundService = group.find(s => s.name === serviceName);
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
    const serviceNamesForTooltip = compactCodes.map(code => {
      // Если это код, ищем полное название
      if (isServiceCode(code)) {
        // Ищем по service_code (точное совпадение)
        for (const group of Object.values(services)) {
          if (Array.isArray(group)) {
            const foundService = group.find(s => s.service_code === code);
            if (foundService) {
              return foundService.name;
            }
          }
        }

        // Ищем по старому полю code
        for (const group of Object.values(services)) {
          if (Array.isArray(group)) {
            const foundService = group.find(s => s.code === code);
            if (foundService) {
              return foundService.name;
            }
          }
        }

        // Если не нашли по service_code, пытаемся найти по category_code + id (только для формата K01, D02)
        if (/^[A-Z]\d{2}$/.test(code)) {
          const categoryCode = code[0];
          const serviceId = parseInt(code.slice(1));
          for (const group of Object.values(services)) {
            if (Array.isArray(group)) {
              const foundService = group.find(s =>
                s.category_code === categoryCode && s.id === serviceId
              );
              if (foundService) {
                return foundService.name;
              }
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
      const allPatientServiceNames = allPatientServices.map(service => {
        // Если это уже название (длинное, с пробелами), возвращаем как есть
        if (typeof service === 'string' && service.length > 20 && /\s/.test(service)) {
          return service;
        }

        // Если это код, ищем название
        if (isServiceCode(service)) {
          // Ищем по service_code
          for (const group of Object.values(services)) {
            if (Array.isArray(group)) {
              const foundService = group.find(s => s.service_code === service);
              if (foundService) {
                return foundService.name;
              }
            }
          }

          // Ищем по старому полю code
          for (const group of Object.values(services)) {
            if (Array.isArray(group)) {
              const foundService = group.find(s => s.code === service);
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
      tooltipText = `🏥 Все услуги пациента (${allPatientServiceNames.length}):\n\n`;
      allPatientServiceNames.forEach((service, idx) => {
        tooltipText += `${idx + 1}. ${service}\n`;
      });

      // Добавляем информацию о текущих услугах с полными названиями
      if (serviceNamesForTooltip.length > 0) {
        tooltipText += `\n📋 Текущие услуги (${serviceNamesForTooltip.length}):\n`;
        serviceNamesForTooltip.forEach((serviceName, idx) => {
          tooltipText += `• ${serviceName}\n`;
        });
      }
    } else {
      // Fallback: показываем только текущие услуги с полными названиями
      tooltipText = serviceNamesForTooltip.length > 1
        ? `Услуги:\n${serviceNamesForTooltip.map((serviceName, idx) => `${idx + 1}. ${serviceName}`).join('\n')}`
        : serviceNamesForTooltip[0] || '';
    }

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
              backgroundColor: withOpacity('var(--mac-accent-blue)', 0.12),
              color: 'var(--mac-accent-blue)',
              border: `1px solid ${withOpacity('var(--mac-accent-blue)', 0.25)}`
            }}
          >
            {code}
          </span>
        ))}
      </div>
    );
  }, [withOpacity, createServiceMapping, services]);

  // Рендер типа обращения
  const renderVisitType = useCallback((visitType) => {
    const typeColors = {
      paid: 'var(--mac-accent-blue)',
      repeat: 'var(--mac-success)',
      free: 'var(--mac-warning)',
      allfree: '#ff6b35' // ✅ Добавлено для AllFree (оранжевый цвет)
    };

    const typeText = t[visitType] || visitType;
    const color = typeColors[visitType] || 'var(--mac-text-secondary)';

    // ✅ ИСПРАВЛЕНО: Для allfree используем rgba напрямую, так как withOpacity работает только с CSS переменными
    const isAllFree = visitType === 'allfree';
    const backgroundColor = isAllFree
      ? 'rgba(255, 107, 53, 0.08)'
      : withOpacity(color, 0.08);
    const borderColor = isAllFree
      ? 'rgba(255, 107, 53, 0.2)'
      : withOpacity(color, 0.2);

    return (
      <span style={{
        padding: '3px 6px',
        borderRadius: '8px',
        fontSize: '11px',
        fontWeight: '600',
        backgroundColor: backgroundColor,
        color: color,
        border: `1px solid ${borderColor}`
      }}>
        {typeText}
      </span>
    );
  }, [themeColors, withOpacity, t]);

  // Рендер вида оплаты
  const renderPaymentType = useCallback((paymentType, paymentStatus) => {
    const paymentIcons = {
      cash: '💵',
      card: '💳',
      online: '🌐',
      free: '🆓' // ✅ Добавлено для all_free
    };

    const paymentColors = {
      cash: 'var(--mac-success)',
      card: 'var(--mac-accent-blue)',
      online: 'var(--mac-accent-blue)', // Используем accent вместо хардкоженного цвета
      free: 'var(--mac-warning)' // ✅ Добавлено для all_free
    };

    const statusColors = {
      paid: 'var(--mac-success)',
      pending: 'var(--mac-warning)',
      failed: 'var(--mac-error)'
    };

    const typeText = paymentType === 'free' ? (t.free || 'Бесплатно') : (t[paymentType] || paymentType);
    const icon = paymentIcons[paymentType] || '💰';
    const color = paymentColors[paymentType] || 'var(--mac-text-secondary)';
    const statusColor = statusColors[paymentStatus] || 'var(--mac-text-secondary)';

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
          backgroundColor: withOpacity(color, 0.08),
          color: color,
          border: `1px solid ${withOpacity(color, 0.2)}`
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
  }, [withOpacity, t]);

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
      // ✅ ИСПРАВЛЕНО: Используем queue_number (уже выбран для текущей вкладки в RegistrarPanel)
      // вместо отображения всех номеров из queue_numbers, что вызывало дублирование
      if (row.queue_number !== undefined && row.queue_number !== null) {
        // ✅ ИСПРАВЛЕНО: Используем статус из queue_number_status (соответствует текущей вкладке)
        // или ищем соответствующий queue_number в queue_numbers для получения его статуса
        let queueStatus = row.queue_number_status;
        if (!queueStatus && row.queue_numbers && Array.isArray(row.queue_numbers)) {
          // Ищем queue_number в queue_numbers и берём его статус
          const matchingQueue = row.queue_numbers.find(q => q.number === row.queue_number);
          if (matchingQueue) {
            queueStatus = matchingQueue.status;
          } else if (row.queue_numbers.length > 0) {
            // ✅ ИСПРАВЛЕНО: Если не нашли точное совпадение, используем статус из первого queue_number
            // вместо общего row.status, так как статусы отдельных очередей могут отличаться
            queueStatus = row.queue_numbers[0].status;
          }
        }
        // Fallback: используем общий статус записи только если queue_numbers отсутствует
        queueStatus = queueStatus || row.status || 'waiting';
        const statusConfig = {
          waiting: {
            bg: 'var(--mac-warning, #ff9500)',
            icon: '⏳',
            text: 'Ожидает',
            pulse: true
          },
          called: {
            bg: 'var(--mac-accent-blue, #007aff)',
            icon: '📢',
            text: 'Вызван',
            pulse: true
          },
          served: {
            bg: 'var(--mac-success, #34c759)',
            icon: '✅',
            text: 'Обслужен',
            pulse: false
          },
          no_show: {
            bg: 'var(--mac-error, #ff3b30)',
            icon: '❌',
            text: 'Не явился',
            pulse: false
          }
        };

        const config = statusConfig[queueStatus] || statusConfig.waiting;

        return (
          <span
            style={{
              padding: '4px 8px',
              backgroundColor: config.bg,
              color: 'var(--mac-text-primary)',
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: '700',
              minWidth: '32px',
              textAlign: 'center',
              display: 'inline-block',
              boxShadow: 'var(--mac-shadow-sm, 0 2px 4px rgba(0,0,0,0.1))'
            }}
            title={`№${row.queue_number}${row.queue_numbers?.length > 1 ? ` (${row.queue_numbers.length} очередей)` : ''}`}
          >
            {row.queue_number}
          </span>
        );
      }

      // Fallback: Если есть номера очередей, но нет queue_number - показываем первый
      if (row.queue_numbers && Array.isArray(row.queue_numbers) && row.queue_numbers.length > 0) {
        const firstQueue = row.queue_numbers[0];
        const queueStatus = firstQueue.status || row.status || 'waiting';
        const statusConfig = {
          waiting: {
            bg: 'var(--mac-warning, #ff9500)',
            icon: '⏳',
            text: 'Ожидает',
            pulse: true
          },
          called: {
            bg: 'var(--mac-accent-blue, #007aff)',
            icon: '📢',
            text: 'Вызван',
            pulse: true
          },
          served: {
            bg: 'var(--mac-success, #34c759)',
            icon: '✅',
            text: 'Обслужен',
            pulse: false
          },
          no_show: {
            bg: 'var(--mac-error, #ff3b30)',
            icon: '❌',
            text: 'Не явился',
            pulse: false
          }
        };

        const config = statusConfig[queueStatus] || statusConfig.waiting;

        return (
          <span
            style={{
              padding: '4px 8px',
              backgroundColor: config.bg,
              color: 'var(--mac-text-primary)',
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: '700',
              minWidth: '32px',
              textAlign: 'center',
              display: 'inline-block',
              boxShadow: 'var(--mac-shadow-sm, 0 2px 4px rgba(0,0,0,0.1))'
            }}
            title={`${firstQueue.queue_name || 'Очередь'}: №${firstQueue.number}${row.queue_numbers.length > 1 ? ` (${row.queue_numbers.length} очередей)` : ''}`}
          >
            {firstQueue.number}
          </span>
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
          backgroundColor: 'var(--mac-accent-blue)',
          color: 'var(--mac-text-primary)',
          borderRadius: '6px',
          fontSize: '14px',
          fontWeight: '700',
          minWidth: '32px',
          textAlign: 'center',
          display: 'inline-block',
          boxShadow: 'var(--mac-shadow-sm, 0 2px 4px rgba(0,0,0,0.1))'
        }}>
          {todayIndex}
        </span>
      );
    }

    // Для записей не на сегодня показываем дефолтный номер
    const fallbackIndex = data.findIndex(item => item.id === row.id) + 1;
    return (
      <span style={{
        color: 'var(--mac-text-secondary)',
        fontSize: '12px',
        padding: '2px 6px',
        backgroundColor: withOpacity('var(--mac-text-secondary)', 0.06),
        borderRadius: '4px'
      }}>
        #{fallbackIndex}
      </span>
    );
  }, [data, withOpacity]);


  // Инлайновый лоадер без раннего возврата
  const loaderNode = (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '60px',
      color: 'var(--mac-text-secondary)'
    }}>
      <div style={{ textAlign: 'center' }}>
        <div
          className="loading-spinner"
          style={{
            width: '40px',
            height: '40px',
            border: '3px solid var(--mac-border)',
            borderTop: '3px solid var(--mac-accent-blue)',
            borderRadius: '50%',
            margin: '0 auto 16px'
          }} />
        {t.loading}
      </div>
    </div>
  );

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
      <div style={{
        padding: '16px',
        borderBottom: '1px solid var(--mac-border)',
        overflowX: 'auto',
        minWidth: '600px'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          flexWrap: 'nowrap',
          minWidth: 0
        }}>
          {/* Поиск */}
          <div style={{ position: 'relative', minWidth: '200px', maxWidth: '300px', flex: '1 1 auto' }}>
            <MacOSInput
              type="text"
              placeholder={t.search}
              value={filterConfig.search}
              onChange={(e) => setFilterConfig(prev => ({ ...prev, search: e.target.value }))}
              icon={Search}
              style={{ width: '100%' }}
            />
          </div>

          {/* Фильтр по статусу */}
          <MacOSSelect
            value={filterConfig.status}
            onChange={(e) => setFilterConfig(prev => ({ ...prev, status: e.target.value }))}
            options={[
              { value: '', label: t.filter },
              { value: 'scheduled', label: t.scheduled },
              { value: 'confirmed', label: t.confirmed },
              { value: 'queued', label: t.queued },
              { value: 'in_cabinet', label: t.in_cabinet },
              { value: 'done', label: t.done },
              { value: 'cancelled', label: t.cancelled },
              { value: 'paid_pending', label: t.paid_pending },
              { value: 'paid', label: t.paid }
            ]}
            style={{ minWidth: '120px', maxWidth: '150px', flex: '0 0 auto' }}
          />

          {/* Экспорт */}
          <MacOSButton
            variant="outline"
            onClick={handleExport}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              flex: '0 0 auto',
              minWidth: '100px'
            }}
          >
            <Download size={16} />
            {t.export}
          </MacOSButton>

          {/* Информация о выбранных */}
          {showCheckboxes && selectedRows.size > 0 && (
            <MacOSBadge variant="info" style={{ flex: '0 0 auto' }}>
              {t.selected}: {selectedRows.size}
            </MacOSBadge>
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
            <tr>
              {/* Чекбокс для выбора всех */}
              {showCheckboxes && (
                <th style={{
                  padding: '12px 8px',
                  textAlign: 'left',
                  borderBottom: '1px solid var(--mac-border)',
                  width: '40px',
                  color: 'var(--mac-text-primary)'
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
                  borderBottom: '1px solid var(--mac-border)',
                  color: 'var(--mac-text-primary)',
                  fontWeight: '600',
                  fontSize: '14px',
                  width: '60px',
                  cursor: 'pointer',
                  userSelect: 'none'
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
                  borderBottom: '1px solid var(--mac-border)',
                  color: 'var(--mac-text-primary)',
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
                  borderBottom: '1px solid var(--mac-border)',
                  color: 'var(--mac-text-primary)',
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
                  borderBottom: '1px solid var(--mac-border)',
                  color: 'var(--mac-text-primary)',
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
                  borderBottom: '1px solid var(--mac-border)',
                  color: 'var(--mac-text-primary)',
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
                borderBottom: '1px solid var(--mac-border)',
                color: 'var(--mac-text-primary)',
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
                borderBottom: '1px solid var(--mac-border)',
                color: 'var(--mac-text-primary)',
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
                borderBottom: '1px solid var(--mac-border)',
                color: 'var(--mac-text-primary)',
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
                  borderBottom: '1px solid var(--mac-border)',
                  color: 'var(--mac-text-primary)',
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
                  borderBottom: '1px solid var(--mac-border)',
                  color: 'var(--mac-text-primary)',
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
                  borderBottom: '1px solid var(--mac-border)',
                  color: 'var(--mac-text-primary)',
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
                borderBottom: '1px solid var(--mac-border)',
                color: 'var(--mac-text-primary)',
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
                    color: 'var(--mac-text-secondary)',
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
                    backgroundColor: selectedRows.has(row.id)
                      ? withOpacity('var(--mac-accent-blue)', 0.06)
                      : (index % 2 === 0 ? 'var(--mac-bg-primary)' : 'var(--mac-bg-secondary)'),
                    borderBottom: '1px solid var(--mac-border)',
                    cursor: 'pointer'
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
                    color: 'var(--mac-text-secondary)',
                    fontSize: '14px'
                  }}>
                    {renderQueueNumbers(row)}
                  </td>

                  {/* Пациент */}
                  <td style={{
                    padding: '12px 8px',
                    color: 'var(--mac-text-primary)',
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
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        <span>{row.patient_fio || '—'}</span>
                        {/* Ярлыки источника/приоритета */}
                        {row.source === 'online' && (
                          <span
                            style={{
                              fontSize: '10px',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                              color: 'white',
                              fontWeight: '600',
                              whiteSpace: 'nowrap'
                            }}
                            title="Приоритет: ранняя онлайн-регистрация"
                          >
                            QR
                          </span>
                        )}
                        {row.source === 'desk' && (
                          <span
                            style={{
                              fontSize: '10px',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              background: 'var(--mac-separator)',
                              color: 'var(--mac-text-secondary)',
                              fontWeight: '600',
                              whiteSpace: 'nowrap'
                            }}
                          >
                            Manual
                          </span>
                        )}
                      </div>
                      {row.patient_birth_year && (
                        <div style={{
                          fontSize: '12px',
                          color: 'var(--mac-text-secondary)',
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
                      color: 'var(--mac-text-primary)',
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
                        <Phone size={18} style={{ color: 'var(--mac-accent-blue)', fontWeight: 'bold', filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.1))' }} />
                        {formatPhoneNumber(row.patient_phone)}
                      </div>
                    </td>
                  )}

                  {/* Год рождения */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    color: 'var(--mac-text-primary)',
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
                      color: 'var(--mac-text-primary)',
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
                            color: 'var(--mac-accent-blue)',
                            fontWeight: 'bold',
                            filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.1))',
                            flexShrink: 0
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
                      // ✅ ИСПРАВЛЕНО: Проверяем и discount_mode, и approval_status для all_free
                      const discountMode = row.discount_mode;
                      const isAllFreeApproved = discountMode === 'all_free' && row.approval_status === 'approved';

                      if (discountMode === 'benefit') return 'free';
                      if (discountMode === 'repeat') return 'repeat';
                      // ✅ ИСПРАВЛЕНО: Для AllFree возвращаем 'allfree' вместо 'free'
                      if (isAllFreeApproved || discountMode === 'all_free') return 'allfree';
                      return 'paid';
                    })())}
                  </td>

                  {/* Услуги */}
                  <td style={{
                    padding: '12px 8px',
                    minWidth: '180px'
                  }}>
                    {renderServices(row.services, row.all_patient_services)}
                  </td>

                  {/* Вид оплаты */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    minWidth: '100px'
                  }}>
                    {renderPaymentType(
                      // ✅ ИСПРАВЛЕНО: Для all_free (одобренных или нет) используем 'free', иначе payment_type или 'cash'
                      (() => {
                        const discountMode = row.discount_mode;
                        const approvalStatus = row.approval_status;
                        // Если discount_mode = 'all_free', показываем как 'free' независимо от approval_status
                        // (так как пользователь уже выбрал all_free при редактировании)
                        if (discountMode === 'all_free') {
                          return 'free';
                        }
                        return row.payment_type || 'cash';
                      })(),
                      row.payment_status
                    )}
                  </td>

                  {/* Дата и время регистрации */}
                  <td style={{
                    padding: '12px 8px',
                    textAlign: 'center',
                    color: 'var(--mac-text-primary)',
                    fontSize: '14px',
                    minWidth: '100px'
                  }}>
                    <div>
                      {/* Дата и время регистрации */}
                      {row.created_at ? (
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', justifyContent: 'center' }}>
                            <Calendar size={12} style={{ color: 'var(--mac-text-secondary)' }} />
                            {new Date(row.created_at).toLocaleDateString('ru-RU')}
                          </div>
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            justifyContent: 'center',
                            marginTop: '2px',
                            fontSize: '12px',
                            color: 'var(--mac-text-secondary)'
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
                            <Calendar size={12} style={{ color: 'var(--mac-text-secondary)' }} />
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
                              color: 'var(--mac-text-secondary)'
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
                    color: (() => {
                      // ✅ ИСПРАВЛЕНИЕ #3: Цвет зависит от реальной стоимости (cost из VisitService)
                      const discountMode = row.discount_mode;
                      const isAllFreeApproved = discountMode === 'all_free' && row.approval_status === 'approved';
                      if (isAllFreeApproved) return 'var(--mac-warning)';

                      // ⭐ Используем ту же логику что и в отображении
                      let amount = 0;
                      if (row.has_shared_invoice) {
                        amount = row.cost || 0;
                      } else {
                        amount = row.cost || row.invoice_amount || row.payment_amount || 0;
                      }

                      return amount > 0 ? 'var(--mac-success, #34c759)' : 'var(--mac-text-secondary)';
                    })(),
                    fontSize: '14px',
                    fontWeight: '600',
                    minWidth: '90px'
                  }}>
                    {(() => {
                      // ✅ ИСПРАВЛЕНИЕ #3: Правильный приоритет отображения цен
                      // 1. cost из VisitService (реальная цена с учётом скидок из wizard)
                      // 2. invoice_amount (только если НЕ shared invoice)
                      const discountMode = row.discount_mode;

                      // Показываем "Бесплатно" если discount_mode = 'all_free'
                      if (discountMode === 'all_free') {
                        return 'Бесплатно';
                      }

                      // ⭐ НОВАЯ ЛОГИКА: Приоритет cost, затем invoice_amount (если не shared)
                      let amount = 0;
                      if (row.has_shared_invoice) {
                        // Для shared invoice используем ТОЛЬКО cost (не показываем сумму всего invoice)
                        amount = row.cost || 0;
                      } else {
                        // Для обычных случаев: приоритет cost, fallback invoice_amount
                        amount = row.cost || row.invoice_amount || row.payment_amount || 0;
                      }

                      // Если есть сумма - показываем, иначе "—"
                      return amount > 0 ? `${amount.toLocaleString()} сум` : '—';
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
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '4px',
                        flexWrap: 'wrap',
                        position: 'relative',
                        zIndex: 100
                      }}
                      onClick={(e) => {
                        // Блокируем клик на строку при клике в контейнере действий
                        e.stopPropagation();
                      }}
                      onMouseDown={(e) => {
                        // Блокируем mousedown на строку при клике в контейнере действий
                        e.stopPropagation();
                      }}
                    >
                      {/* В режиме панели врача кнопки оплаты не показываем */}
                      {!isDoctorView && (() => {
                        const status = (row.status || '').toLowerCase();
                        const paymentStatus = (row.payment_status || '').toLowerCase();
                        return (
                          status === 'paid_pending' ||
                          paymentStatus === 'pending' ||
                          (status === 'scheduled' && paymentStatus !== 'paid') ||
                          (status === 'confirmed' && paymentStatus !== 'paid') ||
                          (status === 'waiting' && paymentStatus !== 'paid') ||
                          (status === 'queued' && paymentStatus !== 'paid') ||
                          (!paymentStatus && status !== 'paid' && status !== 'done' && status !== 'served' && status !== 'completed' && status !== 'cancelled')
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
                              backgroundColor: 'var(--mac-success, #34c759)',
                              color: 'var(--mac-text-primary)',
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
                      {(isDoctorView ? (row.status === 'queued' || row.status === 'waiting' || row.payment_status === 'paid') : (row.status === 'queued' || row.status === 'waiting')) && (
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
                            backgroundColor: 'var(--mac-success, #34c759)',
                            color: 'var(--mac-text-primary)',
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
                      {(row.payment_status === 'paid' || row.status === 'queued' || row.status === 'waiting') && (
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
                            color: 'var(--mac-accent-blue)',
                            cursor: 'pointer',
                            pointerEvents: 'auto'
                          }}
                          title="Печать"
                        >
                          <FileText size={14} />
                        </button>
                      )}

                      {/* Завершить */}
                      {(row.status === 'in_cabinet' || row.status === 'called') && (
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
                            backgroundColor: 'var(--mac-success, #34c759)',
                            color: 'var(--mac-text-primary)',
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
                          logger.log('[EnhancedAppointmentsTable] Кнопка Просмотр нажата:', row);
                          if (onActionClick) {
                            onActionClick('view', row, e);
                          }
                        }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          // Дублируем обработчик для надежности
                          if (onActionClick) {
                            onActionClick('view', row, e);
                          }
                        }}
                        style={{
                          padding: '4px',
                          border: 'none',
                          borderRadius: '4px',
                          backgroundColor: 'transparent',
                          color: 'var(--mac-text-secondary)',
                          cursor: 'pointer',
                          pointerEvents: 'auto',
                          position: 'relative',
                          zIndex: 101
                        }}
                        title="Просмотр"
                      >
                        <Eye size={14} />
                      </button>

                      {/* Редактировать */}
                      <button
                        className="action-button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          logger.log('[EnhancedAppointmentsTable] Кнопка Редактировать нажата:', row);
                          if (onActionClick) {
                            onActionClick('edit', row, e);
                          }
                        }}
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          // Дублируем обработчик для надежности
                          if (onActionClick) {
                            onActionClick('edit', row, e);
                          }
                        }}
                        style={{
                          padding: '4px',
                          border: 'none',
                          borderRadius: '4px',
                          backgroundColor: 'transparent',
                          color: 'var(--mac-text-secondary)',
                          cursor: 'pointer',
                          pointerEvents: 'auto',
                          position: 'relative',
                          zIndex: 101
                        }}
                        title="Редактировать"
                      >
                        <Edit size={14} />
                      </button>

                      {/* Просмотр EMR (только для завершённых записей) */}
                      {(row.status === 'served' || row.status === 'completed' || row.status === 'done' ||
                        (row.status === 'in_visit' && row.payment_status === 'paid')) && (
                          <button
                            className="action-button"
                            onMouseDown={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              onActionClick?.('view_emr', row, e);
                            }}
                            style={{
                              padding: '4px',
                              border: 'none',
                              borderRadius: '4px',
                              backgroundColor: 'transparent',
                              color: 'var(--mac-accent-blue, #007aff)',
                              cursor: 'pointer',
                              pointerEvents: 'auto'
                            }}
                            title="Просмотр EMR"
                          >
                            <FileText size={14} />
                          </button>
                        )}

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
                          color: 'var(--mac-text-secondary)',
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
                            backgroundColor: 'var(--mac-accent-blue, #007aff)',
                            color: 'var(--mac-text-primary)',
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
          borderTop: '1px solid var(--mac-border)',
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
            color: 'var(--mac-text-secondary)',
            fontSize: '14px'
          }}>
            <span>{t.page}</span>
            <select
              value={currentPage}
              onChange={(e) => setCurrentPage(parseInt(e.target.value))}
              style={{
                padding: '4px 8px',
                border: '1px solid var(--mac-border)',
                borderRadius: '4px',
                backgroundColor: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
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
            color: 'var(--mac-text-secondary)',
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
                border: '1px solid var(--mac-border)',
                borderRadius: '6px',
                backgroundColor: 'var(--mac-bg-primary)',
                color: currentPage === 1 ? 'var(--mac-text-secondary)' : 'var(--mac-text-primary)',
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
                border: '1px solid var(--mac-border)',
                borderRadius: '6px',
                backgroundColor: 'var(--mac-bg-primary)',
                color: currentPage === totalPages ? 'var(--mac-text-secondary)' : 'var(--mac-text-primary)',
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

