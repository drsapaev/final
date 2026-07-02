import { useState, useEffect, useCallback, useRef, useMemo, memo, startTransition } from 'react';
import PropTypes from 'prop-types';
import { useSearchParams, useLocation, useNavigate } from 'react-router-dom';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import AppointmentContextMenu from '../components/tables/AppointmentContextMenu';
import ModernTabs from '../components/navigation/ModernTabs';
import {
  Button, Card, CardHeader, CardContent, Badge, Icon, Input,
} from '../components/ui/macos';
import { AnimatedTransition, AnimatedLoader } from '../components/ui';
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import { useTheme } from '../contexts/ThemeContext';
import '../components/ui/animations.css';
import '../styles/responsive.css';
import '../styles/animations.css';
import '../styles/dark-theme-visibility-fix.css';
// DS-3: utility classes for common inline style patterns
import './registrar/registrar.css';
import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';
// Note: getApiOrigin moved to ./registrar/registrarHelpers.js (decomp step 1)
import notify from '../services/notify';
import RoleNotificationCenter from '../components/notifications/RoleNotificationCenter';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../components/common/ConfirmDialog';
// QW-06 fix: translations extracted to separate file (was 50+ inline keys).
import { getRegistrarTranslator } from './registrarTranslations';
// Decomp 2: hotkeys extracted to useRegistrarHotkeys hook
import { useRegistrarHotkeys } from './registrar/useRegistrarHotkeys';
// Decomp 3: reschedule helpers extracted to useRegistrarReschedule hook
import { useRegistrarReschedule } from './registrar/useRegistrarReschedule';
// Decomp 4: data-loading functions extracted to useRegistrarData hook
import { useRegistrarData } from './registrar/useRegistrarData';
// Decomp 5: record action handlers extracted to useRegistrarActions hook
import { useRegistrarActions } from './registrar/useRegistrarActions';
// Decomp 6a: QueueView extracted to component
import QueueView from './registrar/views/QueueView';
// Strategic Direction 3: navigation helpers for canonical nested routes
import { getViewFromPath } from './registrar/registrarNavigation';

// Decomp step 1: helpers extracted to ./registrar/registrarHelpers.js
import {
  API_BASE,
  REGISTRAR_TAB_LABEL_KEYS,
  REGISTRAR_STATUS_LABEL_KEYS,
  registrarWorkflowHeaderStyle,
  registrarWorkflowTitleStyle,
  registrarWorkflowMetaStyle,
  registrarWorkflowActionsStyle,
  normalizePatientGender,
  formatPreviewList,
  buildPostWizardPaymentRow,
  isMultiRecordAggregateRow,
} from './registrar/registrarHelpers';


// Современные диалоги
import PaymentDialog from '../components/dialogs/PaymentDialog';
import CancelDialog from '../components/dialogs/CancelDialog';
import PrintDialog from '../components/dialogs/PrintDialog';
import ModernDialog from '../components/dialogs/ModernDialog';
import { printPanelTicketInBrowserAsync } from '../services/panelPrint';

// Современный мастер
// ✅ Используется только новый мастер (V2)
import AppointmentWizardV2 from '../components/wizard/AppointmentWizardV2';
import PaymentManager from '../components/payment/PaymentManager';

// Современная очередь
import ModernQueueManager from '../components/queue/ModernQueueManager';

// Современная статистика
import ModernStatistics from '../components/statistics/ModernStatistics';

// Модальное окно редактирования пациента
// ✨ ЗАКОММЕНТИРОВАНО: Теперь используется AppointmentWizardV2 для редактирования
// import EditPatientModal from '../components/common/EditPatientModal';

// Утилиты для работы с датами
import { getLocalDateString, getYesterdayDateString } from '../utils/dateUtils';
import { rescheduleTomorrow, rescheduleVisit } from '../api/visits';
// Note: formatNetworkErrorMessage + isNetworkFetchError moved to useRegistrarData.js (Decomp 4)
import { getErrorMessage } from '../utils/errorHandler';
import {
  aggregatePatientsForAllDepartments as aggregateRegistrarPatients,
  sortRegistrarRowsForPresentation
} from '../utils/registrarAggregation';

// ⭐ SSOT: Centralized service code resolver
import { toServiceCode as ssotToServiceCode } from '../utils/serviceCodeResolver';

// API client
import { api } from '../api/client';
// ⭐ BATCH API: Для атомарных операций с записями пациента (см. BATCH_UPDATE_ARCHITECTURE.md)


// ✅ Форс-мажор модальное окно
import ForceMajeureModal from '../components/registrar/ForceMajeureModal';

const RegistrarPanel = () => {
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirm, confirmDialog] = useConfirm();
  // Рендер компонента (debug отключен)
  // Адаптивные хуки
  const { isMobile, isTablet } = useBreakpoint();

  // Основные состояния
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  // R-02 fix: activeTab синхронизирован с URL (?dept=...).
  // Раньше был useState(null) — F5 сбрасывал выбранное отделение.
  const [activeTab, setActiveTabRaw] = useState(() => searchParams.get('dept') || null);
  const setActiveTab = useCallback((tab) => {
    setActiveTabRaw(tab);
    // R-02: пишем в URL для shareable links + back button
    const params = new URLSearchParams(window.location.search);
    if (tab) {
      params.set('dept', tab);
    } else {
      params.delete('dept');
    }
    setSearchParams(params, { replace: true });
  }, [setSearchParams]);
  const currentView = useMemo(() => {
    // Strategic Direction 3: prefer canonical path-derived view
    // (/registrar/welcome, /registrar/queue) over legacy ?view= query param.
    const pathView = getViewFromPath(location.pathname);
    if (pathView) return pathView;

    // Backward compatibility: legacy ?view= query param
    const explicitView = searchParams.get('view');
    if (explicitView === 'welcome' || explicitView === 'queue') {
      return explicitView;
    }

    const legacyTab = searchParams.get('tab');
    if (legacyTab === 'welcome' || legacyTab === 'queue') {
      return legacyTab;
    }

    return explicitView;
  }, [searchParams, location.pathname]);
  const searchQuery = useMemo(() => (searchParams.get('q') || '').toLowerCase(), [searchParams]);
  const statusFilter = useMemo(() => searchParams.get('status'), [searchParams]);
  const todayStr = getLocalDateString();

  // ✅ Получаем patientId из URL для автоматического поиска
  const patientIdFromUrl = useMemo(() => {
    const id = searchParams.get('patientId');
    return id ? parseInt(id, 10) : null;
  }, [searchParams]);

  // ✅ Эффект для автоматической загрузки пациента из URL
  useEffect(() => {
    const loadPatientFromUrl = async () => {
      if (!patientIdFromUrl) return;

      try {
        const token = tokenManager.getAccessToken();
        if (!token) return;

        const response = await fetch(`${API_BASE}/api/v1/patients/${patientIdFromUrl}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
          const patientData = await response.json();
          const patientName = `${patientData.last_name || ''} ${patientData.first_name || ''}`.trim();

          // Устанавливаем поисковый запрос с именем пациента
          setSearchParams((prev) => {
            const newParams = new URLSearchParams(prev);
            newParams.set('q', patientName);
            return newParams;
          });

          logger.info('[Registrar] Загружен пациент из URL:', patientName);
        }
      } catch (error) {
        logger.error('[Registrar] Не удалось загрузить пациента:', error);
      }
    };

    loadPatientFromUrl();
  }, [patientIdFromUrl, setSearchParams]);

  // ✅ ДИНАМИЧЕСКИЕ ОТДЕЛЕНИЯ: состояние для хранения отделений из БД
  const [dynamicDepartments, setDynamicDepartments] = useState([]);

  // ⭐ SSOT: Queue profiles loaded from API (via ModernTabs)
  // Used for filtering entries by queue_tags instead of hardcoded mapping
  const [queueProfiles, setQueueProfiles] = useState([]);

  // Состояния для печати
  const [printDialog, setPrintDialog] = useState({ open: false, type: 'ticket', data: null });void
  useState(null);
  const [cancelDialog, setCancelDialog] = useState({ open: false, row: null, reason: '' });
  const [paymentDialog, setPaymentDialog] = useState({ open: false, row: null, paid: false, source: null });
  const [recordPreviewDialog, setRecordPreviewDialog] = useState({ open: false, row: null });
  // ✅ State for rescheduling
  const [rescheduleData, setRescheduleData] = useState(null);

  // ✅ State for Force Majeure modal
  const [forceMajeureModal, setForceMajeureModal] = useState({ open: false, specialistId: null, specialistName: '' });

  const [contextMenu, setContextMenu] = useState({ open: false, row: null, position: { x: 0, y: 0 } });

  // Состояния для пагинации
  const [paginationInfo, setPaginationInfo] = useState({ total: 0, hasMore: false, loadingMore: false });
  // QW-03 fix: demoAppointments useMemo (260 lines) removed.
  // Production code should never ship demo data. Backend fixtures
  // are used for tests; error states show proper error UI instead.

  // Состояния для управления данными
  const [appointments, setAppointments] = useState([]);
  // ⭐ SSOT FIX: Сырые данные (flat list) до агрегации — для Tooltip
  const [dataSource, setDataSource] = useState('loading'); // 'loading' | 'api' | 'error' (QW-03: 'demo' removed)
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  // QW-01 fix: bulk-action state removed — checkboxes were already disabled
  // (showCheckboxes=false) and the bulk-action bar was unreachable via UI.
  // Only hidden Ctrl+A/Alt+1-3 hotkeys could populate this state, creating
  // dead UI that surfaced unexpectedly. See audit P-011.
  const appointmentsCount = appointments.length;
  // ✅ Используется только новый мастер (V2)
  const [showWizard, setShowWizard] = useState(false);
  const [wizardEditMode, setWizardEditMode] = useState(false); // ✨ НОВОЕ: Режим редактирования
  const [wizardInitialData, setWizardInitialData] = useState(null); // ✨ НОВОЕ: Данные для редактирования
  const [showPaymentManager, setShowPaymentManager] = useState(false); // Для модуля оплаты
  const [isProcessing, setIsProcessing] = useState(false); // Состояние обработки


  // Отладка состояния мастера удалена - используется AppointmentWizard

  // Отладка состояния загрузки
  useEffect(() => {




    // logger.info('⏳ appointmentsLoading changed:', appointmentsLoading);
  }, [appointmentsLoading]); // Отладка изменений appointments
  useEffect(() => {





































































































































































































      // logger.info('📋 appointments changed, count:', appointments.length);
      // if (appointments.length > 0) {
      //   logger.info('📋 Первая запись в состоянии:', appointments[0]);
      // }
      // Тестируем агрегацию пациентов при изменении данных (debug отключен)
      /*if (appointments.length > 0) {
        setTimeout(() => {
          logger.info('🧪 Тестирование агрегации пациентов:');
          logger.info('Исходные записи:', appointments.length);
           // Простая функция агрегации для тестирования
          const patientGroups = {};
          appointments.forEach(appointment => {
            const patientKey = appointment.patient_fio;
            if (!patientGroups[patientKey]) {
              patientGroups[patientKey] = {
                patient_fio: appointment.patient_fio,
                services: [],
                departments: new Set(),
                cost: 0 // Общая стоимость
              };
            }
             // Суммируем стоимость
            if (appointment.cost) {
              patientGroups[patientKey].cost += appointment.cost;
            }
             if (appointment.services && Array.isArray(appointment.services)) {
              appointment.services.forEach(service => {
                if (!patientGroups[patientKey].services.includes(service)) {
                  patientGroups[patientKey].services.push(service);
                }
              });
            }
            if (appointment.department) {
              patientGroups[patientKey].departments.add(appointment.department);
            }
          });
           const aggregated = Object.values(patientGroups);
          logger.info('После агрегации:', aggregated.length);
           // Находим первого пациента для тестирования
          const firstPatient = aggregated[0];
          if (firstPatient) {
            logger.info('Первый пациент после агрегации:', firstPatient.patient_fio);
            logger.info('Количество услуг:', firstPatient.services.length);
            logger.info('Услуги:', firstPatient.services);
            logger.info('Отделения:', Array.from(firstPatient.departments));
            logger.info('Общая стоимость:', firstPatient.cost);
          }
        }, 100);
      }*/}, [appointments]); // Убираем дублирование - filteredAppointments уже определена ниже в коде
  const [showSlotsModal, setShowSlotsModal] = useState(false);
  // QW-02 fix: hold the date the user picks in the inline date input inside the
  // reschedule slots dialog. Replaces the previous window.prompt() call that was
  // jarring, blocking, and lacked a date picker.
  const [customRescheduleDate, setCustomRescheduleDate] = useState('');
  const autoRefresh = true; // Новые состояния для интеграции с админ панелью
  // Decomp 3: reschedule helpers extracted to useRegistrarReschedule hook
  const {
    resolveRescheduleVisitId,
    removeRescheduledAppointmentFromView,
  } = useRegistrarReschedule({ setAppointments });
  const [doctors, setDoctors] = useState([]);const [services, setServices] = useState({});const [showCalendar, setShowCalendar] = useState(false);const [historyDate, setHistoryDate] = useState(getLocalDateString());const [tempDateInput, setTempDateInput] = useState(getLocalDateString());const language = useMemo(() => localStorage.getItem('ui_lang') || 'ru', []); // Выбор врача остаётся явным: URL-параметр или ручной выбор в очереди
  // QW-06 fix: translations moved to ./registrarTranslations.js (was 50+ inline keys).
  // EN translations added (previously missing — EN users saw RU fallback).
  // Full migration to locales/{ru,uz,en}.js deferred until useTranslation.jsx
  // is refactored to use centralized locale files (see audit §8, Direction 3).
  const t = useMemo(() => getRegistrarTranslator(language), [language]);
  const currentWorklistLabel = t(REGISTRAR_TAB_LABEL_KEYS[activeTab] || 'tabs_appointments');
  const statusFilterLabel = statusFilter ? t(REGISTRAR_STATUS_LABEL_KEYS[statusFilter] || statusFilter) : null;
  const { theme, isDark, getSpacing, getFontSize, getColor } = useTheme();
  // Адаптивные цвета из централизованной системы темизации
  // DS-2 fix: replaced --color-* variables with --mac-* canonical tokens
  const cardBg = isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)';
  const textColor = 'var(--mac-text-primary)';
  const borderColor = isDark ? 'var(--mac-border)' : 'var(--mac-border-secondary)';
  const accentColor = 'var(--mac-accent-blue)';

  // Используем централизованную типографику и отступы
  // Используем CSS переменные вместо getSpacing и getColor

  const pageStyle = {
    padding: '0',
    maxWidth: 'none',
    margin: '0',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    fontSize: isMobile ? 'var(--mac-font-size-sm)' : isTablet ? 'var(--mac-font-size-base)' : 'var(--mac-font-size-lg)',
    fontWeight: 400,
    lineHeight: 1.5,
    background: 'var(--mac-gradient-window)',
    color: 'var(--mac-text-primary)',
    minHeight: '100vh',
    position: 'relative',
    transition: 'background var(--mac-duration-normal) var(--mac-ease)'
  };

  // Контейнер таблицы, визуально "сливается" с вкладками
  const tableContainerStyle = {
    background: theme === 'light' ?
    'rgba(255, 255, 255, 0.98)' :
    'rgba(15, 23, 42, 0.8)',
    backdropFilter: 'blur(20px)',
    color: textColor,
    borderLeft: `1px solid ${theme === 'light' ? 'rgba(0, 0, 0, 0.15)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderRight: `1px solid ${theme === 'light' ? 'rgba(0, 0, 0, 0.15)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderBottom: `1px solid ${theme === 'light' ? 'rgba(0, 0, 0, 0.15)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderTop: `1px solid ${theme === 'light' ? 'rgba(0, 0, 0, 0.08)' : 'rgba(255, 255, 255, 0.05)'}`,
    borderRadius: '0 0 20px 20px',
    margin: '0 20px 20px 20px',
    boxShadow: theme === 'light' ?
    '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)' :
    '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
    overflow: 'hidden'
  };

  // Содержимое контейнера таблицы без верхнего внутреннего отступа
  const tableContentStyle = {
    padding: '0',
    color: textColor
  };

  // QW-01 cleanup: buttonStyle and buttonSecondaryStyle removed (were unused
  // dead code — 32 lines of inline styles that bypassed the macOS design
  // system canonical Button component). See audit §5.5, §5.6.


  // Decomp 4: data-loading functions extracted to useRegistrarData hook.
  // loadAppointments and loadMoreAppointments remain inline due to complex
  // ref dependencies (loadAppointmentsInFlightRef, autoRefreshCooldownUntilRef,
  // autoRefreshCooldownLoggedRef, filteredAppointmentsRef).
  const {
    loadIntegratedData,
    enrichAppointmentsWithPatientData,
  } = useRegistrarData({
    setDoctors,
    setServices,
    setDynamicDepartments,
  });


  // Улучшенная загрузка записей с поддержкой тихого режима
  const loadAppointments = useCallback(async (options = {}) => {
    // console.log('📥 loadAppointments called at:', new Date().toISOString(), options);
    const { silent = false } = options || {};
    const callSource = String(options?.source || 'unknown');
    const isAutoRefreshCall = callSource === 'auto_refresh';
    if (isAutoRefreshCall) {
      const cooldownUntil = autoRefreshCooldownUntilRef.current;
      if (Date.now() < cooldownUntil) {
        if (!autoRefreshCooldownLoggedRef.current) {
          logger.info('⏳ Автообновление приостановлено после rate limit', {
            cooldownUntil: new Date(cooldownUntil).toISOString()
          });
          autoRefreshCooldownLoggedRef.current = true;
        }
        return;
      }

      if (loadAppointmentsInFlightRef.current) {
        logger.info('⏭️ Автообновление пропущено: предыдущий запрос еще выполняется');
        return;
      }
    }

    loadAppointmentsInFlightRef.current = true;
    try {
      if (!silent) {
        setAppointmentsLoading(true);
        setDataSource('loading');
      }

      // Проверяем наличие токена
      const token = tokenManager.getAccessToken();
      // console.log('🔍 loadAppointments: token exists:', !!token);
      if (!token) {
        logger.warn('Токен аутентификации отсутствует, показываем пустое состояние');
        startTransition(() => {
          if (!silent) setDataSource('api');
          setAppointments([]);
        });
        return;
      }


      // console.log('🔍 loadAppointments: making request');


      // Используем новый эндпоинт для получения очередей на указанную дату
      // Если календарь открыт, используем historyDate, иначе сегодня
      const urlDate = searchParams.get('date');
      const dateParam = showCalendar && historyDate ? historyDate : urlDate || getLocalDateString();
      /* console.log('📅 Параметры для loadAppointments:', {
        source: callSource,
        showCalendar,
        historyDate,
        dateParam,
        activeTab
      }); */

      const params = new URLSearchParams();
      params.append('target_date', dateParam);



      // console.log('🔍 loadAppointments: requesting with params:', { target_date: dateParam });


      const response = await api.get('/registrar/queues/today', { params: { target_date: dateParam } });

      // Axios successful response
      const data = response.data;

      // Новый формат: данные сгруппированы по специальностям
      let appointmentsData = [];

      if (data && typeof data === 'object') {
        // Временно отключено логирование больших объектов для диагностики
        // logger.info('📊 Получены данные от сервера:', data);
        // console.log('📊 Получены данные от сервера (count):', data.queues?.length || 0);


        // Обрабатываем формат от эндпоинта registrar_integration.py
        if (data.queues && Array.isArray(data.queues)) {
          // console.log('📊 Обрабатываем формат очередей:', data.queues.length, 'очередей');
          // ✅ ОТЛАДКА: Логируем структуру данных от сервера
          /*data.queues.forEach((q, idx) => {
            logger.info(`  Очередь ${idx + 1}: specialty=${q.specialty}, entries=${q.entries?.length || 0}`);
            if (q.entries && q.entries.length > 0) {
              q.entries.slice(0, 2).forEach((e, eIdx) => {
                const entryData = e.data || e;
                logger.info(`    Запись ${eIdx + 1}: type=${e.type}, id=${entryData?.id}, patient_id=${entryData?.patient_id}, patient_name=${entryData?.patient_name}`);
              });
            }
          });*/


          // ⭐ SSOT: Simple flatMap - no deduplication, no aggregation
          // Each backend entry = one frontend row
          // Removed: appointmentsMap, mergedByPatientKey, getAppointmentKey, calcPriority, mergeAppointments

          // Minimal field adaptation layer
          const adaptEntry = (entry, queue) => {
            const fullEntry = entry.data || entry;
            const entryId = fullEntry?.id;
            if (!entryId) return null; // Skip entries without ID

            const queueNum = fullEntry.queue_position ?? fullEntry.number ?? 0;
            const queueTag = fullEntry.queue_tag ?? queue.queue_tag ?? queue.specialty ?? null;
            const queueName = fullEntry.queue_name ?? queue.specialist_name ?? queue.specialty ?? null;
            const queueTime = entry.queue_time || fullEntry.queue_time || fullEntry.created_at || null;
            const canonicalStatus = fullEntry.canonical_status ?? fullEntry.queue_status ?? fullEntry.status ?? null;

            return {
              // SSOT passthrough
              id: entryId,
              canonical_record_id: fullEntry.canonical_record_id ?? entry.canonical_record_id ?? entryId,
              record_kind: fullEntry.record_kind ?? entry.record_kind ?? null,
              source_kind: fullEntry.source_kind ?? entry.source_kind ?? null,
              visit_id: fullEntry.visit_id || entry.visit_id || null,
              appointment_id: fullEntry.appointment_id || entry.appointment_id || null,
              queue_entry_id: fullEntry.queue_entry_id || entry.queue_entry_id || null,
              patient_id: fullEntry.patient_id || entry.patient_id,
              patient_fio: fullEntry.patient_fio ?? fullEntry.patient_name ?? entry.patient_fio ?? entry.patient_name ?? 'Неизвестный пациент',
              patient_birth_year: fullEntry.patient_birth_year ?? fullEntry.birth_year ?? entry.patient_birth_year ?? entry.birth_year ?? null,
              patient_phone: fullEntry.patient_phone ?? fullEntry.phone ?? entry.patient_phone ?? entry.phone ?? '',
              patient_gender: normalizePatientGender(fullEntry) ?? normalizePatientGender(entry),
              gender: normalizePatientGender(fullEntry) ?? normalizePatientGender(entry),
              sex: normalizePatientGender(fullEntry) ?? normalizePatientGender(entry),
              address: fullEntry.address ?? entry.address ?? '',
              services: Array.isArray(fullEntry.services) ? fullEntry.services : [],
              service_codes: Array.isArray(fullEntry.service_codes) ? fullEntry.service_codes : [],
              service_details: Array.isArray(fullEntry.service_details) ? fullEntry.service_details : [],
              cost: fullEntry.cost || 0,
              payment_status: fullEntry.payment_status ?? null,
              source: fullEntry.source || entry.source || 'desk',
              status: canonicalStatus,
              canonical_status: fullEntry.canonical_status ?? canonicalStatus,
              queue_status: fullEntry.queue_status ?? canonicalStatus,
              record_type: fullEntry.record_type ?? fullEntry.type ?? entry.record_type ?? entry.type ?? null,
              created_at: fullEntry.created_at || null,
              queue_time: queueTime,
              updated_at: fullEntry.updated_at || fullEntry.last_changed_at || null,
              last_changed_at: fullEntry.last_changed_at || fullEntry.updated_at || null,
              display_time_kind: fullEntry.display_time_kind || (fullEntry.queue_time ? 'queue_time' : 'created_at'),
              timezone: fullEntry.timezone || data.timezone || 'Asia/Tashkent',
              discount_mode: fullEntry.discount_mode ?? null,
              approval_status: fullEntry.approval_status || null,
              available_actions: Array.isArray(fullEntry.available_actions) ? fullEntry.available_actions : [],
              can_mark_paid: Boolean(fullEntry.can_mark_paid),
              can_start_visit: Boolean(fullEntry.can_start_visit),
              can_cancel: Boolean(fullEntry.can_cancel),
              can_print_ticket: Boolean(fullEntry.can_print_ticket),
              can_complete: Boolean(fullEntry.can_complete),

              // Queue info
              queue_number: queueNum,
              queue_numbers: [{
                number: queueNum,
                queue_tag: queueTag,
                queue_name: queueName,
                specialty: queueTag,
                status: canonicalStatus,
                queue_time: queueTime,
                updated_at: fullEntry.updated_at || fullEntry.last_changed_at || null,
                last_changed_at: fullEntry.last_changed_at || fullEntry.updated_at || null,
                timezone: fullEntry.timezone || data.timezone || 'Asia/Tashkent'
              }],
              specialty: queueTag,
              queue_tag: queueTag,
              queue_name: queueName,
              department: fullEntry.department ?? queueTag,
              department_key: fullEntry.department_key || null,

              // Derived fields (minimal)
              visit_type: fullEntry.visit_type ?? fullEntry.discount_mode ?? null,
              payment_type: fullEntry.payment_type ?? null,
              date: fullEntry.date ?? data.date ?? dateParam,
              appointment_date: fullEntry.appointment_date ?? data.date ?? dateParam,

              // ⭐ SSOT: session_id for visual grouping (presentation only)
              // DO NOT parse this value - it's an opaque string from backend
              session_id: fullEntry.session_id || null
            };
          };

          // ⭐ SSOT: flatMap all entries without any deduplication or aggregation
          appointmentsData = data.queues.flatMap((queue) =>
          (queue.entries || []).
          map((entry) => adaptEntry(entry, queue)).
          filter((entry) => entry !== null) // Remove entries without ID
          );

          logger.info(`📊 SSOT: Loaded ${appointmentsData.length} entries (no dedup, no aggregation)`);
        } else {
          // Обрабатываем старый формат для совместимости
          if (activeTab && data[activeTab]) {
            appointmentsData = Array.isArray(data[activeTab]) ? data[activeTab] : [];
          } else {
            // Берем все специальности и объединяем
            for (const dept in data) {
              const deptData = data[dept];
              if (Array.isArray(deptData)) {
                appointmentsData.push(...deptData);
              }
            }
          }
        }

        setPaginationInfo({
          total: appointmentsData.length,
          hasMore: false,
          loadingMore: false
        });

        logger.info(`📊 Загружено ${appointmentsData.length} записей для специальности: ${activeTab || 'все'}`);

        // Отладка: показываем ID всех загруженных записей
        if (appointmentsData.length > 0) {
          logger.info('📋 ID всех загруженных записей:', appointmentsData.map((a) => a.id));
        }

        // ✅ ИСПРАВЛЕНО: Пустая очередь - это нормально, не переключаемся в демо-режим
        if (appointmentsData.length === 0) {
          logger.info('📋 Нет записей на сегодня - это нормальная ситуация в начале дня');
          // Устанавливаем пустой массив, не выбрасываем ошибку
          setAppointments([]);
          setDataSource('api'); // ✅ Указываем, что данные получены от API
          setAppointmentsLoading(false);
          return; // ✅ Выходим из функции, не загружаем демо-данные
        }
      } else {
        logger.warn('⚠️ Получены некорректные данные от сервера:', data);
        throw new Error('Некорректные данные от сервера');
      }

      if (appointmentsData.length > 0) {
        // Обогащаем данные записей информацией о пациентах
        const enriched = await enrichAppointmentsWithPatientData(appointmentsData);

        // ⭐ SSOT: Просто устанавливаем данные без local overrides
        // Removed: _locallyModified, localStorage overrides
        startTransition(() => {
          setAppointments(enriched);
          setDataSource('api');
        });
        logger.info('✅ SSOT: Загружено', enriched.length, 'записей (без local overrides)');
      } else {
        // QW-03 fix: empty API response is a valid state, not a demo fallback.
        // Empty result is already handled earlier (line ~1370). This branch
        // is unreachable but kept as defensive code.
        startTransition(() => {
          setAppointments([]);
          setDataSource('api');
        });
      }
    } catch (error) {
      if (error?.response?.status === 429) {
        autoRefreshCooldownUntilRef.current = Date.now() + 60_000;
        autoRefreshCooldownLoggedRef.current = false;
        logger.warn('⏳ Регистраторская очередь ограничена по частоте, включаем cooldown на 60с', {
          source: callSource,
          dateParam: showCalendar && historyDate ? historyDate : getLocalDateString()
        });
        return;
      }

      // Handle axios errors
      if (error.response?.status === 401) {
        // Токен недействителен
        logger.warn('Токен недействителен (401), очищаем и показываем ошибку');
        localStorage.removeItem('auth_token');
        // QW-03 fix: show error state instead of demo data.
        startTransition(() => {
          if (!silent) setDataSource('error');
          setAppointments([]);
        });
      } else {
        // Other errors (network, 404, 500, etc.)
        logger.error('❌ Backend недоступен для загрузки записей:', error.message);
        logger.error('❌ Детали ошибки:', error);
        startTransition(() => {
          if (!silent) setDataSource('error');
          setAppointments([]);
        });
        // Показываем уведомление пользователю только при первой загрузке
        if (appointmentsCount === 0) {
          notify.error('Backend недоступен. Проверьте подключение и повторите попытку.');
        }
      }
    } finally {
      loadAppointmentsInFlightRef.current = false;
      if (!silent) setAppointmentsLoading(false);
    }
  }, [enrichAppointmentsWithPatientData, showCalendar, historyDate, searchParams, activeTab, appointmentsCount]);

  // Слушаем обновления отделений от админ-панели
  useEffect(() => {
    const handleDepartmentsUpdate = (event) => {
      logger.info('RegistrarPanel: Получено обновление отделений, перезагружаю...', event.detail);
      loadIntegratedData();
    };

    window.addEventListener('departments:updated', handleDepartmentsUpdate);
    return () => window.removeEventListener('departments:updated', handleDepartmentsUpdate);
  }, [loadIntegratedData]);

  // Первичная загрузка данных (однократно) с защитой от двойного вызова в React 18
  const initialLoadRef = useRef(false);
  const loadAppointmentsInFlightRef = useRef(false);
  const autoRefreshCooldownUntilRef = useRef(0);
  const autoRefreshCooldownLoggedRef = useRef(false);
  useEffect(() => {
    if (initialLoadRef.current) return;
    initialLoadRef.current = true;
    logger.info('🚀 Starting initial data load (guarded)...');
    loadAppointments({ source: 'initial_load' });
    loadIntegratedData();
  }, [loadAppointments, loadIntegratedData]);

  // Слушаем глобальные события обновления очереди для синхронизации статусов
  useEffect(() => {
    const handleQueueUpdate = (event) => {
      const { action, specialty } = event.detail || {};
      logger.info('[RegistrarPanel] Получено событие обновления очереди:', { action, specialty, detail: event.detail });

      // Для критических действий обновляем немедленно без silent режима
      const criticalActions = ['patientCalled', 'visitStarted', 'visitCompleted', 'nextPatientCalled', 'refreshAll', 'entryAdded'];
      const shouldUpdateImmediately = criticalActions.includes(action);

      if (shouldUpdateImmediately) {
        logger.info('[RegistrarPanel] Немедленное обновление после действия:', action);
        logger.info('[RegistrarPanel] Детали события:', event.detail);
        // Увеличиваем задержку для гарантии сохранения данных в БД (особенно для новых записей)
        const delay = action === 'entryAdded' || action === 'refreshAll' ? 500 : 300;
        setTimeout(() => {
          logger.info('[RegistrarPanel] Выполняем обновление после задержки:', delay, 'ms');
          loadAppointments({ source: `queue_update_${action}`, silent: false });
        }, delay);
      } else {
        // Для других событий тихое обновление
        loadAppointments({ source: 'queue_update_event', silent: true });
      }
    };
    window.addEventListener('queueUpdated', handleQueueUpdate);

    return () => {
      window.removeEventListener('queueUpdated', handleQueueUpdate);
    };
  }, [loadAppointments]);

  // Перезагружаем данные при изменении фильтров
  useEffect(() => {
    if (initialLoadRef.current) {
      logger.info('🔄 Фильтры изменились (поиск/статус), но НЕ перезагружаем данные (дата контролируется календарём)');
      // Не перезагружаем данные - фильтрация происходит на клиенте через useMemo filteredAppointments
    }
  }, [searchQuery, statusFilter]);

  // Синхронизация tempDateInput с historyDate при открытии календаря
  useEffect(() => {
    if (showCalendar) {
      setTempDateInput(historyDate);
    }
  }, [showCalendar, historyDate]);

  // Debounce для ввода даты с клавиатуры
  useEffect(() => {
    if (!showCalendar) return;

    const timer = setTimeout(() => {
      // Проверяем, что введённая дата валидна и отличается от текущей
      if (tempDateInput && tempDateInput !== historyDate) {
        logger.info('📅 Debounced date input:', tempDateInput);
        setHistoryDate(tempDateInput);
      }
    }, 1000); // Задержка 1 секунда

    return () => clearTimeout(timer);
  }, [tempDateInput, showCalendar, historyDate]);

  // Перезагружаем данные при изменении даты в календаре
  useEffect(() => {
    if (showCalendar && historyDate && initialLoadRef.current) {
      logger.info('📅 Дата календаря изменилась на:', historyDate);
      logger.info('📅 Вызываем loadAppointments с параметрами:', { showCalendar, historyDate });
      loadAppointments({ silent: false, source: 'calendar_date_change' });
    }
  }, [historyDate, showCalendar, loadAppointments]);

  // Отслеживаем изменения в appointments для отладки
  useEffect(() => {
    logger.info('🔔 appointments state изменился:', {
      count: appointments.length,
      showCalendar,
      historyDate,
      first3: appointments.slice(0, 3).map((a) => ({ id: a.id, fio: a.patient_fio, date: a.appointment_date }))
    });
  }, [appointments, showCalendar, historyDate]);

  // Функция для загрузки дополнительных записей
  const loadMoreAppointments = useCallback(async () => {
    if (paginationInfo.loadingMore || !paginationInfo.hasMore) return;

    setPaginationInfo((prev) => ({ ...prev, loadingMore: true }));

    try {
      logger.info('RegistrarPanel: load-more delegates to canonical queue loader');
      await loadAppointments({ source: 'load_more', silent: true });
    } catch (error) {
      logger.error('Ошибка загрузки дополнительных записей:', error);
    } finally {
      setPaginationInfo((prev) => ({ ...prev, loadingMore: false }));
    }
  }, [paginationInfo.loadingMore, paginationInfo.hasMore, loadAppointments]);

  // Обработчик события из хедера для открытия мастера записи
  useEffect(() => {
    const handleOpenWizard = () => {
      setShowWizard(true);
    };

    window.addEventListener('openAppointmentWizard', handleOpenWizard);
    return () => {
      window.removeEventListener('openAppointmentWizard', handleOpenWizard);
    };
  }, []);

  // P-008 companion: when the user clicks "Новая запись" from another page,
  // HeaderNew navigates to /registrar?action=new. Detect that query param on
  // mount / route change and auto-open the wizard, then clear the param so
  // a refresh does not re-trigger it.
  useEffect(() => {
    const action = searchParams.get('action');
    if (action === 'new' && !showWizard) {
      setShowWizard(true);
      // Clean the URL so a refresh or back-navigation does not re-open the wizard
      const next = new URLSearchParams(searchParams);
      next.delete('action');
      setSearchParams(next, { replace: true });
    }
    // setSearchParams is a stable identity from useSearchParams — React Router 6.3+
    // guarantees referential stability, so it is safe to omit from deps.
  }, [searchParams, showWizard]); // eslint-disable-line react-hooks/exhaustive-deps

  // ✅ Проверка localStorage для обновления после присоединения к очереди (fallback механизм)
  useEffect(() => {
    const checkLastQueueJoin = () => {
      try {
        const lastJoinStr = localStorage.getItem('lastQueueJoin');
        if (!lastJoinStr) return;

        const lastJoin = JSON.parse(lastJoinStr);
        const joinTime = new Date(lastJoin.timestamp);
        const now = new Date();
        const diffMs = now - joinTime;

        // Проверяем только если прошло меньше 10 секунд с момента присоединения
        if (diffMs < 10000 && diffMs > 0) {
          logger.info('[RegistrarPanel] Обнаружено недавнее присоединение к очереди, обновляем данные');
          logger.info('[RegistrarPanel] Данные присоединения:', lastJoin);
          // Удаляем флаг после использования
          localStorage.removeItem('lastQueueJoin');
          // Обновляем данные
          setTimeout(() => {
            loadAppointments({ source: 'queueJoin_fallback', silent: false });
          }, 500);
        }
      } catch (err) {
        logger.error('[RegistrarPanel] Ошибка проверки lastQueueJoin:', err);
      }
    };

    // Проверяем при монтировании и каждые 2 секунды
    checkLastQueueJoin();
    const interval = setInterval(checkLastQueueJoin, 2000);

    return () => clearInterval(interval);
  }, [loadAppointments]);

  // Автообновление очереди с возможностью паузы (в тихом режиме)
  useEffect(() => {
    // P-026 fix: previously auto-refresh was disabled whenever ANY of
    // (showWizard, paymentDialog, printDialog, cancelDialog) was open. This
    // meant a registrar with a payment dialog open for 2+ minutes would not
    // see new online-queue patients arrive in the worklist behind the dialog.
    //
    // R-26 fix: pause auto-refresh when ANY dialog is open.
    // Раньше только showWizard — но payment/cancel/reschedule dialogs
    // тоже могут пострадать от фонового refresh (row positions change).
    const anyDialogOpen = showWizard
      || paymentDialog.open
      || cancelDialog.open
      || printDialog.open
      || recordPreviewDialog.open
      || contextMenu.open
      || forceMajeureModal.open
      || showSlotsModal;
    if (anyDialogOpen) return;
    if (!autoRefresh) return;
    if (Date.now() < autoRefreshCooldownUntilRef.current) return;

    const id = setInterval(() => {
      if (Date.now() < autoRefreshCooldownUntilRef.current || loadAppointmentsInFlightRef.current) {
        return;
      }
      // Загружаем только записи тихо, без смены индикаторов
      logger.info('⏰ Автообновление: вызов loadAppointments (dialog-open resilient)');
      loadAppointments({ silent: true, source: 'auto_refresh' });
    }, 15000);

    return () => clearInterval(id);
  }, [autoRefresh, showWizard, loadAppointments]);

  // Функции для жесткого потока
  // Decomp 5: record action handlers extracted to useRegistrarActions hook.
  // openRecordPreview, openRecordEditor, handleContextMenuAction remain
  // inline because they are simple state setters (1-3 lines each).
  // R-33 fix: RU messages applied in useRegistrarActions hook.
  const {
    runRegistrarRecordAction,
    handleStartVisit,
    handlePayment,
    updateAppointmentStatus,
  } = useRegistrarActions({ appointments, loadAppointments });


  // QW-01 fix: handleBulkAction removed along with bulk-action UI.

  // ✅ ИСПОЛЬЗУЕМ useRef для хранения filteredAppointments, чтобы избежать ошибки "Cannot access before initialization"
  const filteredAppointmentsRef = useRef([]);

  // Горячие клавиши — extracted to useRegistrarHotkeys hook (Decomp 2)
  // Phase 2: navigate replaces setSearchParams for canonical routes
  useRegistrarHotkeys({
    setShowWizard,
    setShowSlotsModal,
    setActiveTab,
    navigate,
    showWizard,
    showSlotsModal,
    appointments,
  });

  // Мемоизированные счетчики и индикаторы по отделам
  const departmentStats = useMemo(() => {
    const stats = {};

    // ⭐ SSOT: Use queue profile keys from API, not hardcoded department keys
    // queueProfiles is loaded from GET /queues/profiles via ModernTabs
    const profileKeys = queueProfiles.length > 0 ?
    queueProfiles.map((p) => p.key) :
    ['cardiology', 'ecg', 'dermatology', 'stomatology', 'lab', 'procedures']; // Fallback

    // Get queue_tags for each profile for accurate matching
    const profileTagsMap = {};
    queueProfiles.forEach((p) => {
      profileTagsMap[p.key] = p.queue_tags || [p.key];
    });

    profileKeys.forEach((profileKey) => {
      // ⭐ SSOT: Match entries by queue_tags from profile
      const possibleTags = profileTagsMap[profileKey] || [profileKey];

      const profileAppointments = appointments.filter((a) => {
        const entryTag = (a.queue_tag || a.specialty || '').toLowerCase().trim();
        return possibleTags.some((tag) => tag.toLowerCase() === entryTag);
      });

      const todayAppointments = profileAppointments.filter((a) => {
        const appointmentDate = a.date || a.appointment_date;
        return appointmentDate === todayStr;
      });

      stats[profileKey] = {
        todayCount: todayAppointments.length,
        hasActiveQueue: profileAppointments.some((a) =>
        a.queue_numbers && a.queue_numbers.length > 0 &&
        ['waiting', 'called', 'in_service'].includes(a.status)
        ),
        hasPendingPayments: profileAppointments.some((a) =>
        a.status === 'paid_pending' || a.payment_status === 'pending'
        )
      };
    });

    return stats;
  }, [appointments, todayStr, queueProfiles]);


  // 🎨 PRESENTATION-ONLY: Aggregation for "All departments" tab
  // Groups entries by patient for visual display (1 patient = 1 row)
  // ✅ ALLOWED by SSOT: This is view-model grouping, NOT business logic
  // ⚠️ Do NOT use for: filtering, routing, department decisions
  const aggregatePatientsForAllDepartments = useCallback((appointments) => aggregateRegistrarPatients(appointments), []);

  // Мемоизированная фильтрация записей по выбранной вкладке (повторный клик снимает фильтр → activeTab === null)
  // Фильтрация по вкладке + по дате (?date=YYYY-MM-DD) + по поиску (?q=...)

  // ✅ Функция фильтрации услуг по вкладке
  // ⭐ ИСПРАВЛЕНО: Для QR-записей с несколькими специалистами используем queue_numbers
  const filterServicesByDepartment = useCallback((appointment, departmentKey) => {
    // ⭐ SSOT: Используем централизованную функцию toServiceCode
    // Используем только канонический резолв из SSOT
    const toServiceCode = (value) => {
      if (!value) return null;

      // Сначала пробуем SSOT резолвер
      const ssotResult = ssotToServiceCode(value);
      if (ssotResult) return ssotResult;

      return null;
    };

    // ⭐ Для QR-записей с queue_numbers - собираем услуги из всех queue_numbers
    const normalizeDepartmentKey = (value) => value ? String(value).toLowerCase().trim() : null;
    const targetDepartmentKey = normalizeDepartmentKey(departmentKey);

    const getServiceIdentity = (serviceItem) => {
      if (serviceItem && typeof serviceItem === 'object') {
        return {
          id: serviceItem.id ?? serviceItem.service_id ?? null,
          code: serviceItem.service_code ?? serviceItem.code ?? null,
          name: serviceItem.name ?? serviceItem.service_name ?? null,
          departmentKey: serviceItem.department_key ?? serviceItem.departmentKey ?? null
        };
      }

      return {
        id: typeof serviceItem === 'number' || typeof serviceItem === 'string' && !isNaN(serviceItem) ? Number(serviceItem) : null,
        code: typeof serviceItem === 'string' ? serviceItem : null,
        name: typeof serviceItem === 'string' ? serviceItem : null,
        departmentKey: null
      };
    };

    const serviceMatchesIdentity = (candidate, identity) => {
      if (!candidate || typeof candidate !== 'object') return false;
      const candidateId = candidate.id ?? candidate.service_id ?? null;
      if (identity.id != null && candidateId != null && Number(candidateId) === Number(identity.id)) return true;

      const candidateCode = candidate.service_code ?? candidate.code ?? null;
      if (identity.code && candidateCode && String(candidateCode).toUpperCase() === String(identity.code).toUpperCase()) return true;

      const candidateName = candidate.name ?? candidate.service_name ?? null;
      if (identity.name && candidateName && String(candidateName).trim() === String(identity.name).trim()) return true;

      return false;
    };

    const findBackendServiceMeta = (serviceItem, index) => {
      const identity = getServiceIdentity(serviceItem);
      if (identity.departmentKey) return identity;

      const serviceDetails = Array.isArray(appointment.service_details) ? appointment.service_details : [];
      const indexedDetail = serviceDetails[index];
      if (indexedDetail?.department_key) return indexedDetail;

      const detailMatch = serviceDetails.find((detail) => serviceMatchesIdentity(detail, identity));
      if (detailMatch?.department_key) return detailMatch;

      if (services && typeof services === 'object') {
        for (const groupServices of Object.values(services)) {
          if (!Array.isArray(groupServices)) continue;
          const serviceMatch = groupServices.find((service) => serviceMatchesIdentity(service, identity));
          if (serviceMatch?.department_key) return serviceMatch;
        }
      }

      return null;
    };

    const filterByBackendDepartment = (appointmentServices) => {
      if (!targetDepartmentKey || !Array.isArray(appointmentServices) || appointmentServices.length === 0) {
        return null;
      }

      let sawBackendDepartment = false;
      const filtered = appointmentServices.filter((serviceItem, index) => {
        const serviceMeta = findBackendServiceMeta(serviceItem, index);
        const serviceDepartmentKey = normalizeDepartmentKey(serviceMeta?.department_key ?? serviceMeta?.departmentKey);
        if (!serviceDepartmentKey) return false;
        sawBackendDepartment = true;
        return serviceDepartmentKey === targetDepartmentKey;
      });

      return sawBackendDepartment ? filtered : null;
    };

    if (appointment.queue_numbers && Array.isArray(appointment.queue_numbers) && appointment.queue_numbers.length > 0) {

      // ⭐ Если НЕТ departmentKey (вкладка "Все отделения") - используем уже имеющиеся services
      if (!departmentKey) {
        // ✅ ИСПРАВЛЕНО: Используем appointment.services напрямую, т.к. они уже содержат правильные коды (K11, L02 и т.д.)
        // Раньше мы генерировали коды из specialty/service_name, что приводило к fallback на K01/L01
        if (appointment.services && Array.isArray(appointment.services) && appointment.services.length > 0) {
          return appointment.services;
        }

        // Fallback: только если services пустой, генерируем из queue_numbers
        const allCodes = [];
        const seenCodes = new Set();

        appointment.queue_numbers.forEach((qn) => {
          // Приоритет 1: service_name
          const serviceNameCode = toServiceCode(qn.service_name);
          if (serviceNameCode && !seenCodes.has(serviceNameCode)) {
            allCodes.push(serviceNameCode);
            seenCodes.add(serviceNameCode);
          }
        });

        return allCodes.length > 0 ? allCodes : [];
      }

      // ⭐ Для конкретной вкладки - фильтруем из существующих services по категории
      // ✅ ИСПРАВЛЕНО: Используем appointment.services напрямую, фильтруя по категории отделения
      const backendFilteredServices = filterByBackendDepartment(appointment.services || []);
      if (backendFilteredServices) {
        return backendFilteredServices;
      }

      const departmentCodePrefixes = {
        'cardio': ['K'], // K01, K11 и т.д. - все кардиоуслуги кроме ECG
        'echokg': ['K10', 'ECG'], // Только ЭКГ (K10)
        'derma': ['D'], // D01 и т.д. (только консультации, не D_PROC)
        'dental': ['S'], // S01, S10 и т.д.
        'lab': ['L'], // L01, L02, L11 и т.д.
        'procedures': ['P', 'C', 'D_PROC'] // P01, P02, C01, C05, D_PROC02 и т.д.
      };

      const allowedPrefixes = departmentCodePrefixes[departmentKey] || [];

      // ✅ Фильтруем существующие services по категории
      if (appointment.services && Array.isArray(appointment.services) && appointment.services.length > 0) {
        const filteredByDepartment = appointment.services.filter((serviceItem) => {
          // ✅ ИСПРАВЛЕНО: Извлекаем код из объекта если это объект, иначе используем как строку
          // Backend может возвращать services как [{code: "L10", name: "Общий белок", ...}] или как ["L10"]
          const code = typeof serviceItem === 'object' && serviceItem?.code ?
          String(serviceItem.code).toUpperCase() :
          String(serviceItem).toUpperCase();

          // Специальная логика для echokg: только K10 и ECG коды
          if (departmentKey === 'echokg') {
            return code === 'K10' || code.startsWith('ECG');
          }

          // Специальная логика для cardio: все K-коды КРОМЕ K10 (ЭКГ)
          if (departmentKey === 'cardio') {
            return code.startsWith('K') && code !== 'K10';
          }

          // Для остальных отделений - проверяем по префиксу
          return allowedPrefixes.some((prefix) => code.startsWith(prefix));
        });

        if (filteredByDepartment.length > 0) {
          return filteredByDepartment;
        }
      }

      // Если services не дали подходящих кодов, не подменяем их specialty-эвристикой.
      return [];
    }

    // ⭐ Для обычных записей без queue_numbers
    if (!departmentKey) {
      return appointment.services;
    }

    // ⭐ Стандартная фильтрация по service_codes
    if (!appointment.services || !Array.isArray(appointment.services) || appointment.services.length === 0) {
      return appointment.services;
    }

    const appointmentServiceCodes = appointment.service_codes || [];
    const appointmentServices = appointment.services || [];

    // Создаем маппинг service -> service_code
    const backendFilteredServices = filterByBackendDepartment(appointmentServices);
    if (backendFilteredServices) {
      return backendFilteredServices;
    }

    const serviceToCodeMap = new Map();

    appointmentServices.forEach((service, index) => {
      if (appointmentServiceCodes[index]) {
        serviceToCodeMap.set(service, String(appointmentServiceCodes[index]).toUpperCase());
        return;
      }

      if (services && typeof services === 'object') {
        for (const groupName in services) {
          const groupServices = services[groupName];
          if (Array.isArray(groupServices)) {
            if (typeof service === 'number' || typeof service === 'string' && !isNaN(service)) {
              const serviceId = parseInt(service);
              const serviceByID = groupServices.find((s) => s.id === serviceId);
              if (serviceByID && serviceByID.service_code) {
                serviceToCodeMap.set(service, String(serviceByID.service_code).toUpperCase());
                return;
              }
            }
            const serviceByName = groupServices.find((s) => s.name === service);
            if (serviceByName && serviceByName.service_code) {
              serviceToCodeMap.set(service, String(serviceByName.service_code).toUpperCase());
              return;
            }
          }
        }
      }
    });

    // Маппинг категорий по вкладкам
    const departmentCategoryMapping = {
      'cardio': ['K', 'ECHO'],
      'echokg': ['ECG'],
      'derma': ['D', 'DERM', 'DERM_PROC'],
      'dental': ['S', 'DENT', 'STOM'],
      'lab': ['L'],
      'procedures': ['P', 'C', 'D_PROC']
    };

    const getServiceCategoryByCode = (serviceCode) => {
      if (!serviceCode) return null;
      const normalizedCode = String(serviceCode).toUpperCase();

      if (normalizedCode === 'K10' || normalizedCode === 'CARD_ECG' || normalizedCode.includes('ECG') || normalizedCode.includes('ЭКГ')) return 'ECG';
      if (normalizedCode === 'CARD_ECHO' || normalizedCode.includes('ECHO') || normalizedCode.includes('ЭХОКГ')) return 'ECHO';
      if (normalizedCode.match(/^P\d+$/)) return 'P';
      if (normalizedCode.match(/^D_PROC\d+$/)) return 'D_PROC';
      if (normalizedCode.match(/^C\d+$/)) return 'C';
      if (normalizedCode.match(/^K\d+$/) && normalizedCode !== 'K10') return 'K';
      if (normalizedCode.match(/^S\d+$/)) return 'S';
      if (normalizedCode.match(/^L\d+$/)) return 'L';
      if (normalizedCode === 'D01') return 'D';
      if (normalizedCode.startsWith('CONS_CARD')) return 'K';
      if (normalizedCode.startsWith('CONS_DERM') || normalizedCode.startsWith('DERMA_')) return 'DERM';
      if (normalizedCode.startsWith('CONS_DENT') || normalizedCode.startsWith('DENT_') || normalizedCode.startsWith('STOM_')) return 'DENT';
      if (normalizedCode.startsWith('LAB_')) return 'L';
      if (normalizedCode.startsWith('COSM_')) return 'C';
      if (normalizedCode.startsWith('PHYSIO_') || normalizedCode.startsWith('PHYS_')) return 'P';
      if (normalizedCode.startsWith('DERM_PROC_') || normalizedCode.startsWith('DERM_')) return 'D_PROC';
      if (normalizedCode.startsWith('CARD_') && !normalizedCode.includes('ECG')) return 'K';
      return null;
    };

    const targetCategoryCodes = departmentCategoryMapping[departmentKey] || [];

    const filteredServices = appointmentServices.
    filter((service) => {
      const serviceCode = serviceToCodeMap.get(service);
      if (!serviceCode) return false;
      const category = getServiceCategoryByCode(serviceCode);
      return targetCategoryCodes.includes(category);
    });

    return filteredServices;
  }, [services]);

  // ✅ filteredAppointments вычисляется здесь и сохраняется в ref
  const filteredAppointments = useMemo(() => {
    // ⭐ SSOT: Get queue_tags from loaded profiles instead of hardcoded mapping
    // queueProfiles is populated by ModernTabs via onProfilesLoaded callback
    const getQueueTagsForTab = (tabKey) => {
      if (!tabKey) return [];

      // Find profile by key
      const profile = queueProfiles.find((p) => p.key === tabKey);
      if (profile && profile.queue_tags && profile.queue_tags.length > 0) {
        return profile.queue_tags;
      }

      // Fallback: use tabKey itself as the only tag
      // ⚠️ TEMPORARY ADAPTER: for backwards compatibility during transition
      return [tabKey];
    };

    // Если выбрана конкретная вкладка (не "Все отделения"), используем appointments с фильтрацией по queue_tag
    if (activeTab) {
      // ⭐ SSOT: queue_tags from API profiles, not hardcoded
      const possibleTags = getQueueTagsForTab(activeTab);

      // Фильтруем appointments по queue_tag вкладки
      const entriesForTab = (appointments).filter((entry) => {
        // Определяем queue_tag записи
        const entryQueueTag = (
        entry.queue_tag ||
        entry.specialty ||
        entry.queue_numbers && entry.queue_numbers[0]?.queue_tag ||
        '').
        toString().toLowerCase().trim();

        // Проверяем соответствие вкладке
        const matchesTab = possibleTags.some((tag) => tag.toLowerCase() === entryQueueTag);
        if (!matchesTab) return false;

        // Фильтр по статусу
        if (statusFilter && entry.status !== statusFilter) return false;

        // Фильтр по поиску
        if (searchQuery) {
          const inFio = (entry.patient_fio || entry.patient_name || '').toLowerCase().includes(searchQuery);
          const inId = String(entry.id).includes(searchQuery);
          const phoneDigits = (entry.patient_phone || entry.phone || '').replace(/\D/g, '');
          const searchDigits = searchQuery.replace(/\D/g, '');
          const inPhone = phoneDigits.includes(searchDigits);
          if (!inFio && !inId && !inPhone) return false;
        }

        return true;
      });

      // Сортируем по queue_time ASC
      const sorted = sortRegistrarRowsForPresentation(entriesForTab);

      logger.info('⭐ FIX 16: Вкладка', activeTab, '- найдено', sorted.length, 'записей из',
      appointments.length, 'appointments');

      // ⭐ FIX 16: Подробный лог queue_time для каждой entry
      sorted.forEach((entry, idx) => {
        logger.info(`  📌 Entry[${idx}]: id=${entry.id}, queue_tag=${entry.queue_tag}, queue_time=${entry.queue_time}, patient=${entry.patient_fio}`);
      });

      // Каждая entry уже содержит свой queue_time — никакого переопределения не нужно
      return sorted.map((entry) => ({
        ...entry,
        // Нормализуем поля для совместимости с EnhancedAppointmentsTable
        patient_fio: entry.patient_fio || entry.patient_name || 'Неизвестный пациент',
        queue_number: entry.number || entry.queue_number,
        queue_numbers: entry.queue_numbers || [{
          number: entry.number,
          queue_tag: entry.queue_tag || entry.specialty,
          status: entry.status,
          queue_time: entry.queue_time
        }]
      }));
    }

    // Для вкладки "Все отделения" (activeTab === null или undefined) - агрегируем пациентов
    if (!activeTab) {
      // Сначала фильтруем по статусу, если задан
      const filtered = sortRegistrarRowsForPresentation(appointments.filter((appointment) => {
        // Фильтр по статусу (если задан)
        if (statusFilter && appointment.status !== statusFilter) return false;
        return true;
      }));

      // Затем агрегируем пациентов
      logger.info(`📊 Для вкладки "Все отделения": ${filtered.length} записей до агрегации`);
      const qrInFiltered = filtered.filter((a) => a.source === 'online');
      logger.info(`🔍 QR-записей в фильтре: ${qrInFiltered.length}`);
      qrInFiltered.forEach((a) => {
        logger.info(`  - ${a.patient_fio}: ${a.queue_numbers?.length || 0} queue_numbers`, a.queue_numbers);
      });

      const aggregatedPatients = aggregatePatientsForAllDepartments(filtered);
      logger.info(`📊 После агрегации: ${aggregatedPatients.length} пациентов`);

      // Применяем поиск к агрегированным данным
      if (searchQuery) {
        const searched = aggregatedPatients.filter((patient) => {
          const inFio = (patient.patient_fio || '').toLowerCase().includes(searchQuery);

          // Поиск по ID записи
          const inId = String(patient.id).includes(searchQuery);

          // Улучшенный поиск по телефону
          const originalPhone = (patient.patient_phone || '').toLowerCase();
          const phoneDigits = originalPhone.replace(/\D/g, '');
          const searchDigits = searchQuery.replace(/\D/g, '');

          const inPhone = originalPhone.includes(searchQuery) ||
          phoneDigits.includes(searchDigits) ||
          searchDigits.length >= 3 && phoneDigits.includes(searchDigits);

          // Поиск по услугам (теперь ищем в агрегированном списке)
          const inServices = Array.isArray(patient.services) && patient.services.some((s) => String(s).toLowerCase().includes(searchQuery));

          return inFio || inPhone || inServices || inId;
        });
        // Presentation-only order: backend queue_time first, then created_at.
        return sortRegistrarRowsForPresentation(searched);
      }

      // ⭐ ВАЖНО: Сортируем агрегированных пациентов по queue_time ASC (согласно cursor.yaml)
      const sortedAggregated = sortRegistrarRowsForPresentation(aggregatedPatients);

      // ✅ ИСПРАВЛЕНО: Применяем правильное форматирование услуг для вкладки "Все отделения"
      // Это гарантирует, что для QR-записей будут показаны все коды услуг (K01, S01 и т.д.)
      return sortedAggregated.map((patient) => ({
        ...patient,
        services: filterServicesByDepartment(patient, null)
      }));
    }

    // Presentation-only order on a copy; backend remains owner of queue facts.
    return sortRegistrarRowsForPresentation(appointments);
  }, [appointments, activeTab, statusFilter, searchQuery, aggregatePatientsForAllDepartments, filterServicesByDepartment, queueProfiles]);

  // ✅ Сохраняем filteredAppointments в ref для использования в handleKeyDown
  filteredAppointmentsRef.current = filteredAppointments;

  // Мемоизированный компонент индикатора источника данных (для всех вкладок)
  const DataSourceIndicator = memo(({ count }) => {
    // QW-03 fix: 'demo' state replaced with 'error' state — no more fake data.
    // DS-3: inline styles replaced with .registrar-ds-* CSS classes
    if (dataSource === 'error') {
      return (
        <div className="registrar-ds-indicator registrar-ds-error">
          <Icon name="exclamationmark.triangle" size="small" className="registrar-text-white" />
          <span>Не удалось загрузить записи. Проверьте подключение к серверу.</span>
          <button
            onClick={() => loadAppointments({ source: 'error_refresh_button', force: true })}
            className="registrar-ds-retry-btn">

            Повторить
          </button>
        </div>);

    }

    if (dataSource === 'api') {
      return (
        <div className="registrar-ds-indicator registrar-ds-success">
          <Icon name="checkmark.circle" size="small" className="registrar-text-white" />
          <span>Данные загружены с сервера</span>
          <span className="registrar-ds-count">
            {count} из {paginationInfo.total} записей
          </span>
        </div>);

    }

    if (dataSource === 'loading') {
      return (
        <div className="registrar-ds-indicator registrar-ds-loading">
          <Icon name="arrow.up.arrow.down" size="small" className="registrar-text-white" />
          <span>Загрузка данных...</span>
        </div>);

    }

    return null;
  });

  DataSourceIndicator.displayName = 'DataSourceIndicator';
  DataSourceIndicator.propTypes = {
    count: PropTypes.number.isRequired,
  };

  // Функция генерации CSV
  const generateCSV = (data) => {
    const headers = ['№', 'ФИО', 'Год рождения', 'Телефон', 'Услуги', 'Тип обращения', 'Вид оплаты', 'Стоимость', 'Статус'];
    const rows = data.map((row, index) => [
    index + 1,
    row.patient_fio || '',
    row.patient_birth_year || '',
    // R-05 fix: маскируем телефон в CSV-экспорте
    maskPhoneForCSV(row.patient_phone || ''),
    Array.isArray(row.services) ? row.services.join('; ') : row.services || '',
    row.visit_type || '',
    row.payment_type || '',
    row.cost || '',
    row.status || '']
    );

    // R-23 fix: CSV injection protection (CWE-1236).
    // Экранируем двойные кавычки (CSV standard: " → "")
    // и префиксируем опасные символы (=, +, -, @) одинарной кавычкой,
    // чтобы Excel/LibreOffice не интерпретировали их как формулы.
    const escapeCSVCell = (value) => {
      const str = String(value ?? '');
      let escaped = str.replace(/"/g, '""');
      if (/^[=+\-@]/.test(escaped)) {
        escaped = "'" + escaped;
      }
      return `"${escaped}"`;
    };

    const csvContent = [
    headers.join(','),
    ...rows.map((row) => row.map(escapeCSVCell).join(','))].
    join('\n');

    return csvContent;
  };

  // R-05 fix: маскирование телефона для CSV-экспорта.
  function maskPhoneForCSV(phone) {
    if (!phone) return '';
    const digits = phone.replace(/\D/g, '');
    if (digits.length < 4) return '***';
    const lastTwo = digits.slice(-2);
    const countryMatch = phone.match(/^\+\d{1,3}/);
    const country = countryMatch ? countryMatch[0] : '+';
    return `${country} ***-**-${lastTwo}`;
  }

  // Функция скачивания CSV
  const downloadCSV = (content, filename) => {
    const blob = new Blob(['\ufeff' + content], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };


  // Обработчик действий контекстного меню
  const openRecordPreview = useCallback((row) => {
    setRecordPreviewDialog({ open: true, row });
  }, []);

  const openRecordEditor = useCallback((row) => {
    if (isMultiRecordAggregateRow(row)) {
      logger.info('[RegistrarPanel] Opening edit wizard for aggregate all-departments row', {
        patient: row?.patient_fio || row?.patient_name,
        groupedRecords: row?.grouped_records?.length || 0,
        recordRefs: row?.grouped_record_refs?.length || 0,
        aggregatedIds: row?.aggregated_ids?.length || 0
      });
    }

    logger.info('[RegistrarPanel] Opening edit wizard for:', row?.patient_fio || row?.patient_name);
    setWizardEditMode(true);
    setWizardInitialData(row);
    setShowWizard(true);
  }, []);

  const handleContextMenuAction = useCallback(async (action, row) => {
    switch (action) {
      case 'view':
        openRecordPreview(row);
        break;
      case 'edit':
        openRecordEditor(row);
        logger.info('Редактирование записи:', row);
        break;
      case 'in_cabinet':
        await updateAppointmentStatus(row.id, 'in_cabinet', '', row);
        notify.success('Пациент отправлен в кабинет');
        break;
      case 'call':
        await handleStartVisit(row);
        break;
      case 'complete':
        await updateAppointmentStatus(row.id, 'done', '', row);
        notify.success('Приём завершён');
        break;
      case 'payment':
        setPaymentDialog({ open: true, row, paid: false, source: 'context' });
        break;
      case 'print':
        setPrintDialog({ open: true, type: 'ticket', data: row });
        break;
      case 'reschedule':
        setRescheduleData(row);
        setShowSlotsModal(true);
        break;
      case 'cancel':
        setCancelDialog({ open: true, row, reason: '' });
        break;
      case 'call_patient':
        if (row.patient_phone) {
          // R-24 fix: санитизация tel: URL — оставляем только digits и +.
          // Предотвращает injection через специальные символы в phone field.
          const sanitizedPhone = String(row.patient_phone).replace(/[^\d+]/g, '');
          window.open(`tel:${sanitizedPhone}`);
        }
        break;
      case 'force_majeure':
        // Открываем модальное окно форс-мажора для специалиста
        setForceMajeureModal({
          open: true,
          specialistId: row.doctor_id || row.specialist_id || null,
          specialistName: row.doctor_name || row.specialist_name || 'Все специалисты'
        });
        break;
      default:
        logger.info('Неизвестное действие:', action);
        break;
    }
  }, [updateAppointmentStatus, handleStartVisit, openRecordPreview, openRecordEditor]);

  return (
    <div style={{ ...pageStyle, overflow: 'hidden' }} role="main" aria-label="Панель регистратора">
      {/* Skip to content link for screen readers */}
      <a
        href="#main-content"
        className="registrar-hidden-visually"
        onFocus={(e) => {
          e.target.style.left = '0';
        }}
        onBlur={(e) => {
          e.target.style.left = '-9999px';
        }}>

        Перейти к основному содержимому
      </a>

      {/* R-03 fix: breadcrumb навигация для wayfinding.
          Показывает текущую view, выбранное отделение, поисковый запрос. */}
      <nav aria-label="Навигация" className="registrar-breadcrumb-nav">
        <button
          type="button"
          onClick={() => {
            const p = new URLSearchParams(searchParams);
            p.set('view', 'welcome');
            p.delete('q');
            p.delete('status');
            setSearchParams(p, { replace: true });
          }}
          className="registrar-breadcrumb-link"
        >
          Регистратура
        </button>
        {activeTab && (
          <>
            <span>›</span>
            <span>{queueProfiles.find(p => p.key === activeTab)?.title || activeTab}</span>
          </>
        )}
        {searchQuery && (
          <>
            <span>›</span>
            <span>Поиск: «{searchQuery}»</span>
          </>
        )}
        {showWizard && (
          <>
            <span>›</span>
            <span>{wizardEditMode ? 'Редактирование' : 'Новая запись'}</span>
          </>
        )}
      </nav>

      {/* Современные вкладки */}
      {(!currentView || currentView !== 'welcome' && currentView !== 'queue') &&
      <div style={{
        margin: `0 ${'1rem'}`,
        maxWidth: 'none',
        width: 'calc(100vw - 32px)'
      }}>
          <ModernTabs
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onProfilesLoaded={setQueueProfiles} // ⭐ SSOT: Store profiles for filtering
          departmentStats={departmentStats}
          theme={theme}
          language={language}
          dynamicDepartments={dynamicDepartments} />

        </div>
      }

      {/* Старые вкладки удалены - используется ModernTabs компонент */}

      {/* Основной контент без отступа сверху */}
      <div className="registrar-overflow-hidden">
        {/* Экран приветствия по параметру view=welcome (с историей: календарь + поиск) */}
        {currentView === 'welcome' &&
        <AnimatedTransition type="fade" delay={100}>
            <Card variant="default" className="registrar-card-surface">
              <CardHeader className="registrar-card-header">
                {/* QW-08 fix: reduced AnimatedTransition from 10 to 3 (100/200/300ms). */}
                {/* Previous delays 400/800/900/1000/1100/1350/1400/1500 blocked first */}
                {/* user intent until 1.5s after page load. */}
                <AnimatedTransition type="slide" direction="up" delay={200}>
                  <h1 className="registrar-hero-title">
                    {t('welcome')} в панель регистратора!
                    <Icon name="person" size="default" className="registrar-text-accent" />
                  </h1>
                </AnimatedTransition>
                <AnimatedTransition type="fade" delay={300}>
                  <div className="registrar-date-subtitle">
                    {new Date().toLocaleDateString(language === 'ru' ? 'ru-RU' : 'uz-UZ', {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                  })}
                  </div>
                </AnimatedTransition>
              </CardHeader>

              <CardContent>
                {/* Современная статистика */}
                <ModernStatistics
                appointments={appointments}
                departmentStats={departmentStats}
                language={language}
                selectedDate={showCalendar && historyDate ? historyDate : getLocalDateString()}
                onExport={() => {
                  logger.info('Экспорт статистики');
                }}
                onRefresh={() => {
                  loadAppointments({ source: 'statistics_refresh' });
                }} />


                {/* Панель управления и фильтров */}
                {/* QW-08 fix: unwrapped nested AnimatedTransition (was delays 800-1500). */}
                  <div style={{ marginBottom: 'var(--mac-spacing-8)' }}>
                      <h2 className="registrar-section-heading">
                        <Icon name="gear" size="default" className="registrar-text-accent" />
                        Панель управления
                      </h2>

                    {/* Быстрые действия */}
                      <div className="registrar-grid-auto" style={{ marginBottom: 'var(--mac-spacing-6)' }}>
                          <Button
                          variant="primary"
                          size="default"
                          onClick={() => {
                            logger.info('Кнопка "Новая запись" нажата');
                            setWizardEditMode(false); // ✅ Сброс режима
                            setWizardInitialData(null); // ✅ Сброс данных
                            setShowWizard(true);
                          }}
                          aria-label="Create new appointment"
                          className="registrar-flex" style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>

                            <Icon name="plus" size="small" className="registrar-text-white" />
                            {t('new_appointment')}
                          </Button>

                        {/* Кнопка модуля оплаты */}
                          <Button
                          variant="secondary"
                          size="default"
                          onClick={() => setShowPaymentManager(true)}
                          aria-label="Open payment module"
                          className="registrar-flex">

                            <Icon name="creditcard" size="small" />
                            Модуль оплаты
                          </Button>

                          <Button
                          variant="outline"
                          size="default"
                          onClick={() => {
                            logger.info('Кнопка "Экспорт CSV" нажата');
                            const csvContent = generateCSV(appointments);
                            const filename = `appointments_${getLocalDateString()}.csv`;
                            downloadCSV(csvContent, filename);
                            notify.success(`Экспортировано ${appointments.length} записей`);
                          }}
                          className="registrar-flex">

                            <Icon name="square.and.arrow.up" size="small" />
                            {t('export_csv')}
                          </Button>
                      </div>

                    {/* Фильтры и навигация */}
                      <div className="registrar-surface-toolbar">
                        <h3 className="registrar-subsection-heading">
                          <Icon name="magnifyingglass" size="default" className="registrar-text-accent" />
                          Фильтры и навигация
                        </h3>

                        <div className="registrar-grid-auto">
                          <Button
                          variant={showCalendar ? 'warning' : 'outline'}
                          size="default"
                          onClick={() => {
                            logger.info('Кнопка "Календарь" нажата');
                            setShowCalendar(!showCalendar);
                          }}
                          className="registrar-flex">

                            <Icon name="magnifyingglass" size="small" style={{ color: showCalendar ? 'white' : 'var(--mac-text-primary)' }} />
                            Календарь
                          </Button>

                          <Button
                          variant="success"
                          size="default"
                          onClick={() => setSearchParams({ status: 'queued' })}
                          className="registrar-flex">

                            <Icon name="checkmark.circle" size="small" className="registrar-text-white" />
                            Активная очередь
                          </Button>

                          <Button
                          variant="primary"
                          size="default"
                          onClick={() => setSearchParams({ status: 'paid_pending' })}
                          className="registrar-flex">

                            <Icon name="creditcard" size="small" className="registrar-text-white" />
                            Ожидают оплаты
                          </Button>

                          <Button
                          variant="outline"
                          size="default"
                          onClick={() => setSearchParams({})}
                          className="registrar-flex">

                            <Icon name="eye" size="small" />
                            Все записи
                          </Button>

                          <Button
                          variant="outline"
                          size="default"
                          onClick={() => navigate('/registrar/queue')}
                          className="registrar-flex">

                            <Icon name="bell" size="small" />
                            Онлайн-очередь
                          </Button>

                          <Button
                          variant="outline"
                          size="default"
                          onClick={() => {loadAppointments({ source: 'manual_refresh_button' });notify.success('Данные обновлены');}}
                          className="registrar-flex">

                            <Icon name="gear" size="small" />
                            Обновить данные
                          </Button>
                        </div>

                        {/* Календарный виджет */}
                        {showCalendar &&
                      <div className="registrar-info-card" style={{ padding: 'var(--mac-spacing-5)', boxShadow: 'var(--mac-shadow-sm)' }}>
                            <div className="registrar-flex-col">
                              <label className="registrar-picker-label">
                                <Icon name="magnifyingglass" size="small" className="registrar-text-secondary" />
                                Выберите дату для просмотра истории:
                              </label>
                              <Input
                            type="date"
                            label=""
                            value={tempDateInput}
                            onChange={(e) => {
                              setTempDateInput(e.target.value);
                              logger.info('Введена дата (debounced):', e.target.value);
                            }}
                            onBlur={(e) => {
                              if (e.target.value && e.target.value !== historyDate) {
                                logger.info('📅 Date input blur - applying immediately:', e.target.value);
                                setHistoryDate(e.target.value);
                              }
                            }} />

                              <div style={{
                            display: 'flex',
                            gap: '8px',
                            flexWrap: 'wrap'
                          }}>
                                <button
                              type="button"
                              onClick={() => {
                                const today = getLocalDateString();
                                setTempDateInput(today);
                                setHistoryDate(today);
                              }}
                              className="registrar-date-btn"
                              style={{
                                background: theme === 'light' ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-quaternary)',
                                color: textColor
                              }}>

                                  Сегодня
                                </button>
                                <button
                              type="button"
                              onClick={() => {
                                const yesterdayStr = getYesterdayDateString();
                                setTempDateInput(yesterdayStr);
                                setHistoryDate(yesterdayStr);
                              }}
                              className="registrar-date-btn"
                              style={{
                                background: theme === 'light' ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-quaternary)',
                                color: textColor
                              }}>

                                  Вчера
                                </button>
                                <button
                              type="button"
                              onClick={() => {
                                const weekAgo = new Date();
                                weekAgo.setDate(weekAgo.getDate() - 7);
                                const weekAgoStr = getLocalDateString(weekAgo);
                                setTempDateInput(weekAgoStr);
                                setHistoryDate(weekAgoStr);
                              }}
                              className="registrar-date-btn"
                              style={{
                                background: theme === 'light' ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-quaternary)',
                                color: textColor
                              }}>

                                  Неделю назад
                                </button>
                              </div>
                            </div>
                          </div>
                      }
                      </div>
                  </div>

                {/* История записей */}
                <div>
                  <div className="registrar-flex-between" style={{ marginBottom: 'var(--mac-spacing-4)' }}>
                    <h3 className="registrar-history-heading">
                      <Icon name="eye" size="default" className="registrar-text-accent" />
                      История записей
                    </h3>
                    {showCalendar &&
                  <Badge variant="secondary" className="registrar-badge-date">
                        <Icon name="magnifyingglass" size="small" />
                        {new Date(historyDate).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })}
                      </Badge>
                  }
                  </div>
                  <div className="registrar-surface-toolbar">
                    {/* Индикатор источника данных */}
                    {appointments.length > 0 && <DataSourceIndicator count={appointments.length} />}

                    {/* ✅ ДОБАВЛЕНО: Сообщение при пустой очереди */}
                    {(() => {
                    const token = tokenManager.getAccessToken();
                    const isNoToken = !token;
                    const isEmptyQueue = !appointmentsLoading && dataSource === 'api' && filteredAppointments.length === 0;

                    logger.info('🎯 Empty state render check:', {
                      appointmentsLoading,
                      dataSource,
                      filteredLength: filteredAppointments.length,
                      appointmentsLength: appointments.length,
                      hasToken: !!token,
                      isNoToken,
                      isEmptyQueue,
                      shouldShow: isEmptyQueue
                    });

                    return isEmptyQueue;
                  })() &&
                  <div className="registrar-empty-state">
                          {/* QW-04: empty state 1 of 3 (session-expired / empty-queue). */}
                    {/* Full unification deferred — requires EmptyState.jsx migration */}
                    {/* from Tailwind/native to macOS design system first. */}
                    <div style={{
                      fontSize: '48px',
                      marginBottom: '16px',
                      opacity: 0.3
                    }}>
                            {!tokenManager.hasToken() ?
                      <Icon name="lock" size="large" /> :
                      <Icon name="doc.text" size="large" />}
                          </div>
                          <h3 className="registrar-empty-heading" style={{ color: textColor }}>
                            {!tokenManager.hasToken() ? 'Сессия истекла' : 'Очередь пуста'}
                          </h3>
                          <p className="registrar-empty-desc-text" style={{ fontSize: '16px', color: textColor }}>
                            {!tokenManager.hasToken() ?
                      'Нажмите "Войти снова", чтобы обновить данные.' :
                      'На сегодня нет записей в очереди.'}
                          </p>

                          {/* Кнопки действий */}
                          {!tokenManager.hasToken() &&
                    <div className="registrar-flex-wrap">
                              <button
                        onClick={() => {
                          // Перенаправляем на страницу входа
                          window.location.href = '/login';
                        }}
                        className="registrar-btn-lg registrar-btn-accent"
                        onMouseOver={(e) => e.target.style.background = 'var(--mac-accent-blue-hover)'}
                        onMouseOut={(e) => e.target.style.background = 'var(--mac-accent-blue)'}>

                                <Icon name="key" size="small" className="registrar-icon-mr" />Войти снова
                              </button>

                              <button
                        onClick={() => {
                          // Обновляем данные
                          loadAppointments({ source: 'manual_refresh_button' });
                        }}
                        className="registrar-btn-lg registrar-btn-success"
                        onMouseOver={(e) => e.target.style.background = 'var(--mac-accent-green-hover)'}
                        onMouseOut={(e) => e.target.style.background = 'var(--mac-accent-green)'}>

                                <Icon name="arrow.up.arrow.down" size="small" className="registrar-icon-mr" />Обновить данные
                              </button>

                              <button
                        onClick={() => {
                          // Перезапускаем приложение
                          window.location.reload();
                        }}
                        className="registrar-btn-lg registrar-btn-neutral"
                        onMouseOver={(e) => e.target.style.background = 'var(--mac-text-secondary)'}
                        onMouseOut={(e) => e.target.style.background = 'var(--mac-text-tertiary)'}>

                                <Icon name="arrow.up.arrow.down" size="small" className="registrar-icon-mr" />Перезапустить приложение
                              </button>
                            </div>
                    }
                          <p style={{
                      fontSize: '14px',
                      color: textColor,
                      marginBottom: '24px'
                    }}>
                            {activeTab ?
                      `Сегодня нет записей в отделении ${activeTab === 'cardio' ? 'Кардиология' : activeTab === 'derma' ? 'Дерматология' : activeTab === 'dental' ? 'Стоматология' : activeTab === 'lab' ? 'Лаборатория' : activeTab}` :
                      'Сегодня пока нет записей'}
                          </p>
                          {/* QW-04: empty state 3 of 3 (welcome no-records). */}
                    {/* See empty state 1 above for unification plan. */}
                    <Button
                      variant="primary"
                      onClick={() => {
                        setWizardEditMode(false); // ✅ Сброс режима
                        setWizardInitialData(null); // ✅ Сброс данных
                        setShowWizard(true);
                      }}
                      className="registrar-btn-cta">

                            <Icon name="plus" size="small" className="registrar-icon-mr" />Создать первую запись
                          </Button>
                        </div>
                  }

                    {/* Таблица отображается только если есть данные */}
                    {(appointmentsLoading || filteredAppointments.length > 0) &&
                  <EnhancedAppointmentsTable
                    data={filteredAppointments}
                    rawEntries={appointments} // ⭐ SSOT FIX: Сырые данные для полного Tooltip
                    loading={appointmentsLoading}
                    theme={theme}
                    language={language}
                    outerBorder={true}
                    services={services}
                    showCheckboxes={false} // ✅ Отключаем чекбоксы для регистратуры
                    onRowClick={(row) => {
                      logger.info('Открыть детали записи:', row);
                      // Здесь можно открыть модальное окно с деталями записи
                    }}
                    onActionClick={(action, row, event) => {
                      switch (action) {
                        case 'view':
                          logger.info('Просмотр записи:', row);
                          openRecordPreview(row);
                          break;
                        case 'edit':
                          logger.info('[RegistrarPanel] Открытие мастера редактирования для:', row.patient_fio || row.patient_name);
                          openRecordEditor(row);
                          break;
                        case 'payment':
                          logger.info('Открытие модального окна оплаты для записи (welcome):', row);
                          setPaymentDialog({ open: true, row, paid: false, source: 'welcome' });
                          break;
                        case 'in_cabinet':
                          logger.info('Отправка пациента в кабинет (welcome):', row);
                          updateAppointmentStatus(row.id, 'in_cabinet', '', row);
                          break;
                        case 'call':
                          logger.info('Вызов пациента (welcome):', row);
                          handleStartVisit(row);
                          break;
                        case 'complete':
                          logger.info('Завершение приёма (welcome):', row);
                          updateAppointmentStatus(row.id, 'done', '', row);
                          break;
                        case 'print':
                          logger.info('Печать талона (welcome):', row);
                          setPrintDialog({ open: true, type: 'ticket', data: row });
                          break;
                        case 'more':{
                            // Показать контекстное меню с дополнительными действиями
                            const rect = event?.target?.getBoundingClientRect();
                            setContextMenu({
                              open: true,
                              row,
                              position: {
                                x: rect?.right || event?.clientX || 0,
                                y: rect?.top || event?.clientY || 0
                              }
                            });
                            break;
                          }
                        default:
                          break;
                      }
                    }} />

                  }
                  </div>
                </div>
              </CardContent>
            </Card>
          </AnimatedTransition>
        }

        {/* Онлайн-очередь — extracted to QueueView component (Decomp 6a) */}
        {currentView === 'queue' &&
          <QueueView
            searchParams={searchParams}
            setSearchParams={setSearchParams}
            loadAppointments={loadAppointments}
            getSpacing={getSpacing}
            getFontSize={getFontSize}
            getColor={getColor}
            language={language}
            theme={theme}
            doctors={doctors}
          />
        }


        {/* Основная панель с записями */}
        {(!currentView || currentView !== 'welcome' && currentView !== 'queue') &&
        <div
          id="main-content"
          role="tabpanel"
          aria-labelledby={activeTab ? `${activeTab}-tab` : undefined}
          style={{
            ...tableContainerStyle,
            // Убираем отрицательный отступ для идеальной стыковки с вкладками
            margin: `0 ${isMobile ? '1rem' : '1rem'} ${'2rem'} ${isMobile ? '1rem' : '1rem'}`,
            borderRadius: isMobile ? '0 0 12px 12px' : '0 0 20px 20px',
            maxWidth: 'none',
            width: 'calc(100vw - 32px)'
          }}>
            <div style={{
            ...tableContentStyle,
            padding: isMobile ? '0.5rem' : '1rem'
          }}>

              <div
                style={registrarWorkflowHeaderStyle}
                aria-label="Сводка рабочего списка регистратуры">
                <div className="registrar-worklist-container">
                  <div className="registrar-worklist-meta">
                    Регистратура
                  </div>
                  <h2 style={registrarWorkflowTitleStyle}>
                    Рабочий список: {currentWorklistLabel}
                  </h2>
                  <p style={registrarWorkflowMetaStyle}>
                    {showCalendar ?
                    new Date(historyDate).toLocaleDateString(language === 'ru' ? 'ru-RU' : 'uz-UZ', { day: 'numeric', month: 'long', year: 'numeric' }) :
                    t('today')} · {filteredAppointments.length} {t('tabs_appointments')}
                  </p>
                </div>

                <div style={registrarWorkflowActionsStyle}>
                  {statusFilterLabel &&
                  <Badge variant="warning" style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 'var(--mac-spacing-1)'
                  }}>
                      <Icon name="magnifyingglass" size="small" />
                      Фильтр: {statusFilterLabel}
                    </Badge>
                  }
                  <Badge variant={appointmentsLoading ? 'info' : 'secondary'}>
                    {appointmentsLoading ? t('loading') : `${filteredAppointments.length} ${t('tabs_appointments')}`}
                  </Badge>
                  <Button
                  variant="primary"
                  size="default"
                  onClick={() => {
                    setWizardEditMode(false);
                    setWizardInitialData(null);
                    setShowWizard(true);
                  }}
                  aria-label="Создать новую запись из рабочего списка регистратора"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 'var(--mac-spacing-2)',
                    flexShrink: 0
                  }}>
                    <Icon name="plus" size="small" className="registrar-text-white" />
                    {t('new_appointment')}
                  </Button>
                </div>
              </div>

              {/* QW-01 fix: bulk-action bar removed (was dead UI) */}

              {/* Таблица записей */}
              {appointmentsLoading ?
            <AnimatedLoader.TableSkeleton rows={8} columns={10} /> :
            filteredAppointments.length === 0 && dataSource === 'api' ?
            <div className="registrar-empty-state">
                  <div className="registrar-empty-icon-lg">
                    {/* QW-04: empty state 2 of 3 (worklist empty). */}
                    <Icon name="doc.text" size="large" />
                  </div>
                  <h3 className="registrar-empty-heading" style={{ color: textColor }}>
                    Очередь пуста
                  </h3>
                  <p className="registrar-empty-desc-text" style={{ fontSize: '14px', color: textColor }}>
                    {activeTab ?
                `Сегодня нет записей в отделении ${activeTab === 'cardio' ? 'Кардиология' : activeTab === 'derma' ? 'Дерматология' : activeTab === 'dental' ? 'Стоматология' : activeTab === 'lab' ? 'Лаборатория' : activeTab}` :
                'Сегодня пока нет записей'}
                  </p>
                  <Button
                variant="primary"
                onClick={() => setShowWizard(true)}
                className="registrar-btn-cta">

                    <Icon name="plus" size="small" className="registrar-icon-mr" />Создать первую запись
                  </Button>
                </div> :
            filteredAppointments.length === 0 ?
            <div className="registrar-empty-table">
                  {t('empty_table')}
                </div> :

            <EnhancedAppointmentsTable
              data={filteredAppointments}
              loading={appointmentsLoading}
              theme={theme}
              language={language}
              outerBorder={false}
              services={services}
              showCheckboxes={false} // ✅ Отключаем чекбоксы для регистратуры
              onRowClick={(row) => {
                logger.info('Открыть детали записи:', row);
                // Здесь можно открыть модальное окно с деталями записи
              }}
              onActionClick={(action, row, event) => {
                switch (action) {
                  case 'view':
                    logger.info('Просмотр записи:', row);
                    openRecordPreview(row);
                    break;
                  case 'edit':
                    logger.info('[RegistrarPanel] Открытие мастера редактирования для:', row.patient_fio || row.patient_name);
                    openRecordEditor(row);
                    break;
                  case 'payment':
                    logger.info('Открытие модального окна оплаты для записи:', row);
                    setPaymentDialog({ open: true, row, paid: false, source: 'table' });
                    break;
                  case 'in_cabinet':
                    logger.info('Отправка пациента в кабинет:', row);
                    updateAppointmentStatus(row.id, 'in_cabinet', '', row);
                    break;
                  case 'call':
                    logger.info('Вызов пациента:', row);
                    handleStartVisit(row);
                    break;
                  case 'complete':
                    logger.info('Завершение приёма:', row);
                    updateAppointmentStatus(row.id, 'done', '', row);
                    break;
                  case 'print':
                    logger.info('Печать талона:', row);
                    setPrintDialog({ open: true, type: 'ticket', data: row });
                    break;
                  case 'more':{
                      // Показать контекстное меню с дополнительными действиями
                      const rect = event?.target?.getBoundingClientRect();
                      setContextMenu({
                        open: true,
                        row,
                        position: {
                          x: rect?.right || event?.clientX || 0,
                          y: rect?.top || event?.clientY || 0
                        }
                      });
                      break;
                    }
                  default:
                    break;
                }
              }} />

            }

              {/* Кнопка загрузки дополнительных записей */}
              {paginationInfo.hasMore &&
            <div className="registrar-load-more-bar">
                  <button
                onClick={loadMoreAppointments}
                disabled={paginationInfo.loadingMore}
                aria-label={paginationInfo.loadingMore ? 'Loading more appointments' : 'Load more appointments'}
                className={`registrar-btn-base ${paginationInfo.loadingMore ? 'registrar-btn-neutral' : 'registrar-btn-accent'} registrar-flex`}
                  style={{
                    cursor: paginationInfo.loadingMore ? 'not-allowed' : 'pointer',
                    boxShadow: '0 2px 4px rgba(59, 130, 246, 0.3)'
                  }}>

                    {paginationInfo.loadingMore ?
                <>
                        <div className="registrar-spinner" />
                        Загрузка...
                      </> :

                <>
                        <Icon name="arrow.up.arrow.down" size="small" className="registrar-icon-mr" />Загрузить еще
                      </>
                }
                  </button>
                </div>
            }

              {/* Старая таблица и прежняя конфигурация удалены - используется EnhancedAppointmentsTable */}
            </div>
          </div>
        }
      </div> {/* Закрытие скроллируемого контента */}

      {/* Мастер создания записи */}

      {/* Современные диалоги */}
      <ModernDialog
        isOpen={recordPreviewDialog.open}
        onClose={() => setRecordPreviewDialog({ open: false, row: null })}
        title="Просмотр записи"
        maxWidth="36rem"
        dialogStyle={{
          backgroundColor: 'var(--mac-bg-primary)'
        }}
        actions={[
          {
            label: 'Закрыть',
            variant: 'secondary',
            onClick: () => setRecordPreviewDialog({ open: false, row: null })
          },
          {
            label: 'Редактировать',
            variant: 'primary',
            onClick: () => {
              const row = recordPreviewDialog.row;
              setRecordPreviewDialog({ open: false, row: null });
              if (row) openRecordEditor(row);
            }
          }
        ]}>
        {recordPreviewDialog.row && (
          <div className="registrar-text-primary registrar-grid-gap-md">
            {[
              ['Пациент', recordPreviewDialog.row.patient_fio || recordPreviewDialog.row.patient_name],
              ['Телефон', recordPreviewDialog.row.patient_phone || recordPreviewDialog.row.phone],
              ['Год рождения', recordPreviewDialog.row.patient_birth_year || recordPreviewDialog.row.birth_year],
              ['Пол', normalizePatientGender(recordPreviewDialog.row)],
              ['Отделение', recordPreviewDialog.row.queue_name || recordPreviewDialog.row.department || recordPreviewDialog.row.specialty],
              ['Услуги', formatPreviewList(recordPreviewDialog.row.services || recordPreviewDialog.row.service_details)],
              ['Очередь', formatPreviewList(recordPreviewDialog.row.queue_numbers)],
              ['Статус', recordPreviewDialog.row.status || recordPreviewDialog.row.canonical_status],
              ['Оплата', recordPreviewDialog.row.payment_status || recordPreviewDialog.row.payment_type],
              ['Сумма', recordPreviewDialog.row.cost]
            ].filter(([, value]) => value !== null && value !== undefined && value !== '').map(([label, value]) => (
              <div
                key={label}
                className="registrar-surface"
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'minmax(120px, 0.36fr) minmax(0, 1fr)',
                  gap: '12px',
                  alignItems: 'start'
                }}>
                <span className="registrar-text-secondary" style={{ fontSize: '13px' }}>{label}</span>
                <span style={{ minWidth: 0, overflowWrap: 'anywhere', fontWeight: 500 }}>
                  {String(value)}
                </span>
              </div>
            ))}
          </div>
        )}
      </ModernDialog>

      <CancelDialog
        isOpen={cancelDialog.open}
        onClose={() => setCancelDialog({ open: false, row: null, reason: '' })}
        appointment={cancelDialog.row}
        onCancel={async (appointmentId, reason) => {
          try {
            const data = appointmentId === cancelDialog.row?.id
              ? cancelDialog.row
              : appointments.find((a) => a.id === appointmentId);
            const result = await runRegistrarRecordAction(data, 'cancel', { reason });
            if (!result) return;
            if (!result.success) {
              const successCount = Number(result.success_count || 0);
              const failedCount = Number(result.failed_count || 0);
              if (successCount === 0) {
                throw new Error(result.results?.find((item) => !item.success)?.error || 'cancel_failed');
              }
              notify.warning('Cancelled ' + successCount + '; failed ' + failedCount);
            }
            await loadAppointments({ silent: true, source: 'cancel_complete' });
          } catch (error) {
            logger.error('RegistrarPanel: cancellation failed:', error);
            notify.error(getErrorMessage(error, 'Could not cancel record. Check connection and try again.'));
            throw error;
          }
        }} />


      <PaymentDialog
        isOpen={paymentDialog.open}
        onClose={() => setPaymentDialog({ open: false, row: null, paid: false, source: null })}
        appointment={paymentDialog.row}
        onPaymentSuccess={async (paymentData) => {
          // ✅ ИСПРАВЛЕНО: используем реальный API вызов через handlePayment
          const appointment = paymentDialog.row;
          if (appointment) {
            const updated = await handlePayment(appointment, paymentData);
            if (updated) {
              // Canonical state is refreshed by handlePayment via loadAppointments.
              logger.info('PaymentDialog: Оплата успешна, данные обновлены:', updated);
            }
          }
        }}
        onPrintTicket={(appointment) => {
          const printSource = {
            ...(paymentDialog.row || {}),
            ...(appointment || {})
          };
          setPrintDialog({
            open: true,
            type: 'ticket',
            data: printSource
          });
        }} />


      {/* Модальное окно редактирования пациента */}
      {/* ✨ ЗАКОММЕНТИРОВАНО: Теперь используется AppointmentWizardV2 для редактирования */}
      {/*
           {editPatientModal.open && (
            <EditPatientModal
              isOpen={editPatientModal.open}
              onClose={() => setEditPatientModal({ open: false, patient: null })}
              patient={editPatientModal.patient}
              onSave={async () => {
                // Обновляем список записей после сохранения
                logger.info('[RegistrarPanel] EditPatientModal: onSave вызван, обновляем список');
                await loadAppointments({ source: 'edit_patient_save', silent: false });
              }}
              theme={{ isDark, getColor, getSpacing, getFontSize }}
            />
           )}
           */}

      <PrintDialog
        isOpen={printDialog.open}
        onClose={() => setPrintDialog({ open: false, type: 'ticket', data: null })}
        documentType={printDialog.type || 'ticket'}
        documentData={printDialog.data}
        onPrint={async (printerName, docType, docData) => {
          logger.info('Printing:', { printerName, docType, docData });

          if (docType !== 'ticket') {
            throw new Error(`Неподдерживаемый тип документа: ${docType}`);
          }

          const result = await printPanelTicketInBrowserAsync(docData);
          if (result?.opened && result?.success) {
            return;
          }

          if (!result?.opened) {
            throw new Error('Браузер заблокировал окно печати. Разрешите всплывающие окна для приложения и повторите печать.');
          }

          throw result?.error || new Error('Не удалось подготовить талон к печати. Проверьте данные записи и повторите попытку.');
        }} />


      {/* ✅ Используется только новый мастер (V2) */}
      <AppointmentWizardV2
        isOpen={showWizard}
        editMode={wizardEditMode} // ✨ НОВОЕ: Передаем режим
        initialData={wizardInitialData} // ✨ НОВОЕ: Передаем данные
        activeTab={activeTab} // ✅ ПЕРЕДАЕМ activeTab для фильтрации услуг
        onClose={() => {
          logger.info('AppointmentWizardV2 closing');
          setShowWizard(false);
          setWizardEditMode(false); // ✨ Сброс режима
          setWizardInitialData(null); // ✨ Сброс данных
        }}
        isProcessing={isProcessing}
        setIsProcessing={setIsProcessing}
        onComplete={async (wizardData) => {
          logger.info('AppointmentWizardV2 completed successfully:', wizardData);
          const wasEditMode = wizardEditMode;
          const postWizardPaymentRow = (!wasEditMode || Number(wizardData?.total_amount || 0) > 0)
            ? buildPostWizardPaymentRow(wizardData)
            : null;

          // Обновляем данные (работает и для создания, и для редактирования)
          try {
            // P-004 fix: removed hardcoded 1500ms delay (previously setTimeout(resolve, 1500)).
            // That dead time was added as a workaround for backend batch operations not
            // finishing fast enough — it cost registrars ~60 sec/day of pure wait time.
            // Strategy now: optimistic UI (close wizard + notify success immediately),
            // then reload appointments with force=true. If the first reload returns stale
            // data, a single silent retry is attempted after a short debounce.
            setShowWizard(false);
            setWizardEditMode(false); // ✨ Сброс режима
            setWizardInitialData(null); // ✨ Сброс данных

            const message = wasEditMode ?
              'Запись успешно обновлена!' :
              'Запись успешно создана!';
            notify.success(message);

            // Open payment/print dialog immediately — user can act while data refreshes
            if (postWizardPaymentRow) {
              if (Number(postWizardPaymentRow.cost || 0) > 0) {
                setPaymentDialog({ open: true, row: postWizardPaymentRow, paid: false, source: wasEditMode ? 'wizard-edit' : 'wizard-create' });
              } else {
                setPrintDialog({ open: true, type: 'ticket', data: postWizardPaymentRow });
              }
            }

            // Reload data in the background (does not block UI)
            try {
              await Promise.all([
                loadAppointments({ silent: true, source: 'wizard-complete', force: true }),
                loadIntegratedData(),
              ]);
            } catch (refreshError) {
              // Background refresh failed — single silent retry
              logger.warn('First post-wizard reload failed, retrying once:', refreshError);
              try {
                await loadAppointments({ silent: true, source: 'wizard-complete-retry', force: true });
              } catch (retryError) {
                logger.error('Post-wizard reload retry also failed:', retryError);
              }
            }
          } catch (error) {
            logger.error('Error refreshing data after wizard completion:', error);
            // Не показываем ошибку пользователю, так как запись уже создана
            setShowWizard(false);
            notify.success('Запись создана! Обновите страницу для отображения изменений.');
          }
        }} />


      {/* Старые диалоги удалены - используются современные компоненты CancelDialog, PaymentDialog, PrintDialog */}
      {/* Встроенное модальное окно оплаты удалено - используется PaymentDialog компонент */}
      {/* Встроенный мастер удален - используется AppointmentWizard компонент */}

      {/* Модальное окно слотов */}
      <ModernDialog
        isOpen={showSlotsModal}
        onClose={() => setShowSlotsModal(false)}
        title={`📅 ${t('available_slots')}`}
        maxWidth="32rem"
        dialogStyle={{
          backgroundColor: 'var(--mac-bg-primary)'
        }}
        actions={[
          {
            label: '🌅 ' + t('tomorrow'),
            variant: 'primary',
            onClick: async () => {
              if (!rescheduleData) return;

              // R-43 fix: confirmation dialog для destructive action.
              // Перенос записи — необратимое действие (запись меняет день).
              const ok = await confirm({
                title: 'Перенос на завтра',
                message: 'Перенести запись пациента на завтра?',
                description: 'Запись будет перемещена на завтрашний день. ' +
                  'Текущее время слота может измениться.',
                confirmLabel: 'Перенести',
                cancelLabel: 'Отмена',
                intent: 'primary',
              });
              if (!ok) return;

              try {
                setShowSlotsModal(false);
                const targetVisitId = resolveRescheduleVisitId(rescheduleData);
                if (!targetVisitId) {
                  notify.error('Не удалось определить визит для переноса');
                  return;
                }
                logger.info(`Перенос визита ${targetVisitId} на завтра`);
                await rescheduleTomorrow(targetVisitId);
                notify.success('Визит успешно перенесён на завтра');
                removeRescheduledAppointmentFromView(rescheduleData, targetVisitId);
                setRescheduleData(null);
                loadAppointments({ source: 'reschedule_tomorrow' });
              } catch (e) {
                logger.error('Ошибка переноса на завтра:', e);
                notify.error(getErrorMessage(e, 'Не удалось перенести запись. Проверьте соединение и попробуйте снова.'));
              }
            }
          },
          {
            label: t('select_date'),
            variant: 'secondary',
            // QW-02 fix: previously called window.prompt('Введите дату переноса (YYYY-MM-DD):', currentVal)
            // — a jarring native browser dialog that blocks the tab, has no date picker,
            // no min-date guard, and breaks the macOS-style visual language of the app.
            // Now the date is captured via the inline <input type="date"> rendered in the
            // dialog body (see customRescheduleDate state + date input below). This action
            // validates the captured date and performs the reschedule.
            onClick: async () => {
              if (!rescheduleData) return;

              const dateStr = customRescheduleDate || '';

              if (!dateStr) {
                notify.error('Выберите дату переноса');
                return;
              }

              if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
                notify.error('Неверный формат даты. Используйте YYYY-MM-DD');
                return;
              }

              // Optional guard: prevent rescheduling to a past date
              const today = getLocalDateString();
              if (dateStr < today) {
                notify.error('Нельзя перенести запись на прошедшую дату');
                return;
              }

              // R-43 fix: confirmation dialog для destructive action.
              const ok = await confirm({
                title: 'Перенос на другую дату',
                message: `Перенести запись пациента на ${dateStr}?`,
                confirmLabel: 'Перенести',
                cancelLabel: 'Отмена',
                intent: 'primary',
              });
              if (!ok) return;

              try {
                setShowSlotsModal(false);
                const targetVisitId = resolveRescheduleVisitId(rescheduleData);
                if (!targetVisitId) {
                  notify.error('Не удалось определить визит для переноса');
                  return;
                }
                logger.info(`Перенос визита ${targetVisitId} на ${dateStr}`);
                await rescheduleVisit(targetVisitId, dateStr);
                notify.success(`Визит перенесён на ${dateStr}`);
                removeRescheduledAppointmentFromView(rescheduleData, targetVisitId);
                setRescheduleData(null);
                setCustomRescheduleDate('');
                loadAppointments({ source: 'reschedule_date' });
              } catch (e) {
                logger.error('Ошибка переноса на дату:', e);
                notify.error(getErrorMessage(e, 'Не удалось перенести запись. Проверьте соединение и попробуйте снова.'));
              }
            }
          }
        ]}>
        <div className="registrar-grid-gap-lg">
          <div className="registrar-reschedule-card"
            style={{
              border: `1px solid ${theme === 'dark' ? 'rgba(59, 130, 246, 0.22)' : 'rgba(59, 130, 246, 0.14)'}`,
              backgroundColor: theme === 'dark' ? 'rgba(59, 130, 246, 0.08)' : 'rgba(59, 130, 246, 0.06)'
            }}>
            <div className="registrar-flex-start">
              <div className="registrar-reschedule-icon registrar-text-accent"
                style={{
                  backgroundColor: theme === 'dark' ? 'rgba(59, 130, 246, 0.2)' : 'rgba(59, 130, 246, 0.14)'
                }}>
                📅
              </div>
              <div>
                <div className="registrar-reschedule-title" style={{ color: getColor('textPrimary') }}>
                  Перенос записи
                </div>
                <div className="registrar-reschedule-desc" style={{ color: getColor('textSecondary') }}>
                  Выберите быстрый перенос на завтра или укажите другую дату.
                </div>
              </div>
            </div>
          </div>

          {/* QW-02 fix: inline date picker replacing window.prompt().
              min=today prevents selecting past dates natively in the picker. */}
          <div className="registrar-reschedule-card"
            style={{
              border: `1px solid ${theme === 'dark' ? 'rgba(0,0,0,0.3)' : 'rgba(0,0,0,0.08)'}`,
              backgroundColor: theme === 'dark' ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)'
            }}>
            <label htmlFor="reschedule-custom-date" className="registrar-reschedule-label" style={{ color: getColor('textPrimary') }}>
              Дата переноса
            </label>
            <input
              id="reschedule-custom-date"
              type="date"
              value={customRescheduleDate}
              min={getLocalDateString()}
              aria-label="Дата переноса записи"
              onChange={(e) => setCustomRescheduleDate(e.target.value)}
              className="registrar-reschedule-input"
                style={{
                  border: `1px solid ${theme === 'dark' ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.12)'}`,
                  backgroundColor: theme === 'dark' ? 'rgba(255,255,255,0.05)' : 'var(--mac-bg-primary)',
                  color: getColor('textPrimary')
                }}
            />
            <div className="registrar-reschedule-hint" style={{ color: getColor('textSecondary') }}>
              Выберите дату и нажмите «{t('select_date')}».
            </div>
          </div>
        </div>
      </ModernDialog>

      {/* Контекстное меню */}
      {contextMenu.open &&
      <AppointmentContextMenu
        row={contextMenu.row}
        position={contextMenu.position}
        theme={theme}
        onClose={() => setContextMenu({ open: false, row: null, position: { x: 0, y: 0 } })}
        onAction={handleContextMenuAction} />

      }

      {/* Модуль оплаты */}
      <PaymentManager
        isOpen={showPaymentManager}
        onClose={(result) => {
          setShowPaymentManager(false);
          if (result?.success) {
            // Обновляем данные после успешной оплаты
            loadAppointments();
            loadIntegratedData();
          }
        }} />


      {/* ✅ Форс-мажор модальное окно */}
      <ForceMajeureModal
        isOpen={forceMajeureModal.open}
        onClose={() => setForceMajeureModal({ open: false, specialistId: null, specialistName: '' })}
        specialistId={forceMajeureModal.specialistId}
        specialistName={forceMajeureModal.specialistName}
        onSuccess={(action, result) => {
          logger.info('[RegistrarPanel] Force majeure action completed:', action, result);
          notify.success(action === 'transfer' ? 'Записи перенесены на завтра' : 'Записи отменены с возвратом');
          loadAppointments({ source: 'force_majeure' });
        }} />

      <RoleNotificationCenter userRole="registrar" />
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}

    </div>);

};

export default RegistrarPanel;
