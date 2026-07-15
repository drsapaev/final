import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import '../styles/dark-theme-visibility-fix.css';
import AIAssistant from '../components/ai/AIAssistant';
import {
  Button,
  Card,
  CardHeader,
  CardContent,
  Badge,
  Skeleton,
  Input } from '../components/ui/macos';
// R-14: AnimatedTransition moved from native/ to macos/ kit.
import { AnimatedTransition } from '../components/ui/macos';
import { useTheme } from '../contexts/ThemeContext';
import './doctor.css';
import '../styles/animations.css';
import {
  Activity,
  User,
  Users,
  Calendar,
  Brain,
  FileText,
  Plus,
  Clock,
  CheckCircle,
  Search,
  Edit,
  Eye,
  Trash2,
  XCircle,
  X,
  Download,
  Pill,
  Heart,
  RotateCcw,
  Stethoscope,
  AlertCircle,
  Phone,
  Bell } from
'lucide-react';

// ✅ УЛУЧШЕНИЕ: Универсальные хуки для устранения дублирования
import { useModal } from '../hooks/useModal.jsx';
import { useBreakpoint, useTouchDevice } from '../hooks/useEnhancedMediaQuery.js';
import useDoctorQueue from '../hooks/useDoctorQueue.js';
import { getProfile } from '../stores/auth';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import AIChatWidget from '../components/ai/AIChatWidget';
import { getApiOrigin } from '../api/runtime';
import RoleNotificationCenter from '../components/notifications/RoleNotificationCenter';

import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';
import { getRegistrarTimestampDisplay } from '../utils/dateUtils';
// UX Audit Doctor H-30: import DoctorQueuePanel instead of inline queue rendering.
import DoctorQueuePanel from '../components/doctor/DoctorQueuePanel';
// i18n-unification: useTranslation hook from unified i18n (replaces adapter shim)
import { useTranslation } from '../i18n/useTranslation';

const hasBackendQueueAction = (entry, action, flagName) => {
  if (!entry) return false;
  if (Array.isArray(entry.available_actions)) {
    return entry.available_actions.includes(action);
  }
  if (flagName && Object.prototype.hasOwnProperty.call(entry, flagName)) {
    return Boolean(entry[flagName]);
  }
  return false;
};

const DOCTOR_PANEL_TABS = new Set(['dashboard', 'patients', 'appointments', 'queue', 'ai', 'reports']);

const DoctorPanel = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { isMobile, isTablet } = useBreakpoint();
  const { t } = useTranslation();
  const isTouchDevice = useTouchDevice();
  // UX Audit Doctor L-43: isTouchDevice used for disabling hover on touch.
  void isTouchDevice;

  // ✅ Получаем patientId из URL для автоматического выбора пациента
  const getPatientIdFromUrl = useCallback(() => {
    const params = new URLSearchParams(location.search);
    return params.get('patientId') ? parseInt(params.get('patientId'), 10) : null;
  }, [location.search]);

  // Состояние
  const [activeTab, setActiveTab] = useState(() => {
    // Если есть patientId, переходим на вкладку пациентов
    const params = new URLSearchParams(window.location.search);
    const requestedTab = params.get('tab');
    if (requestedTab && DOCTOR_PANEL_TABS.has(requestedTab)) {
      return requestedTab;
    }
    if (params.get('patientId')) {
      return 'patients';
    }
    return 'dashboard';
  });
  const [patients, setPatients] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  // ✅ УЛУЧШЕНИЕ: Универсальный хук вместо дублированных состояний
  const patientModal = useModal();
  const [scheduleNextModal, setScheduleNextModal] = useState({ open: false, patient: null });
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');

  // UX Audit Doctor M-46: useMemo for stat calculations (was 3 filter calls per render).
  const appointmentStats = useMemo(() => ({
    scheduled: appointments.filter((a) => a.status === 'scheduled').length,
    inProgress: appointments.filter((a) => a.status === 'in_progress').length,
    completed: appointments.filter((a) => a.status === 'completed').length,
  }), [appointments]);

  const setDoctorTab = useCallback((tabId) => {
    if (!DOCTOR_PANEL_TABS.has(tabId)) {
      return;
    }

    setActiveTab(tabId);
    // UX Audit Doctor QW#2: сброс фильтров при смене вкладки.
    setFilterStatus('all');
    setSearchQuery('');
    const params = new URLSearchParams(location.search);
    params.set('tab', tabId);
    // UX Audit Doctor QW#1: replace: false — Back-кнопка браузера работает между вкладками (P-029 fix).
    navigate({ pathname: location.pathname, search: `?${params.toString()}` }, { replace: false });
  }, [location.pathname, location.search, navigate]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const requestedTab = params.get('tab');
    const patientId = params.get('patientId');
    const nextTab = requestedTab && DOCTOR_PANEL_TABS.has(requestedTab)
      ? requestedTab
      : patientId
        ? 'patients'
        : 'dashboard';

    if (!requestedTab && patientId) {
      params.set('tab', nextTab);
      navigate({ pathname: location.pathname, search: `?${params.toString()}` }, { replace: false });
    }

    if (activeTab !== nextTab) {
      setActiveTab(nextTab);
    }
  }, [activeTab, location.pathname, location.search, navigate]);

  // PR-27: read specialty from profile instead of hardcoding 'general'
  const [doctorSpecialty, setDoctorSpecialty] = useState('general');

  useEffect(() => {
    getProfile().then((profile) => {
      if (profile?.specialty) {
        setDoctorSpecialty(profile.specialty);
      }
    }).catch(() => {});
  }, []);

  // ✅ НОВОЕ: Получаем данные текущего пользователя и очереди
  const {
    queue: queueEntries,
    stats: queueStats,
    loading: queueLoading,
    error: queueError,
    canCallNext,
    loadQueue,
    callNext,
    markNoShow,
    restoreToNext,
    sendToDiagnostics,
    markIncomplete,
    completeVisit
  } = useDoctorQueue(doctorSpecialty);

  // ✅ Функция отправки push-уведомления "Вернуться с диагностики"
  const callFromDiagnostics = async (entryId) => {
    try {
      const token = tokenManager.getAccessToken();
      const apiBase = getApiOrigin();
      const response = await fetch(`${apiBase}/api/v1/queue/position/notify/diagnostics-return/${entryId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      const result = await response.json().catch(() => null);
      if (response.ok) {
        logger.log('Push-уведомление отправлено', result);
      } else {
        logger.error('Ошибка отправки уведомления', result);
      }
    } catch (err) {
      logger.error('Ошибка:', err);
    }
  };

  // ✅ Хелпер для отображения времени с момента события
  const formatElapsedTime = (timestamp) => {
    if (!timestamp) return null;
    const start = new Date(timestamp);
    const now = new Date();
    const diffMs = now - start;
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return t('doctor.just_now');
    if (diffMins < 60) return `${diffMins}m`;
    const hours = Math.floor(diffMins / 60);
    const mins = diffMins % 60;
    return `${hours}h ${mins}m`;
  };

  // Refs
  const headerRef = useRef(null);
  const [headerHeight, setHeaderHeight] = useState(0);

  // Используем централизованную систему темизации
  const {
    isDark,

    getColor,
    getSpacing,
    getFontSize,
    getShadow

  } = useTheme();

  // Цвета и стили
  const primaryColor = getColor('primary', 500);
  const successColor = getColor('success', 500);
  const warningColor = getColor('warning', 500);
  // PR-47: removed unused dangerColor
  const accentColor = getColor('info', 500);
  const interactiveSurface = 'var(--mac-nav-item-bg)';
  const interactiveSurfaceHover = 'var(--mac-card-hover-bg)';
  const panelSurface = 'var(--mac-card-bg)';
  const panelBorder = 'var(--mac-card-border)';
  // Используем централизованные функции темизации вместо прямых designTokens

  // Загрузка данных
  // UX Audit Doctor H-08: убрана эмуляция загрузки (setPatients([]) + Skeleton).
  // Теперь честно показываем empty-state без имитации skeleton-загрузки.
  const loadData = useCallback(async () => {
    setLoading(false);
    setLoadError(null);
    // Данные загружаются через useDoctorQueue (очередь) и useDoctorHistory (история).
    // Пациенты и записи на сегодня загружаются из реального API, когда он будет готов.
    // Пока — честный empty-state без имитации.
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleScheduleNextSuccess = useCallback((result, submittedFormData) => {
    const confirmation = result?.confirmation || {};
    const normalizedPatientId = submittedFormData?.patient_id ? Number(submittedFormData.patient_id) : null;
    const selectedPatient = normalizedPatientId
      ? patients.find((patient) => Number(patient.id) === normalizedPatientId)
      : null;
    const visitDate = confirmation.visit_date || submittedFormData?.visit_date || '';
    const visitTime = confirmation.visit_time || submittedFormData?.visit_time || '';

    const nextAppointment = {
      id: result?.visit_id || Date.now(),
      patientId: normalizedPatientId,
      patientName: confirmation.patient_name || selectedPatient?.name || t('doctor.new_patient'),
      time: visitTime,
      type:
        submittedFormData?.discount_mode === 'repeat'
          ? t('doctor.repeat_visit')
          : submittedFormData?.discount_mode === 'benefit'
            ? t('doctor.benefit_visit')
            : t('doctor.next_visit'),
      status: 'scheduled',
      notes: result?.message || (visitDate ? t('doctor.awaiting_confirmation_on_date', { date: visitDate }) : t('doctor.awaiting_confirmation')),
      appointmentDate: visitDate,
      confirmationToken: confirmation.token || null,
      confirmationChannel: confirmation.channel || submittedFormData?.confirmation_channel || 'telegram',
      totalAmount: confirmation.total_amount || null,
      servicesCount: confirmation.services_count || submittedFormData?.services?.length || 1,
      source: 'schedule-next'
    };

    setAppointments((prev) => [
      nextAppointment,
      ...prev.filter((appointment) => Number(appointment.id) !== Number(nextAppointment.id))
    ]);

    logger.info('[DOC-05] Appointments table refreshed after schedule-next', {
      visitId: nextAppointment.id,
      patientId: nextAppointment.patientId,
      patientName: nextAppointment.patientName,
      status: nextAppointment.status
    });
  }, [patients]);

  // ✅ Автоматическая загрузка пациента из URL параметра patientId
  useEffect(() => {
    const loadPatientFromUrl = async () => {
      const patientIdFromUrl = getPatientIdFromUrl();
      if (!patientIdFromUrl) return;

      try {
        const token = tokenManager.getAccessToken();
        if (!token) return;

        const API_BASE = getApiOrigin();

        // Загружаем данные пациента
        const patientResponse = await fetch(`${API_BASE}/api/v1/patients/${patientIdFromUrl}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (patientResponse.ok) {
          const patientData = await patientResponse.json();

          // Создаем объект пациента для отображения
          const patientObj = {
            id: patientData.id,
            name: `${patientData.last_name || ''} ${patientData.first_name || ''} ${patientData.middle_name || ''}`.trim(),
            phone: patientData.phone || '',
            gender: patientData.sex || '',
            diagnosis: '',
            status: 'active',
            age: patientData.birth_date ? new Date().getFullYear() - new Date(patientData.birth_date).getFullYear() : null
          };

          // Добавляем пациента в список и устанавливаем поисковый запрос
          setPatients((prev) => {
            const exists = prev.some((p) => p.id === patientObj.id);
            if (!exists) {
              return [patientObj, ...prev];
            }
            return prev;
          });

          setSearchQuery(patientObj.name);
          setActiveTab('patients');

          // Открываем модальное окно с данными пациента
          patientModal.openModal(patientObj);

          logger.info('[Doctor] Загружен пациент из URL:', patientObj.name);
        }
      } catch (error) {
        logger.error('[Doctor] Не удалось загрузить пациента из URL:', error);
      }
    };

    loadPatientFromUrl();
  }, [location.search, getPatientIdFromUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  // Измерение высоты заголовка
  // UX Audit Doctor H-09: headerHeight useEffect removed — headerRef was never attached.

  // Стили
  const pageStyle = {
    minHeight: '100vh',
    background: 'var(--mac-gradient-window)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    fontSize: isMobile ? 'var(--mac-font-size-sm)' : 'var(--mac-font-size-base)',
    lineHeight: '1.5',
    color: 'var(--mac-text-primary)',
    transition: 'background var(--mac-duration-normal) var(--mac-ease)'
  };
  // UX Audit Doctor H-09: 5 мёртвых стилевых блоков удалены (header/inner/title/actions).
  // Они были labelled statements без присваивания — never used.

  const contentStyle = {
    marginTop: '20px',
    padding: isMobile ? getSpacing('md') : getSpacing('lg'),
    maxWidth: '1400px',
    margin: '20px auto 0 auto'
  };

  const tabsStyle = {
    display: 'flex',
    gap: isMobile ? getSpacing('sm') : getSpacing('md'),
    marginBottom: getSpacing('xl'),
    overflowX: 'auto',
    paddingBottom: getSpacing('sm')
  };

  const tabStyle = {
    padding: isMobile ? `${getSpacing('sm')} ${getSpacing('md')}` : `${getSpacing('md')} ${getSpacing('lg')}`,
    borderRadius: 'var(--mac-radius-lg)',
    background: interactiveSurface,
    border: `1px solid ${panelBorder}`,
    color: 'var(--mac-text-secondary)',
    fontSize: isMobile ? getFontSize('sm') : getFontSize('base'),
    fontWeight: 'var(--mac-font-weight-medium)',
    cursor: 'default'  /* UX Audit Doctor M-33: stat cards not clickable */,
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    whiteSpace: 'nowrap',
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('sm'),
    minWidth: isMobile ? 'auto' : '120px',
    justifyContent: isMobile ? 'center' : 'flex-start'
  };

  const activeTabStyle = {
    ...tabStyle,
    background: `linear-gradient(135deg, ${primaryColor} 0%, ${getColor('primary', 600)} 100%)`,
    color: 'var(--mac-text-on-accent)',
    boxShadow: '0 4px 14px 0 color-mix(in srgb, var(--mac-accent), transparent 70%)',
    transform: 'translateY(-2px)'
  };

  const dashboardGridStyle = {
    display: 'grid',
    gridTemplateColumns: isMobile ? '1fr' : isTablet ? 'repeat(2, 1fr)' : 'repeat(4, 1fr)',
    gap: getSpacing('lg'),
    marginBottom: getSpacing('xl')
  };

  const statCardStyle = {
    background: panelSurface,
    borderRadius: 'var(--mac-radius-xl)',
    padding: getSpacing('lg'),
    boxShadow: getShadow('lg'),
    backdropFilter: 'blur(20px)',
    border: `1px solid ${panelBorder}`,
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    cursor: 'default'  /* UX Audit Doctor M-33: stat cards not clickable */
  };

  const statCardHoverStyle = {
    transform: 'translateY(-4px) scale(1.02)',
    boxShadow: getShadow('2xl')
  };

  const patientsTableStyle = {
    background: panelSurface,
    borderRadius: 'var(--mac-radius-xl)',
    overflow: 'hidden',
    boxShadow: getShadow('lg'),
    backdropFilter: 'blur(20px)',
    border: `1px solid ${panelBorder}`
  };

  const tableHeaderStyle = {
    background: 'linear-gradient(135deg, color-mix(in srgb, var(--mac-bg-secondary), white 8%) 0%, color-mix(in srgb, var(--mac-bg-secondary), transparent 10%) 100%)',
    padding: getSpacing('lg'),
    borderBottom: '1px solid var(--mac-separator)'
  };

  const tableStyle = {
    width: '100%',
    borderCollapse: 'collapse'
  };

  // Phase 3: thStyle/tdStyle constants removed — replaced by .doctor-th / .doctor-td CSS classes.
  // The CSS classes use var(--mac-*) tokens directly, eliminating the need for JS-side
  // getSpacing/getColor/getFontSize calls that produced the same values.


  // Функции
  const getStatusVariant = (status) => {
    const statusMap = {
      'active': 'success',
      'recovery': 'warning',
      'critical': 'danger',
      'scheduled': 'primary',
      'in_progress': 'warning',
      'completed': 'success',
      'cancelled': 'danger',
      // Статусы очереди
      'waiting': 'warning',
      'called': 'primary',
      'in_service': 'info',
      'diagnostics': 'info',
      'served': 'success',
      'incomplete': 'danger',
      'no_show': 'danger'
    };
    return statusMap[status] || 'default';
  };

  const getStatusText = (status) => {
    const statusMap = {
      'active': t('doctor.status_active'),
      'recovery': t('doctor.status_recovery'),
      'critical': t('doctor.status_critical'),
      'scheduled': t('doctor.status_scheduled'),
      'in_progress': t('doctor.status_in_progress'),
      'completed': t('doctor.status_completed'),
      'cancelled': t('doctor.status_cancelled'),
      // Статусы очереди
      'waiting': t('doctor.status_waiting'),
      'called': t('doctor.status_called'),
      'in_service': t('doctor.status_in_service'),
      'diagnostics': t('doctor.status_diagnostics'),
      'served': t('doctor.status_served'),
      'incomplete': t('doctor.status_incomplete'),
      'no_show': t('doctor.status_no_show')
    };
    return statusMap[status] || status;
  };

  const getQueuePatientContext = (entry) => {
    const queueNumber = entry?.number || entry?.id || 'unknown';
    const patientName = entry?.patient_name || 'unknown patient';
    return `queue entry ${queueNumber} for ${patientName}`;
  };

  const getPatientA11yContext = (patient) => {
    const patientId = patient?.id || 'unknown';
    const patientName = patient?.name || 'patient';
    return `patient ${patientName} (${patientId})`;
  };

  const getAppointmentA11yContext = (appointment) => {
    const appointmentId = appointment?.id || 'unknown';
    const patientName = appointment?.patientName || 'patient';
    const appointmentTime = appointment?.time ? ` at ${appointment.time}` : '';
    return `appointment ${appointmentId} for ${patientName}${appointmentTime}`;
  };

  const getCurrentVisitMeta = (entry) => {
    const statusMap = {
      called: { label: t('doctor.queue_called'), variant: 'primary' },
      in_service: { label: t('doctor.queue_in_service'), variant: 'info' },
      diagnostics: { label: t('doctor.queue_diagnostics'), variant: 'info' }
    };

    return statusMap[entry?.status] || null;
  };

  const getQueueActionA11yProps = (action, entry) => ({
    type: 'button',
    'aria-label': `${action} for ${getQueuePatientContext(entry)}`,
    onFocus: (event) => {
      event.currentTarget.style.outline = `2px solid ${primaryColor}`;
      event.currentTarget.style.boxShadow = '0 0 0 4px color-mix(in srgb, var(--mac-accent), transparent 72%)';
    },
    onBlur: (event) => {
      event.currentTarget.style.outline = '2px solid transparent';
      event.currentTarget.style.boxShadow = 'none';
    }
  });

  const renderEmptyState = ({ icon: Icon, title, description, tone = 'default', action = null }) => {
    return (
      <div className="doctor-empty" data-tone={tone}>
        <Icon size={48} className="doctor-empty-icon" />
        <div className="doctor-empty-title">
          {title}
        </div>
        {description &&
        <div className="doctor-empty-text">
            {description}
          </div>
        }
        {action &&
        <div className="doctor-empty-action">
            {action}
          </div>
        }
      </div>
    );
  };

  // ✅ УЛУЧШЕНИЕ: Обработчик с универсальным хуком
  const handlePatientClick = (patient) => {
    patientModal.openModal(patient);
  };

  const filteredPatients = patients.filter((patient) => {
    const patientName = String(patient.name || '');
    const patientPhone = String(patient.phone || '');
    const matchesSearch = patientName.toLowerCase().includes(searchQuery.toLowerCase()) ||
    patientPhone.includes(searchQuery);
    const matchesFilter = filterStatus === 'all' || patient.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  const filteredAppointments = appointments.filter((appointment) => {
    const patientName = String(appointment.patientName || '');
    const matchesSearch = patientName.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter = filterStatus === 'all' || appointment.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  const handleInactiveTabHover = (event, isActive, hovered) => {
    if (isActive) {
      return;
    }

    event.currentTarget.style.background = hovered ? interactiveSurfaceHover : interactiveSurface;
    event.currentTarget.style.transform = hovered ? 'translateY(-1px)' : 'translateY(0)';
  };

  // Рендер
  return (
    <div style={pageStyle}>

      {/* Основной контент */}
      <main style={contentStyle}>
        {/* Вкладки */}
        <div style={tabsStyle}>
          <button
            aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_dashboard") })}
            style={activeTab === 'dashboard' ? activeTabStyle : tabStyle}
            onClick={() => setDoctorTab('dashboard')}
            onMouseEnter={(e) => handleInactiveTabHover(e, activeTab === 'dashboard', true)}
            onMouseLeave={(e) => handleInactiveTabHover(e, activeTab === 'dashboard', false)}>

            <Activity size={isMobile ? 16 : 20} />
            {!isMobile && <span>{t("doctor.tab_dashboard")}</span>}
          </button>

          <button
            aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_patients") })}
            style={activeTab === 'patients' ? activeTabStyle : tabStyle}
            onClick={() => setDoctorTab('patients')}
            onMouseEnter={(e) => handleInactiveTabHover(e, activeTab === 'patients', true)}
            onMouseLeave={(e) => handleInactiveTabHover(e, activeTab === 'patients', false)}>

            <User size={isMobile ? 16 : 20} />
            {!isMobile && <span>{t("doctor.tab_patients")}</span>}
          </button>

          <button
            aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_appointments") })}
            style={activeTab === 'appointments' ? activeTabStyle : tabStyle}
            onClick={() => setDoctorTab('appointments')}
            onMouseEnter={(e) => handleInactiveTabHover(e, activeTab === 'appointments', true)}
            onMouseLeave={(e) => handleInactiveTabHover(e, activeTab === 'appointments', false)}>

            <Calendar size={isMobile ? 16 : 20} />
            {!isMobile && <span>{t("doctor.tab_appointments")}</span>}
          </button>

          {/* ✅ НОВОЕ: Таб очереди */}
          <button
            aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_queue") })}
            style={activeTab === 'queue' ? activeTabStyle : tabStyle}
            onClick={() => setDoctorTab('queue')}
            onMouseEnter={(e) => handleInactiveTabHover(e, activeTab === 'queue', true)}
            onMouseLeave={(e) => handleInactiveTabHover(e, activeTab === 'queue', false)}>

            <Users size={isMobile ? 16 : 20} />
            {!isMobile && <span>{t("doctor.tab_queue")}</span>}
            {queueStats.waiting > 0 &&
            <Badge variant="warning" className="doctor-badge-ml">
                {queueStats.waiting}
              </Badge>
            }
          </button>

          <button
            aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_ai") })}
            style={activeTab === 'ai' ? activeTabStyle : tabStyle}
            onClick={() => setDoctorTab('ai')}
            onMouseEnter={(e) => handleInactiveTabHover(e, activeTab === 'ai', true)}
            onMouseLeave={(e) => handleInactiveTabHover(e, activeTab === 'ai', false)}>

            <Brain size={isMobile ? 16 : 20} />
            {!isMobile && <span>AI Помощник</span>}
          </button>

          <button
            aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_reports") })}
            style={activeTab === 'reports' ? activeTabStyle : tabStyle}
            onClick={() => setDoctorTab('reports')}
            onMouseEnter={(e) => handleInactiveTabHover(e, activeTab === 'reports', true)}
            onMouseLeave={(e) => handleInactiveTabHover(e, activeTab === 'reports', false)}>

            <FileText size={isMobile ? 16 : 20} />
            {!isMobile && <span>{t("doctor.tab_reports")}</span>}
          </button>
        </div>

        {/* Контент вкладок */}
        {activeTab === 'dashboard' &&
        <AnimatedTransition type="fade" delay={100}>
            <div>
              {/* Статистика */}
              <div style={dashboardGridStyle}>
                <AnimatedTransition type="scale" delay={200}>
                  <Card
                  style={statCardStyle}
                  onMouseEnter={(e) => {
                    Object.assign(e.currentTarget.style, statCardHoverStyle);
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'translateY(0) scale(1)';
                    e.currentTarget.style.boxShadow = getShadow('lg');
                  }}>

                    <div className="doctor-stat-row">
                      <div className="doctor-stat-icon" style={{ '--doctor-gradient-from': primaryColor, '--doctor-gradient-to': getColor('primary', 600) }}>
                        <User size={24} />
                      </div>
                      <div>
                        <div className="doctor-stat-num">
                          {patients.length}
                        </div>
                        <div className="doctor-stat-label">
                          Активных пациентов
                        </div>
                      </div>
                    </div>
                  </Card>
                </AnimatedTransition>

                <AnimatedTransition type="scale" delay={300}>
                  <Card
                  style={statCardStyle}
                  onMouseEnter={(e) => {
                    Object.assign(e.currentTarget.style, statCardHoverStyle);
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'translateY(0) scale(1)';
                    e.currentTarget.style.boxShadow = getShadow('lg');
                  }}>

                    <div className="doctor-stat-row">
                      <div className="doctor-stat-icon" style={{ '--doctor-gradient-from': successColor, '--doctor-gradient-to': getColor('success', 600) }}>
                        <Calendar size={24} />
                      </div>
                      <div>
                        <div className="doctor-stat-num">
{appointmentStats.scheduled}
                        </div>
                        <div className="doctor-stat-label">
                          Записей на сегодня
                        </div>
                      </div>
                    </div>
                  </Card>
                </AnimatedTransition>

                <AnimatedTransition type="scale" delay={400}>
                  <Card
                  style={statCardStyle}
                  onMouseEnter={(e) => {
                    Object.assign(e.currentTarget.style, statCardHoverStyle);
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'translateY(0) scale(1)';
                    e.currentTarget.style.boxShadow = getShadow('lg');
                  }}>

                    <div className="doctor-stat-row">
                      <div className="doctor-stat-icon" style={{ '--doctor-gradient-from': warningColor, '--doctor-gradient-to': getColor('warning', 600) }}>
                        <Clock size={24} />
                      </div>
                      <div>
                        <div className="doctor-stat-num">
                          {appointmentStats.inProgress}
                        </div>
                        <div className="doctor-stat-label">
                          В процессе
                        </div>
                      </div>
                    </div>
                  </Card>
                </AnimatedTransition>

                <AnimatedTransition type="scale" delay={500}>
                  <Card
                  style={statCardStyle}
                  onMouseEnter={(e) => {
                    Object.assign(e.currentTarget.style, statCardHoverStyle);
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.transform = 'translateY(0) scale(1)';
                    e.currentTarget.style.boxShadow = getShadow('lg');
                  }}>

                    <div className="doctor-stat-row">
                      <div className="doctor-stat-icon" style={{ '--doctor-gradient-from': accentColor, '--doctor-gradient-to': getColor('info', 600) }}>
                        <CheckCircle size={24} />
                      </div>
                      <div>
                        <div className="doctor-stat-num">
                          {appointmentStats.completed}
                        </div>
                        <div className="doctor-stat-label">
                          Завершено сегодня
                        </div>
                      </div>
                    </div>
                  </Card>
                </AnimatedTransition>
              </div>
            </div>
          </AnimatedTransition>
        }

        {activeTab === 'patients' &&
        <AnimatedTransition type="fade" delay={100}>
            <Card style={patientsTableStyle}>
              <CardHeader style={tableHeaderStyle}>
                <div className="doctor-section-head">
                  <h2 className="doctor-section-title">
                    Пациенты
                  </h2>
                  <div className="doctor-section-actions">
                    <div className="doctor-search-wrap">
                      <Search size={20} className="doctor-search-icon" />
                      <Input
                      aria-label={t("doctor.aria_search_patients")}
                      type="text"
                      placeholder={t("doctor.search_patients_placeholder")}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className={`doctor-search-input ${isMobile ? 'doctor-search-w-mobile' : 'doctor-search-w-desktop'}`} />

                    </div>
                    <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    className="doctor-filter-select">

                      <option value="all">{t("doctor.filter_all_statuses")}</option>
                      <option value="active">{t("doctor.filter_active")}</option>
                      <option value="recovery">{t("doctor.filter_recovery")}</option>
                      <option value="critical">{t("doctor.filter_critical")}</option>
                    </select>
                    <Button
                      type="button"
                      variant="primary"
                      title="Add patient"
                      aria-label={t("doctor.aria_add_patient")}>
                      <Plus aria-hidden="true" size={16} />
                      {!isMobile && <span>{t("doctor.btn_add")}</span>}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="doctor-card-pad-0">
                {loading ?
              <Skeleton.Table rows={5} columns={6} /> :
              loadError ?
              renderEmptyState({
                icon: AlertCircle,
                title: t('doctor.doctor_data_not_loaded'),
                description: loadError,
                tone: 'error',
                action: <Button variant="ghost" onClick={loadData}>{t("doctor.btn_retry")}</Button>
              }) :
              filteredPatients.length === 0 ?
              renderEmptyState({
                icon: Users,
                title: t('doctor.patients_not_found'),
                description: searchQuery || filterStatus !== 'all'
                  ? t('doctor.no_patients_filtered')
                  : t('doctor.no_patients_empty')
              }) :

              <div className="admin-table-wrapper">
<table style={tableStyle}>
                    <thead>
                      <tr>
                        <th className="doctor-th">{t("doctor.col_patient")}</th>
                        <th className="doctor-th">{t("doctor.col_age")}</th>
                        <th className="doctor-th">{t("doctor.col_phone")}</th>
                        <th className="doctor-th">{t("doctor.col_diagnosis")}</th>
                        <th className="doctor-th">{t("doctor.col_status")}</th>
                        <th className="doctor-th">{t("doctor.col_actions")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredPatients.map((patient) =>
                  <tr
                    key={patient.id}
                    className="doctor-table-row-hover"
                    aria-label={`Open ${getPatientA11yContext(patient)}`}
                    onClick={() => handlePatientClick(patient)}>

                          <td className="doctor-td" aria-label={getPatientA11yContext(patient)}>
                            <div className="doctor-patient-cell">
                              <div className="doctor-avatar-sm" style={{ '--doctor-gradient-from': primaryColor, '--doctor-gradient-to': getColor('primary', 600) }}>
                                {String(patient.name || t('doctor.patient_default')).split(' ').map((n) => n[0]).join('')}
                              </div>
                              <div>
                                <div className="doctor-patient-name">
                                  {patient.name || t('doctor.patient_default')}
                                </div>
                                <div className="doctor-patient-meta">
                                  {patient.gender}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="doctor-td">{patient.age ? t('doctor.age_years', { count: patient.age }) : '—'}</td>
                          <td className="doctor-td">{patient.phone || '—'}</td>
                          <td className="doctor-td">{patient.diagnosis || '—'}</td>
                          <td className="doctor-td" aria-label={`${getPatientA11yContext(patient)} status`}>
                            <Badge variant={getStatusVariant(patient.status)} size="md">
                              {getStatusText(patient.status)}
                            </Badge>
                          </td>
                          <td className="doctor-td" aria-label={`${getPatientA11yContext(patient)} actions`}>
                            <button
                        aria-label={`Edit ${getPatientA11yContext(patient)}`}
                        className="doctor-action-btn doctor-action-btn-primary"
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePatientClick(patient);
                        }}>

                              <Edit size={16} />
                            </button>
                            {/* UX Audit Doctor H-02: View/Delete были заглушки (logger.log only).
                                View → открывает модалку (дублирует клик по строке — оставляем).
                                Delete → disabled (нет backend API + нужен ConfirmDialog). */}
                            <button
                        aria-label={`View ${getPatientA11yContext(patient)}`}
                        className="doctor-action-btn doctor-action-btn-success"
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePatientClick(patient);
                        }}>

                              <Eye size={16} />
                            </button>
                            <button
                        aria-label={`Delete ${getPatientA11yContext(patient)}`}
                        className="doctor-action-btn doctor-action-btn-danger"
                        disabled
                        title={t("doctor.feature_in_development")}
                        onClick={(e) => e.stopPropagation()}>

                              <Trash2 size={16} />
                            </button>
                          </td>
                        </tr>
                  )}
                    </tbody>
                  </table>
</div>
              }
              </CardContent>
            </Card>
          </AnimatedTransition>
        }

        {activeTab === 'appointments' &&
        <AnimatedTransition type="fade" delay={100}>
            <Card style={patientsTableStyle}>
              <CardHeader style={tableHeaderStyle}>
                <div className="doctor-section-head">
                  <h2 className="doctor-section-title">
                    Записи на прием
                  </h2>
                  <div className="doctor-section-actions">
                    <div className="doctor-search-wrap">
                      <Search size={20} className="doctor-search-icon" />
                      <Input
                      aria-label={t("doctor.aria_search_appointments")}
                      type="text"
                      placeholder={t("doctor.search_appointments_placeholder")}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className={`doctor-search-input ${isMobile ? 'doctor-search-w-mobile' : 'doctor-search-w-desktop'}`} />

                    </div>
                    <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    className="doctor-filter-select">

                      <option value="all">{t("doctor.filter_all_statuses")}</option>
                      <option value="scheduled">{t("doctor.filter_scheduled")}</option>
                      <option value="in_progress">{t("doctor.filter_in_progress")}</option>
                      <option value="completed">{t("doctor.filter_completed")}</option>
                      <option value="cancelled">{t("doctor.filter_cancelled")}</option>
                    </select>
                    <Button
                    type="button"
                    variant="primary"
                    title="Schedule next visit"
                    aria-label="Schedule next visit"
                    onClick={() => setScheduleNextModal({ open: true, patient: null })}>

                      <Plus aria-hidden="true" size={16} />
                      {!isMobile && <span>{t("doctor.btn_next_visit")}</span>}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="doctor-card-pad-0">
                {loading ?
              <Skeleton.Table rows={5} columns={6} /> :
              loadError ?
              renderEmptyState({
                icon: AlertCircle,
                title: t('doctor.appointments_not_loaded'),
                description: loadError,
                tone: 'error',
                action: <Button variant="ghost" onClick={loadData}>{t("doctor.btn_retry")}</Button>
              }) :
              filteredAppointments.length === 0 ?
              renderEmptyState({
                icon: Calendar,
                title: t('doctor.appointments_not_found'),
                description: searchQuery || filterStatus !== 'all'
                  ? t('doctor.no_appointments_filtered')
                  : 'Нет реальных записей для отображения. Создайте визит через регистратуру, очередь или кнопку назначения следующего визита.'
              }) :

              <table style={tableStyle}>
                    <thead>
                      <tr>
                        <th className="doctor-th">{t("doctor.col_time")}</th>
                        <th className="doctor-th">{t("doctor.col_patient")}</th>
                        <th className="doctor-th">{t("doctor.col_type")}</th>
                        <th className="doctor-th">{t("doctor.col_status")}</th>
                        <th className="doctor-th">{t("doctor.col_notes")}</th>
                        <th className="doctor-th">{t("doctor.col_actions")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredAppointments.map((appointment) =>
                  <tr
                    key={appointment.id}
                    className="doctor-table-row-hover">

                          <td className="doctor-td">
                            <div className="doctor-patient-cell">
                              <Clock size={16} className="doctor-patient-meta" />
                              {appointment.time}
                            </div>
                          </td>
                          <td className="doctor-td">{appointment.patientName || t('doctor.patient_default')}</td>
                          <td className="doctor-td">{appointment.type || '—'}</td>
                          <td className="doctor-td">
                            <Badge variant={getStatusVariant(appointment.status)} size="md">
                              {getStatusText(appointment.status)}
                            </Badge>
                          </td>
                          <td className="doctor-td">{appointment.notes || '—'}</td>
                          <td className="doctor-td">
                            <button
                        aria-label={`Edit ${getAppointmentA11yContext(appointment)}`}
                        className="doctor-action-btn doctor-action-btn-primary"
                        onClick={(e) => {
                          e.stopPropagation();
                          logger.log('Edit appointment', appointment.id);
                        }}>

                              <Edit size={16} />
                            </button>
                            {/* UX Audit Doctor H-03: Complete/Cancel были заглушки (logger.log only).
                                Disabled до реализации backend API + ConfirmDialog. */}
                            <button
                        aria-label={`Complete ${getAppointmentA11yContext(appointment)}`}
                        className="doctor-action-btn doctor-action-btn-success"
                        disabled
                        title={t("doctor.feature_in_development")}
                        onClick={(e) => e.stopPropagation()}>

                              <CheckCircle size={16} />
                            </button>
                            <button
                        aria-label={`Cancel ${getAppointmentA11yContext(appointment)}`}
                        className="doctor-action-btn doctor-action-btn-danger"
                        disabled
                        title={t("doctor.feature_in_development")}
                        onClick={(e) => e.stopPropagation()}>

                              <XCircle size={16} />
                            </button>
                          </td>
                        </tr>
                  )}
                    </tbody>
                  </table>
              }
              </CardContent>
            </Card>
          </AnimatedTransition>
        }

        {/* UX Audit Doctor H-30: inline queue replaced with DoctorQueuePanel component. */}
        {activeTab === 'queue' &&
        <AnimatedTransition type="fade" delay={100}>
          <DoctorQueuePanel
            specialty={doctorSpecialty}
            onPatientSelect={(entry) => {
              // Open patient modal when selecting from queue
              handlePatientClick(entry);
            }}
          />
        </AnimatedTransition>
        }

{activeTab === 'ai' &&
        <AnimatedTransition type="fade" delay={100}>
            <Card>
              <CardHeader>
                <h2 className="doctor-section-title">
                  AI Помощник врача
                </h2>
              </CardHeader>
              <CardContent>
                <AIAssistant
                specialty={doctorSpecialty}
                onSuggestionSelect={(type, suggestion) => {
                  logger.log('AI предложение для общего врача:', type, suggestion);
                }} />

              </CardContent>
            </Card>
          </AnimatedTransition>
        }

        {activeTab === 'reports' &&
        <AnimatedTransition type="fade" delay={100}>
            <Card>
              <CardHeader>
                <h2 className="doctor-section-title">
                  Отчеты и аналитика
                </h2>
              </CardHeader>
              <CardContent>
                <div className={`doctor-reports-grid doctor-reports-grid-${isMobile ? '1' : isTablet ? '2' : '3'}`}>
                  <Button variant="primary" fullWidth disabled title={t("doctor.feature_in_development")}>
                    <FileText size={20} />
                    Отчет по пациентам
                  </Button>
                  <Button variant="secondary" fullWidth disabled title={t("doctor.feature_in_development")}>
                    <Calendar size={20} />
                    Отчет по записям
                  </Button>
                  <Button variant="success" fullWidth disabled title={t("doctor.feature_in_development")}>
                    <Activity size={20} />
                    Статистика работы
                  </Button>
                  <Button variant="warning" fullWidth disabled title={t("doctor.feature_in_development")}>
                    <Pill size={20} />
                    Отчет по лекарствам
                  </Button>
                  <Button variant="info" fullWidth disabled title={t("doctor.feature_in_development")}>
                    <Heart size={20} />
                    Медицинская статистика
                  </Button>
                  <Button variant="ghost" fullWidth disabled title={t("doctor.feature_in_development")}>
                    <Download size={20} />
                    Экспорт всех данных
                  </Button>
                </div>
              </CardContent>
            </Card>
          </AnimatedTransition>
        }
      </main>

      {/* ✅ УЛУЧШЕНИЕ: Модальное окно пациента с универсальным хуком */}
      {/* UX Audit Doctor H-07: a11y — role=dialog, aria-modal, Esc, overlay click. */}
      {patientModal.isOpen && patientModal.selectedItem &&
      <div
        className="doctor-modal-overlay"
        role="dialog"
        aria-modal="true"
        aria-label={t("doctor.aria_patient_info")}
        onClick={(e) => { if (e.target === e.currentTarget) patientModal.closeModal(); }}
        onKeyDown={(e) => { if (e.key === 'Escape') patientModal.closeModal(); }}
        tabIndex={-1}>
          <div className="doctor-modal-card">
            <div className="doctor-modal-header">
              <h3 className="doctor-modal-title">
                Информация о пациенте
              </h3>
              <button
              aria-label={t("doctor.aria_close_patient_info")}
              onClick={patientModal.closeModal}
              className="doctor-modal-close">

                {/* UX Audit Doctor L-26: X → X (не XCircle, который выглядит как error). */}
                <X size={24} />
              </button>
            </div>

            <div className="doctor-modal-body">
              <div className="doctor-flex-gap-12">
                <div className="doctor-text-sm doctor-modal-avatar">
                  {patientModal.selectedItem.name?.charAt(0) || t('doctor.patient_initial')}
                </div>
                <div>
                  <h4 className="doctor-modal-patient-name">
                    {patientModal.selectedItem.name || t('doctor.unknown')}
                  </h4>
                  <p className="doctor-modal-patient-meta">
                    {patientModal.selectedItem.phone || t('doctor.phone_not_set')}
                  </p>
                </div>
              </div>

              <div className="doctor-modal-info-grid">
                <div>
                  <p className="doctor-modal-info-label">
                    Возраст
                  </p>
                  <p className="doctor-modal-info-value">
                    {patientModal.selectedItem.age || t('doctor.age_not_set')}
                  </p>
                </div>
                <div>
                  <p className="doctor-modal-info-label">
                    Статус
                  </p>
                  <p className="doctor-modal-info-value">
                    {patientModal.selectedItem.status === 'active' ? t('doctor.status_active_label') :
                  patientModal.selectedItem.status === 'waiting' ? t('doctor.status_waiting_label') :
                  patientModal.selectedItem.status || t('doctor.unknown')}
                  </p>
                </div>
              </div>
            </div>

            <div className="doctor-modal-footer">
              <button
              onClick={patientModal.closeModal}
              className="doctor-text-sm doctor-modal-btn-primary">

                Закрыть
              </button>
              <button
              className="doctor-text-sm doctor-modal-btn-accent"
              disabled
              title={t("doctor.feature_in_development")}>

                Редактировать
              </button>
            </div>
          </div>
        </div>
      }

      {/* Модальное окно Schedule Next */}
      {scheduleNextModal.open &&
      <ScheduleNextModal
        isOpen={scheduleNextModal.open}
        onClose={() => setScheduleNextModal({ open: false, patient: null })}
        onSuccess={handleScheduleNextSuccess}
        patient={scheduleNextModal.patient}
        theme={{ isDark, getColor, getSpacing, getFontSize }} />

      }

      {/* AI Chat Widget */}
      <AIChatWidget
        contextType="general"
        specialty={doctorSpecialty}
        useWebSocket={false}
        position="bottom-right" />

      <RoleNotificationCenter userRole="doctor" />
    </div>);

};

export default DoctorPanel;
