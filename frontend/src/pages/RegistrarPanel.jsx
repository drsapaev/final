import { useState, useEffect, useCallback, useRef, useMemo, memo, startTransition } from 'react';
import PropTypes from 'prop-types';
import { useSearchParams, useLocation, useNavigate } from 'react-router-dom';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import AppointmentContextMenu from '../components/tables/AppointmentContextMenu';
import ModernTabs from '../components/navigation/ModernTabs';
import {
  Button, Badge, Icon,
  Input } from '../components/ui/macos';
import { AnimatedLoader } from '../components/ui';
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
// Decomp 6b: WelcomeView extracted to component
import WelcomeView from './registrar/views/WelcomeView';
// Strategic Direction 3: navigation helpers for canonical nested routes
import { getViewFromPath } from './registrar/registrarNavigation';

// Decomp step 1: helpers extracted to ./registrar/registrarHelpers.js
import {
  REGISTRAR_TAB_LABEL_KEYS,
  REGISTRAR_STATUS_LABEL_KEYS,
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

// Modern queue manager — extracted to QueueView component (Decomp 6a)
// Modern statistics — extracted to WelcomeView component (Decomp 7a)

// Модальное окно редактирования пациента
// ✨ ЗАКОММЕНТИРОВАНО: Теперь используется AppointmentWizardV2 для редактирования
// import EditPatientModal from '../components/common/EditPatientModal';

// Утилиты для работы с датами
import { getLocalDateString, formatRegistrarDate } from '../utils/dateUtils';
import { rescheduleTomorrow, rescheduleVisit } from '../api/visits';
// Note: formatNetworkErrorMessage + isNetworkFetchError moved to useRegistrarData.js (Decomp 4)
import { getErrorMessage } from '../utils/errorHandler';
import {
  adaptTimeFields,
  aggregatePatientsForAllDepartments as aggregateRegistrarPatients,
  sortRegistrarRowsForPresentation
} from '../utils/registrarAggregation';

// ⭐ SSOT: Centralized service code resolver
import { toServiceCode as ssotToServiceCode } from '../utils/serviceCodeResolver';

// API client
import { api } from '../api/client';
// UX Audit Registrar #1: getPatient() — централизованный доступ к /patients/{id}.
// Раньше здесь был raw fetch() с ручным Authorization-хедером.
import { getPatient } from '../api/patients';
// ⭐ BATCH API: Для атомарных операций с записями пациента (см. BATCH_UPDATE_ARCHITECTURE.md)


// ✅ Форс-мажор модальное окно
import ForceMajeureModal from '../components/registrar/ForceMajeureModal';
// UX Audit Registrar #14: extracted DataSourceIndicator and CSV utilities.
import DataSourceIndicator from './registrar/DataSourceIndicator';
import { generateCSV, downloadCSV } from './registrar/registrarCsv';

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
    // Phase 3: rely solely on canonical path-derived view.
    // Legacy ?view= and ?tab= params are auto-redirected to canonical paths
    // by the Phase 2 redirect useEffect below, so they never need to be
    // parsed here. The redirect preserves all other query params.
    return getViewFromPath(location.pathname);
  }, [location.pathname]);

  // ✅ Phase 2: redirect legacy ?view=welcome|queue to canonical paths
  // /registrar?view=welcome → /registrar/welcome
  // /registrar?view=queue   → /registrar/queue
  // Preserves all other query params (q, status, date, patientId, dept).
  // The redirect is replace-only (no history pollution) and runs once per
  // legacy-view occurrence.
  useEffect(() => {
    const legacyView = searchParams.get('view');
    if (legacyView !== 'welcome' && legacyView !== 'queue') return;
    // Only redirect when on the bare /registrar path (not already on a sub-path)
    if (location.pathname !== '/registrar') return;

    const params = new URLSearchParams(searchParams);
    params.delete('view');
    params.delete('tab');
    const qs = params.toString();
    const target = qs ? `/registrar/${legacyView}?${qs}` : `/registrar/${legacyView}`;
    navigate(target, { replace: true });
  }, [searchParams, location.pathname, navigate]);

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
        // UX Audit Registrar #1: raw fetch() с ручным Authorization-хедером
        // заменён на getPatient() из api/patients.
        // Auth-token добавляется автоматически axios-interceptor'ом в api/client.js.
        // 401/403 обрабатываются интерсептором (redirect to login или refresh).
        const patientData = await getPatient(patientIdFromUrl);
        const patientName = `${patientData.last_name || ''} ${patientData.first_name || ''}`.trim();

        // Устанавливаем поисковый запрос с именем пациента
        setSearchParams((prev) => {
          const newParams = new URLSearchParams(prev);
          newParams.set('q', patientName);
          return newParams;
        });

        // UX Audit R-3.6: убрано логирование patientName (PII leak).
        logger.info('[Registrar] Загружен пациент из URL (patientId matched)');
      } catch (error) {
        // 404 — пациент не найден, не логируем как error.
        const status = error?.response?.status;
        if (status !== 404) {
          logger.error('[Registrar] Не удалось загрузить пациента:', error);
        }
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
  const [printDialog, setPrintDialog] = useState({ open: false, type: 'ticket', data: null });
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
  const [showSlotsModal, setShowSlotsModal] = useState(false);
  // QW-02 fix: hold the date the user picks in the inline date input inside the
  // reschedule slots dialog. Replaces the previous window.prompt() call that was
  // jarring, blocking, and lacked a date picker.
  const [customRescheduleDate, setCustomRescheduleDate] = useState('');
  // R-27 fix: optional time picker for reschedule (HH:MM)
  const [customRescheduleTime, setCustomRescheduleTime] = useState('');
  const autoRefresh = true; // Новые состояния для интеграции с админ панелью
  // Decomp 3: reschedule helpers extracted to useRegistrarReschedule hook
  const {
    resolveRescheduleVisitId,
    removeRescheduledAppointmentFromView,
  } = useRegistrarReschedule({ setAppointments });
  const [doctors, setDoctors] = useState([]);const [services, setServices] = useState({});const [showCalendar, setShowCalendar] = useState(false);const [historyDate, setHistoryDate] = useState(getLocalDateString());const [tempDateInput, setTempDateInput] = useState(getLocalDateString());const language = useMemo(() => localStorage.getItem('language') || localStorage.getItem('app_language') || 'ru', []); // Выбор врача остаётся явным: URL-параметр или ручной выбор в очереди
  // QW-06 fix: translations moved to ./registrarTranslations.js (was 50+ inline keys).
  // EN translations added (previously missing — EN users saw RU fallback).
  // Full migration to locales/{ru,uz,en}.js deferred until useTranslation.jsx
  // is refactored to use centralized locale files (see audit §8, Direction 3).
  const t = useMemo(() => getRegistrarTranslator(language), [language]);
  const currentWorklistLabel = t(REGISTRAR_TAB_LABEL_KEYS[activeTab] || 'tabs_appointments');
  const statusFilterLabel = statusFilter ? t(REGISTRAR_STATUS_LABEL_KEYS[statusFilter] || statusFilter) : null;
  const { theme, getSpacing, getFontSize, getColor } = useTheme();
  // Адаптивные цвета из централизованной системы темизации
  // DS-2 fix: replaced --color-* variables with --mac-* canonical tokens
  const textColor = 'var(--mac-text-primary)';

  // Phase 3: pageStyle, tableContainerStyle, tableContentStyle constants
  // removed — replaced by .registrar-page-root, .registrar-table-container,
  // .registrar-table-content CSS classes with data-breakpoint attribute
  // for responsive font-size / padding / border-radius variants.

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
      if (!token) {
        logger.warn('Токен аутентификации отсутствует, показываем пустое состояние');
        startTransition(() => {
          if (!silent) setDataSource('api');
          setAppointments([]);
        });
        return;
      }


      // Используем новый эндпоинт для получения очередей на указанную дату
      // Если календарь открыт, используем historyDate, иначе сегодня
      const urlDate = searchParams.get('date');
      const dateParam = showCalendar && historyDate ? historyDate : urlDate || getLocalDateString();

      const params = new URLSearchParams();
      params.append('target_date', dateParam);



      const response = await api.get('/registrar/queues/today', { params: { target_date: dateParam } });

      // Axios successful response
      const data = response.data;

      // Новый формат: данные сгруппированы по специальностям
      let appointmentsData = [];

      if (data && typeof data === 'object') {
        // Обрабатываем формат от эндпоинта registrar_integration.py
        if (data.queues && Array.isArray(data.queues)) {
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
              ...adaptTimeFields(entry, data),
              // Keep queueTime (computed above) as queue_time fallback for backward compat
              queue_time: queueTime,
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
              session_id: fullEntry.session_id || null,

              // P1 fix: pass through lab report summary so registrar can see
              // if lab results are ready for this patient's visit.
              latest_lab_report: fullEntry.latest_lab_report ?? null,
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
        sessionStorage.removeItem('auth_token');  // PR-39 / P0-2;
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

  // UX Audit R-1.3: debounce 1000ms удалён.
  // Раньше: setTimeout 1s + onBlur дублировали применение даты, создавая
  // «мёртвую» секунду без визуального отклика (Nielsen #2).
  // Теперь: дата применяется только через onBlur в WelcomeView (стандартный
  // паттерн для date-picker'ов) или через нативный onChange календаря.

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

  // UX Audit Registrar #17: Keyboard shortcuts для продуктивности регистратора.
  // Ctrl+N — новая запись (открыть wizard)
  // Esc — закрыть wizard/dialogs (если открыт)
  // Не срабатывает когда фокус в input/textarea (чтобы не мешать вводу).
  useEffect(() => {
    const handleKeyDown = (event) => {
      // Ctrl+N — новая запись
      if ((event.ctrlKey || event.metaKey) && event.key === 'n') {
        // Не срабатываем в input/textarea/select
        const tag = event.target?.tagName?.toLowerCase();
        if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
        event.preventDefault();
        if (!showWizard) {
          setWizardEditMode(false);
          setWizardInitialData(null);
          setShowWizard(true);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showWizard]);

  // UX Audit R-1.7: lastQueueJoin polling (2s) удалён.
  // Раньше: setInterval(checkLastQueueJoin, 2000) проверял localStorage
  // каждые 2 секунды — 60 проверок в минуту, даже когда очередь не используется.
  // Теперь: обновление приходит через `queueUpdated` window-event listener
  // (строки ниже), который запускается WebSocket'ом ModernQueueManager.
  // Для fallback между вкладками можно использовать BroadcastChannel,
  // но polling localStorage — это неэффективный паттерн.

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
        // UX Audit R-3.6: убрано логирование patient_fio (PII leak).
        logger.info(`  📌 Entry[${idx}]: id=${entry.id}, queue_tag=${entry.queue_tag}, queue_time=${entry.queue_time}`);
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
        // UX Audit R-3.6: убрано логирование patient_fio (PII leak).
        logger.info(`  - appointment_id=${a.id}: ${a.queue_numbers?.length || 0} queue_numbers`);
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
  // UX Audit Registrar #14: DataSourceIndicator, generateCSV, downloadCSV
  // extracted to ./registrar/DataSourceIndicator.jsx and ./registrar/registrarCsv.js.


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

    // UX Audit R-3.6: убрано логирование patient_fio (PII leak).
    logger.info('[RegistrarPanel] Opening edit wizard for appointment:', row?.id);
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
          // UX Audit R-2.5: используем нативный <a> anchor вместо window.open().
          // window.open() может блокироваться браузером как pop-up, т.к. этот
          // handler вызывается не из прямого user-gesture (через context menu).
          // Нативный anchor — стандартный паттерн для tel: ссылок.
          const link = document.createElement('a');
          link.href = `tel:${sanitizedPhone}`;
          link.style.display = 'none';
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
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
    <div
      className="registrar-page-root"
      data-breakpoint={isMobile ? 'mobile' : isTablet ? 'tablet' : 'desktop'}
      role="main"
      aria-label="Панель регистратора">
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
            // Phase 2: navigate to canonical path (replaces legacy ?view=welcome)
            const p = new URLSearchParams(searchParams);
            p.delete('q');
            p.delete('status');
            p.delete('view');
            p.delete('tab');
            const qs = p.toString();
            navigate(qs ? `/registrar/welcome?${qs}` : '/registrar/welcome', { replace: true });
          }}
          className="registrar-breadcrumb-link"
        >
          Регистратура
        </button>
        {activeTab && (
          <>
            <Icon name="chevron.right" size="small" className="registrar-breadcrumb-separator" aria-hidden="true" />
            <span>{queueProfiles.find(p => p.key === activeTab)?.title || activeTab}</span>
          </>
        )}
        {searchQuery && (
          <>
            <Icon name="chevron.right" size="small" className="registrar-breadcrumb-separator" aria-hidden="true" />
            <span>Поиск: «{searchQuery}»</span>
          </>
        )}
        {showWizard && (
          <>
            <Icon name="chevron.right" size="small" className="registrar-breadcrumb-separator" aria-hidden="true" />
            <span>{wizardEditMode ? 'Редактирование' : 'Новая запись'}</span>
          </>
        )}
      </nav>

      {/* Современные вкладки */}
      {(!currentView || currentView !== 'welcome' && currentView !== 'queue') &&
      <div className="registrar-tabs-wrapper">
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
        {/* Экран приветствия — extracted to WelcomeView component (Decomp 6b) */}
        {currentView === 'welcome' && (
          <WelcomeView
            t={t}
            language={language}
            theme={theme}
            textColor={textColor}
            appointments={appointments}
            departmentStats={departmentStats}
            dataSource={dataSource}
            appointmentsLoading={appointmentsLoading}
            filteredAppointments={filteredAppointments}
            services={services}
            activeTab={activeTab}
            historyDate={historyDate}
            showCalendar={showCalendar}
            tempDateInput={tempDateInput}
            loadAppointments={loadAppointments}
            setShowWizard={setShowWizard}
            setWizardEditMode={setWizardEditMode}
            setWizardInitialData={setWizardInitialData}
            setShowPaymentManager={setShowPaymentManager}
            setHistoryDate={setHistoryDate}
            setShowCalendar={setShowCalendar}
            setTempDateInput={setTempDateInput}
            setSearchParams={setSearchParams}
            navigate={navigate}
            setPaymentDialog={setPaymentDialog}
            setPrintDialog={setPrintDialog}
            setContextMenu={setContextMenu}
            openRecordPreview={openRecordPreview}
            openRecordEditor={openRecordEditor}
            updateAppointmentStatus={updateAppointmentStatus}
            handleStartVisit={handleStartVisit}
            generateCSV={generateCSV}
            downloadCSV={downloadCSV}
            DataSourceIndicator={() => (
              <DataSourceIndicator
                dataSource={dataSource}
                count={appointments.length}
                paginationInfo={paginationInfo}
                onRetry={loadAppointments}
              />
            )}
          />
        )}

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
          className="registrar-table-container"
          data-breakpoint={isMobile ? 'mobile' : 'desktop'}>
            <div
            className="registrar-table-content"
            data-breakpoint={isMobile ? 'mobile' : 'desktop'}>

              <div
                className="registrar-workflow-header"
                aria-label="Сводка рабочего списка регистратуры">
                <div className="registrar-worklist-container">
                  <div className="registrar-worklist-meta">
                    Регистратура
                  </div>
                  <h2 className="registrar-workflow-title">
                    Рабочий список: {currentWorklistLabel}
                  </h2>
                  <p className="registrar-workflow-meta">
                    {showCalendar ?
                    // PR-13: use formatRegistrarDate to avoid browser-local timezone issues
                    // historyDate is YYYY-MM-DD (Tashkent), parse as Tashkent midnight
                    formatRegistrarDate(`${historyDate}T00:00:00+05:00`, language === 'ru' ? 'ru-RU' : 'uz-UZ') :
                    t('today')} · {filteredAppointments.length} {t('tabs_appointments')}
                  </p>
                </div>

                <div className="registrar-workflow-actions">
                  {statusFilterLabel &&
                  <Badge variant="warning" className="registrar-inline-flex-tight">
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
                  className="registrar-inline-flex registrar-inline-flex-shrink">
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
                  <h3 className="registrar-empty-heading registrar-empty-heading-text">
                    Очередь пуста
                  </h3>
                  <p className="registrar-empty-desc-text registrar-empty-desc-fixed">
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
              showCheckboxes={true} // UX Audit Registrar #13: включаем чекбоксы для bulk print
              onRowClick={(row) => {
                logger.info('Открыть детали записи:', row);
                // Здесь можно открыть модальное окно с деталями записи
              }}
              onActionClick={async (action, row, event) => {
                switch (action) {
                  case 'view':
                    logger.info('Просмотр записи:', row);
                    openRecordPreview(row);
                    break;
                  case 'edit':
                    // UX Audit R-3.6: убрано логирование patient_fio (PII leak).
                    logger.info('[RegistrarPanel] Открытие мастера редактирования для appointment:', row.id);
                    openRecordEditor(row);
                    break;
                  case 'payment':
                    logger.info('Открытие модального окна оплаты для записи:', row);
                    setPaymentDialog({ open: true, row, paid: false, source: 'table' });
                    break;
                  case 'in_cabinet': {
                    // UX Audit Registrar #2: window.confirm() → useConfirm hook.
                    // Раньше: if (!window.confirm(`Отправить пациента "..." в кабинет?`)) break;
                    // Теперь: macOS-style ConfirmDialog через useConfirm.
                    const inCabinetName = row.patient_fio || row.patient_name || '';
                    const inCabinetOk = await confirm({
                      title: 'Отправить в кабинет',
                      message: `Отправить пациента «${inCabinetName}» в кабинет?`,
                      confirmLabel: 'Отправить',
                      cancelLabel: 'Отмена',
                      intent: 'primary',
                    });
                    if (!inCabinetOk) break;
                    logger.info('Отправка пациента в кабинет:', row);
                    updateAppointmentStatus(row.id, 'in_cabinet', '', row);
                    break;
                  }
                  case 'call':
                    logger.info('Вызов пациента:', row);
                    handleStartVisit(row);
                    break;
                  case 'complete': {
                    // UX Audit Registrar #2: window.confirm() → useConfirm hook.
                    const completeName = row.patient_fio || row.patient_name || '';
                    const completeOk = await confirm({
                      title: 'Завершение приёма',
                      message: `Завершить приём пациента «${completeName}»?`,
                      confirmLabel: 'Завершить',
                      cancelLabel: 'Отмена',
                      intent: 'primary',
                    });
                    if (!completeOk) break;
                    logger.info('Завершение приёма:', row);
                    updateAppointmentStatus(row.id, 'done', '', row);
                    break;
                  }
                  case 'print':
                    logger.info('Печать талона:', row);
                    setPrintDialog({ open: true, type: 'ticket', data: row });
                    break;
                  // UX Audit Registrar #4: cancel и reschedule теперь доступны
                  // как inline кнопки, а не только через context menu.
                  case 'reschedule':
                    setRescheduleData(row);
                    setShowSlotsModal(true);
                    break;
                  case 'cancel':
                    setCancelDialog({ open: true, row, reason: '' });
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
                className={`registrar-btn-base ${paginationInfo.loadingMore ? 'registrar-btn-neutral' : 'registrar-btn-accent'} registrar-flex registrar-load-more-btn`}
                aria-disabled={paginationInfo.loadingMore}>

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
                className="registrar-surface registrar-preview-row">
                <span className="registrar-text-secondary registrar-preview-label">{label}</span>
                <span className="registrar-preview-value">
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
          // UX Audit: закрываем PaymentDialog при открытии PrintDialog.
          setPaymentDialog({ open: false, row: null, paid: false, source: null });
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
                setCustomRescheduleDate('');
                setCustomRescheduleTime('');
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
            // Now the date is captured via the inline <Input type="date"> rendered in the
            // dialog body (see customRescheduleDate state + date input below). This action
            // validates the captured date and performs the reschedule.
            onClick: async () => {
              if (!rescheduleData) return;

              const dateStr = customRescheduleDate || '';
              const timeStr = (customRescheduleTime || '').trim();

              if (!dateStr) {
                notify.error('Выберите дату переноса');
                return;
              }

              if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
                notify.error('Неверный формат даты. Используйте YYYY-MM-DD');
                return;
              }

              // R-27 fix: validate optional time (HH:MM)
              if (timeStr && !/^\d{2}:\d{2}$/.test(timeStr)) {
                notify.error('Неверный формат времени. Используйте HH:MM');
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
                message: timeStr
                  ? `Перенести запись пациента на ${dateStr} в ${timeStr}?`
                  : `Перенести запись пациента на ${dateStr}?`,
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
                logger.info(`Перенос визита ${targetVisitId} на ${dateStr}${timeStr ? ' ' + timeStr : ''}`);
                await rescheduleVisit(targetVisitId, dateStr, timeStr || undefined);
                notify.success(`Визит перенесён на ${dateStr}${timeStr ? ' ' + timeStr : ''}`);
                removeRescheduledAppointmentFromView(rescheduleData, targetVisitId);
                setRescheduleData(null);
                setCustomRescheduleDate('');
                setCustomRescheduleTime('');
                loadAppointments({ source: 'reschedule_date' });
              } catch (e) {
                logger.error('Ошибка переноса на дату:', e);
                notify.error(getErrorMessage(e, 'Не удалось перенести запись. Проверьте соединение и попробуйте снова.'));
              }
            }
          }
        ]}>
        <div className="registrar-grid-gap-lg">
          <div className="registrar-reschedule-card registrar-reschedule-card-accent">
            <div className="registrar-flex-start">
              <div className="registrar-reschedule-icon registrar-text-accent registrar-reschedule-icon-bg">
                📅
              </div>
              <div>
                <div className="registrar-reschedule-title registrar-reschedule-title-text">
                  Перенос записи
                </div>
                <div className="registrar-reschedule-desc registrar-reschedule-desc-text">
                  Выберите быстрый перенос на завтра или укажите другую дату.
                </div>
              </div>
            </div>
          </div>

          {/* QW-02 fix: inline date picker replacing window.prompt().
              min=today prevents selecting past dates natively in the picker. */}
          <div className="registrar-reschedule-card registrar-reschedule-card-neutral">
            <label htmlFor="reschedule-custom-date" className="registrar-reschedule-label registrar-reschedule-label-text">
              Дата переноса
            </label>
            <Input
              id="reschedule-custom-date"
              type="date"
              value={customRescheduleDate}
              min={getLocalDateString()}
              aria-label="Дата переноса записи"
              onChange={(e) => setCustomRescheduleDate(e.target.value)}
              className="registrar-reschedule-input registrar-reschedule-input-themed"
            />
            {/* R-27 fix: optional time picker (HH:MM) */}
            <label htmlFor="reschedule-custom-time" className="registrar-reschedule-label registrar-reschedule-label-block">
              Время переноса (необязательно)
            </label>
            <Input
              id="reschedule-custom-time"
              type="time"
              value={customRescheduleTime}
              aria-label="Время переноса записи"
              onChange={(e) => setCustomRescheduleTime(e.target.value)}
              className="registrar-reschedule-input registrar-reschedule-input-themed"
            />
            <div className="registrar-reschedule-hint registrar-reschedule-hint-text">
              Выберите дату и нажмите «{t('select_date')}». Время необязательно — если не указано, сохранится текущее.
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
