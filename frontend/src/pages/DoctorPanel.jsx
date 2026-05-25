import { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import '../styles/dark-theme-visibility-fix.css';
import AIAssistant from '../components/ai/AIAssistant';
import {
  Button,
  Card,
  CardHeader,
  CardContent,
  Badge,


  Skeleton } from
'../components/ui/macos';
import AnimatedTransition from '../components/ui/native/AnimatedTransition';
import { useTheme } from '../contexts/ThemeContext';
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
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import AIChatWidget from '../components/ai/AIChatWidget';
import { getApiOrigin } from '../api/runtime';
import RoleNotificationCenter from '../components/notifications/RoleNotificationCenter';

import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';

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

const DoctorPanel = () => {
  const location = useLocation();
  const { isMobile, isTablet } = useBreakpoint();void
  useTouchDevice();

  // ✅ Получаем patientId из URL для автоматического выбора пациента
  const getPatientIdFromUrl = useCallback(() => {
    const params = new URLSearchParams(location.search);
    return params.get('patientId') ? parseInt(params.get('patientId'), 10) : null;
  }, [location.search]);

  // Состояние
  const [activeTab, setActiveTab] = useState(() => {
    // Если есть patientId, переходим на вкладку пациентов
    const params = new URLSearchParams(window.location.search);
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
  } = useDoctorQueue('general');

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
    if (diffMins < 1) return '<1m';
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
  const dangerColor = getColor('danger', 500);
  const accentColor = getColor('info', 500);
  const interactiveSurface = 'var(--mac-nav-item-bg)';
  const interactiveSurfaceHover = 'var(--mac-card-hover-bg)';
  const panelSurface = 'var(--mac-card-bg)';
  const panelBorder = 'var(--mac-card-border)';
  // Используем централизованные функции темизации вместо прямых designTokens

  // Загрузка данных
  const loadData = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setPatients([]);
      setAppointments([]);
    } catch (error) {
      logger.error('Ошибка загрузки данных врача:', error);
      setLoadError('Не удалось загрузить пациентов и записи врача. Повторите попытку или откройте очередь.');
    } finally {
      setLoading(false);
    }
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
      patientName: confirmation.patient_name || selectedPatient?.name || 'Новый пациент',
      time: visitTime,
      type:
        submittedFormData?.discount_mode === 'repeat'
          ? 'Повторный прием'
          : submittedFormData?.discount_mode === 'benefit'
            ? 'Льготный визит'
            : 'Следующий визит',
      status: 'scheduled',
      notes: result?.message || (visitDate ? `Ожидает подтверждения на ${visitDate}` : 'Ожидает подтверждения'),
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
  useEffect(() => {
    if (headerRef.current) {
      setHeaderHeight(headerRef.current.offsetHeight);
    }
  }, [isMobile, isTablet]);

  // Стили
  const pageStyle = {
    minHeight: '100vh',
    background: 'var(--mac-gradient-window)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    fontSize: isMobile ? 'var(--mac-font-size-sm)' : 'var(--mac-font-size-base)',
    lineHeight: '1.5',
    color: 'var(--mac-text-primary)',
    transition: 'background var(--mac-duration-normal) var(--mac-ease)'
  };void

  {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 1000,
    background: `linear-gradient(135deg, ${primaryColor} 0%, ${getColor('primary', 600)} 100%)`,
    backdropFilter: 'blur(20px)',
    borderBottom: `1px solid ${getColor('primary', 200)}`,
    boxShadow: getShadow('lg')
  };void

  {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: isMobile ? getSpacing('md') : getSpacing('lg'),
    maxWidth: '1400px',
    margin: '0 auto'
  };void

  {
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('sm'),
    color: 'var(--mac-text-on-accent)',
    fontSize: isMobile ? getFontSize('lg') : getFontSize('xl'),
    fontWeight: '700',
    textDecoration: 'none'
  };void

  {
    display: 'flex',
    alignItems: 'center',
    gap: isMobile ? getSpacing('sm') : getSpacing('md')
  };

  const contentStyle = {
    marginTop: `${headerHeight + 20}px`,
    padding: isMobile ? getSpacing('md') : getSpacing('lg'),
    maxWidth: '1400px',
    margin: `${headerHeight + 20}px auto 0 auto`
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
    borderRadius: '12px',
    background: interactiveSurface,
    border: `1px solid ${panelBorder}`,
    color: 'var(--mac-text-secondary)',
    fontSize: isMobile ? getFontSize('sm') : getFontSize('base'),
    fontWeight: '500',
    cursor: 'pointer',
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
    borderRadius: '20px',
    padding: getSpacing('lg'),
    boxShadow: getShadow('lg'),
    backdropFilter: 'blur(20px)',
    border: `1px solid ${panelBorder}`,
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    cursor: 'pointer'
  };

  const statCardHoverStyle = {
    transform: 'translateY(-4px) scale(1.02)',
    boxShadow: getShadow('2xl')
  };

  const patientsTableStyle = {
    background: panelSurface,
    borderRadius: '20px',
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

  const thStyle = {
    padding: getSpacing('md'),
    textAlign: 'left',
    fontWeight: '600',
    color: getColor('secondary', 700),
    fontSize: getFontSize('sm'),
    borderBottom: `1px solid ${getColor('secondary', 200)}`
  };

  const tdStyle = {
    padding: getSpacing('md'),
    borderBottom: '1px solid color-mix(in srgb, var(--mac-separator), transparent 30%)',
    fontSize: getFontSize('sm'),
    color: 'var(--mac-text-secondary)'
  };

  const actionButtonStyle = {
    padding: getSpacing('xs'),
    borderRadius: '8px',
    border: 'none',
    outline: '2px solid transparent',
    outlineOffset: '2px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: getSpacing('xs')
  };

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
      'active': 'Активен',
      'recovery': 'Выздоравливает',
      'critical': 'Критический',
      'scheduled': 'Запланирован',
      'in_progress': 'В процессе',
      'completed': 'Завершен',
      'cancelled': 'Отменен',
      // Статусы очереди
      'waiting': 'Ожидает',
      'called': 'Вызван',
      'in_service': 'На приёме',
      'diagnostics': 'На обследовании',
      'served': 'Обслужен',
      'incomplete': 'Не завершён',
      'no_show': 'Не явился'
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
      called: { label: 'Текущий прием', variant: 'primary' },
      in_service: { label: 'На приеме', variant: 'info' },
      diagnostics: { label: 'На диагностике', variant: 'info' }
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
    const color = tone === 'error' ? dangerColor : getColor('secondary', 500);
    return (
      <div style={{ padding: getSpacing('xl'), textAlign: 'center', color }}>
        <Icon size={48} style={{ opacity: 0.55, marginBottom: getSpacing('md') }} />
        <div style={{ fontSize: getFontSize('md'), fontWeight: 600, marginBottom: getSpacing('xs') }}>
          {title}
        </div>
        {description &&
        <div style={{ fontSize: getFontSize('sm'), color: getColor('secondary', 500), maxWidth: 520, margin: '0 auto' }}>
            {description}
          </div>
        }
        {action &&
        <div style={{ marginTop: getSpacing('md') }}>
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
    event.currentTarget.style.transform = hovered ? 'translateY(-2px)' : 'translateY(0)';
  };

  // Рендер
  return (
    <div style={pageStyle}>

      {/* Основной контент */}
      <main style={contentStyle}>
        {/* Вкладки */}
        <div style={tabsStyle}>
          <button
            aria-label="Open doctor dashboard tab"
            style={activeTab === 'dashboard' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('dashboard')}
            onMouseEnter={(e) => handleInactiveTabHover(e, activeTab === 'dashboard', true)}
            onMouseLeave={(e) => handleInactiveTabHover(e, activeTab === 'dashboard', false)}>

            <Activity size={isMobile ? 16 : 20} />
            {!isMobile && <span>Панель</span>}
          </button>

          <button
            aria-label="Open patients tab"
            style={activeTab === 'patients' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('patients')}
            onMouseEnter={(e) => handleInactiveTabHover(e, activeTab === 'patients', true)}
            onMouseLeave={(e) => handleInactiveTabHover(e, activeTab === 'patients', false)}>

            <User size={isMobile ? 16 : 20} />
            {!isMobile && <span>Пациенты</span>}
          </button>

          <button
            aria-label="Open appointments tab"
            style={activeTab === 'appointments' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('appointments')}
            onMouseEnter={(e) => handleInactiveTabHover(e, activeTab === 'appointments', true)}
            onMouseLeave={(e) => handleInactiveTabHover(e, activeTab === 'appointments', false)}>

            <Calendar size={isMobile ? 16 : 20} />
            {!isMobile && <span>Записи</span>}
          </button>

          {/* ✅ НОВОЕ: Таб очереди */}
          <button
            aria-label="Open queue tab"
            style={activeTab === 'queue' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('queue')}
            onMouseEnter={(e) => handleInactiveTabHover(e, activeTab === 'queue', true)}
            onMouseLeave={(e) => handleInactiveTabHover(e, activeTab === 'queue', false)}>

            <Users size={isMobile ? 16 : 20} />
            {!isMobile && <span>Очередь</span>}
            {queueStats.waiting > 0 &&
            <Badge variant="warning" style={{ marginLeft: '4px', fontSize: '10px' }}>
                {queueStats.waiting}
              </Badge>
            }
          </button>

          <button
            aria-label="Open AI assistant tab"
            style={activeTab === 'ai' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('ai')}
            onMouseEnter={(e) => handleInactiveTabHover(e, activeTab === 'ai', true)}
            onMouseLeave={(e) => handleInactiveTabHover(e, activeTab === 'ai', false)}>

            <Brain size={isMobile ? 16 : 20} />
            {!isMobile && <span>AI Помощник</span>}
          </button>

          <button
            aria-label="Open reports tab"
            style={activeTab === 'reports' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('reports')}
            onMouseEnter={(e) => handleInactiveTabHover(e, activeTab === 'reports', true)}
            onMouseLeave={(e) => handleInactiveTabHover(e, activeTab === 'reports', false)}>

            <FileText size={isMobile ? 16 : 20} />
            {!isMobile && <span>Отчеты</span>}
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

                    <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('md') }}>
                      <div style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: '50%',
                      background: `linear-gradient(135deg, ${primaryColor} 0%, ${getColor('primary', 600)} 100%)`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--mac-text-on-accent)'
                    }}>
                        <User size={24} />
                      </div>
                      <div>
                        <div style={{ fontSize: getFontSize('2xl'), fontWeight: '700', color: getColor('secondary', 800) }}>
                          {patients.length}
                        </div>
                        <div style={{ fontSize: getFontSize('sm'), color: getColor('secondary', 600) }}>
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

                    <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('md') }}>
                      <div style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: '50%',
                      background: `linear-gradient(135deg, ${successColor} 0%, ${getColor('success', 600)} 100%)`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--mac-text-on-accent)'
                    }}>
                        <Calendar size={24} />
                      </div>
                      <div>
                        <div style={{ fontSize: getFontSize('2xl'), fontWeight: '700', color: getColor('secondary', 800) }}>
                          {appointments.filter((a) => a.status === 'scheduled').length}
                        </div>
                        <div style={{ fontSize: getFontSize('sm'), color: getColor('secondary', 600) }}>
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

                    <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('md') }}>
                      <div style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: '50%',
                      background: `linear-gradient(135deg, ${warningColor} 0%, ${getColor('warning', 600)} 100%)`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--mac-text-on-accent)'
                    }}>
                        <Clock size={24} />
                      </div>
                      <div>
                        <div style={{ fontSize: getFontSize('2xl'), fontWeight: '700', color: getColor('secondary', 800) }}>
                          {appointments.filter((a) => a.status === 'in_progress').length}
                        </div>
                        <div style={{ fontSize: getFontSize('sm'), color: getColor('secondary', 600) }}>
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

                    <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('md') }}>
                      <div style={{
                      width: '48px',
                      height: '48px',
                      borderRadius: '50%',
                      background: `linear-gradient(135deg, ${accentColor} 0%, ${getColor('info', 600)} 100%)`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--mac-text-on-accent)'
                    }}>
                        <CheckCircle size={24} />
                      </div>
                      <div>
                        <div style={{ fontSize: getFontSize('2xl'), fontWeight: '700', color: getColor('secondary', 800) }}>
                          {appointments.filter((a) => a.status === 'completed').length}
                        </div>
                        <div style={{ fontSize: getFontSize('sm'), color: getColor('secondary', 600) }}>
                          Завершено сегодня
                        </div>
                      </div>
                    </div>
                  </Card>
                </AnimatedTransition>
              </div>

              {/* Быстрые действия */}
              <AnimatedTransition type="fade" delay={600}>
                <Card style={{ marginBottom: getSpacing('xl') }}>
                  <CardHeader>
                    <h2 style={{
                    fontSize: getFontSize('xl'),
                    fontWeight: '700',
                    color: getColor('secondary', 800),
                    margin: 0
                  }}>
                      Быстрые действия
                    </h2>
                  </CardHeader>
                  <CardContent>
                    <div style={{
                    display: 'grid',
                    gridTemplateColumns: isMobile ? '1fr' : isTablet ? 'repeat(2, 1fr)' : 'repeat(4, 1fr)',
                    gap: getSpacing('md')
                  }}>
                      <Button variant="primary" fullWidth>
                        <Plus size={20} />
                        Новый пациент
                      </Button>
                      <Button variant="secondary" fullWidth>
                        <Calendar size={20} />
                        Записать на прием
                      </Button>
                      <Button variant="success" fullWidth>
                        <FileText size={20} />
                        Создать отчет
                      </Button>
                      <Button variant="info" fullWidth>
                        <Download size={20} />
                        Экспорт данных
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </AnimatedTransition>
            </div>
          </AnimatedTransition>
        }

        {activeTab === 'patients' &&
        <AnimatedTransition type="fade" delay={100}>
            <Card style={patientsTableStyle}>
              <CardHeader style={tableHeaderStyle}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: getSpacing('md') }}>
                  <h2 style={{
                  fontSize: getFontSize('xl'),
                  fontWeight: '700',
                  color: getColor('secondary', 800),
                  margin: 0
                }}>
                    Пациенты
                  </h2>
                  <div style={{ display: 'flex', gap: getSpacing('md'), alignItems: 'center', flexWrap: 'wrap' }}>
                    <div style={{ position: 'relative' }}>
                      <Search size={20} style={{ position: 'absolute', left: getSpacing('sm'), top: '50%', transform: 'translateY(-50%)', color: getColor('secondary', 400) }} />
                      <input
                      aria-label="Search patients"
                      type="text"
                      placeholder="Поиск пациентов..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      style={{
                        padding: `${getSpacing('sm')} ${getSpacing('sm')} ${getSpacing('sm')} 40px`,
                        border: `1px solid ${getColor('secondary', 200)}`,
                        borderRadius: '12px',
                        fontSize: getFontSize('sm'),
                        width: isMobile ? '200px' : '250px',
                        background: 'white'
                      }} />

                    </div>
                    <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    style={{
                      padding: getSpacing('sm'),
                      border: `1px solid ${getColor('secondary', 200)}`,
                      borderRadius: '12px',
                      fontSize: getFontSize('sm'),
                      background: 'white'
                    }}>

                      <option value="all">Все статусы</option>
                      <option value="active">Активные</option>
                      <option value="recovery">Выздоравливающие</option>
                      <option value="critical">Критические</option>
                    </select>
                    <Button
                      type="button"
                      variant="primary"
                      title="Add patient"
                      aria-label="Add patient">
                      <Plus aria-hidden="true" size={16} />
                      {!isMobile && <span>Добавить</span>}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent style={{ padding: 0 }}>
                {loading ?
              <Skeleton.Table rows={5} columns={6} /> :
              loadError ?
              renderEmptyState({
                icon: AlertCircle,
                title: 'Данные врача не загружены',
                description: loadError,
                tone: 'error',
                action: <Button variant="ghost" onClick={loadData}>Повторить</Button>
              }) :
              filteredPatients.length === 0 ?
              renderEmptyState({
                icon: Users,
                title: 'Пациенты не найдены',
                description: searchQuery || filterStatus !== 'all'
                  ? 'По текущему поиску или фильтру нет пациентов.'
                  : 'Пациенты не подставляются тестовыми данными. Используйте очередь или регистрацию, чтобы открыть реальную карту пациента.'
              }) :

              <table style={tableStyle}>
                    <thead>
                      <tr>
                        <th style={thStyle}>Пациент</th>
                        <th style={thStyle}>Возраст</th>
                        <th style={thStyle}>Телефон</th>
                        <th style={thStyle}>Диагноз</th>
                        <th style={thStyle}>Статус</th>
                        <th style={thStyle}>Действия</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredPatients.map((patient) =>
                  <tr
                    key={patient.id}
                    style={{
                      cursor: 'pointer',
                      transition: 'background-color 0.2s ease'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = getColor('primary', 50);
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                    aria-label={`Open ${getPatientA11yContext(patient)}`}
                    onClick={() => handlePatientClick(patient)}>

                          <td style={tdStyle} aria-label={getPatientA11yContext(patient)}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('sm') }}>
                              <div style={{
                          width: '32px',
                          height: '32px',
                          borderRadius: '50%',
                          background: `linear-gradient(135deg, ${primaryColor} 0%, ${getColor('primary', 600)} 100%)`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'var(--mac-text-on-accent)',
                          fontSize: getFontSize('sm'),
                          fontWeight: '700'
                        }}>
                                {String(patient.name || 'Пациент').split(' ').map((n) => n[0]).join('')}
                              </div>
                              <div>
                                <div style={{ fontWeight: '500', color: getColor('secondary', 800) }}>
                                  {patient.name || 'Пациент'}
                                </div>
                                <div style={{ fontSize: getFontSize('xs'), color: getColor('secondary', 500) }}>
                                  {patient.gender}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td style={tdStyle}>{patient.age ? `${patient.age} лет` : '—'}</td>
                          <td style={tdStyle}>{patient.phone || '—'}</td>
                          <td style={tdStyle}>{patient.diagnosis || '—'}</td>
                          <td style={tdStyle} aria-label={`${getPatientA11yContext(patient)} status`}>
                            <Badge variant={getStatusVariant(patient.status)} size="md">
                              {getStatusText(patient.status)}
                            </Badge>
                          </td>
                          <td style={tdStyle} aria-label={`${getPatientA11yContext(patient)} actions`}>
                            <button
                        aria-label={`Edit ${getPatientA11yContext(patient)}`}
                        style={{ ...actionButtonStyle, background: getColor('primary', 100), color: primaryColor }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePatientClick(patient);
                        }}>

                              <Edit size={16} />
                            </button>
                            <button
                        aria-label={`View ${getPatientA11yContext(patient)}`}
                        style={{ ...actionButtonStyle, background: getColor('success', 100), color: successColor }}
                        onClick={(e) => {
                          e.stopPropagation();
                          logger.log('View patient', patient.id);
                        }}>

                              <Eye size={16} />
                            </button>
                            <button
                        aria-label={`Delete ${getPatientA11yContext(patient)}`}
                        style={{ ...actionButtonStyle, background: getColor('danger', 100), color: dangerColor }}
                        onClick={(e) => {
                          e.stopPropagation();
                          logger.log('Delete patient', patient.id);
                        }}>

                              <Trash2 size={16} />
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

        {activeTab === 'appointments' &&
        <AnimatedTransition type="fade" delay={100}>
            <Card style={patientsTableStyle}>
              <CardHeader style={tableHeaderStyle}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: getSpacing('md') }}>
                  <h2 style={{
                  fontSize: getFontSize('xl'),
                  fontWeight: '700',
                  color: getColor('secondary', 800),
                  margin: 0
                }}>
                    Записи на прием
                  </h2>
                  <div style={{ display: 'flex', gap: getSpacing('md'), alignItems: 'center', flexWrap: 'wrap' }}>
                    <div style={{ position: 'relative' }}>
                      <Search size={20} style={{ position: 'absolute', left: getSpacing('sm'), top: '50%', transform: 'translateY(-50%)', color: getColor('secondary', 400) }} />
                      <input
                      aria-label="Search appointments"
                      type="text"
                      placeholder="Поиск записей..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      style={{
                        padding: `${getSpacing('sm')} ${getSpacing('sm')} ${getSpacing('sm')} 40px`,
                        border: `1px solid ${getColor('secondary', 200)}`,
                        borderRadius: '12px',
                        fontSize: getFontSize('sm'),
                        width: isMobile ? '200px' : '250px',
                        background: 'white'
                      }} />

                    </div>
                    <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    style={{
                      padding: getSpacing('sm'),
                      border: `1px solid ${getColor('secondary', 200)}`,
                      borderRadius: '12px',
                      fontSize: getFontSize('sm'),
                      background: 'white'
                    }}>

                      <option value="all">Все статусы</option>
                      <option value="scheduled">Запланированы</option>
                      <option value="in_progress">В процессе</option>
                      <option value="completed">Завершены</option>
                      <option value="cancelled">Отменены</option>
                    </select>
                    <Button
                    type="button"
                    variant="primary"
                    title="Schedule next visit"
                    aria-label="Schedule next visit"
                    onClick={() => setScheduleNextModal({ open: true, patient: null })}>

                      <Plus aria-hidden="true" size={16} />
                      {!isMobile && <span>Назначить следующий визит</span>}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent style={{ padding: 0 }}>
                {loading ?
              <Skeleton.Table rows={5} columns={6} /> :
              loadError ?
              renderEmptyState({
                icon: AlertCircle,
                title: 'Записи врача не загружены',
                description: loadError,
                tone: 'error',
                action: <Button variant="ghost" onClick={loadData}>Повторить</Button>
              }) :
              filteredAppointments.length === 0 ?
              renderEmptyState({
                icon: Calendar,
                title: 'Записи не найдены',
                description: searchQuery || filterStatus !== 'all'
                  ? 'По текущему поиску или фильтру нет записей.'
                  : 'Нет реальных записей для отображения. Создайте визит через регистратуру, очередь или кнопку назначения следующего визита.'
              }) :

              <table style={tableStyle}>
                    <thead>
                      <tr>
                        <th style={thStyle}>Время</th>
                        <th style={thStyle}>Пациент</th>
                        <th style={thStyle}>Тип</th>
                        <th style={thStyle}>Статус</th>
                        <th style={thStyle}>Примечания</th>
                        <th style={thStyle}>Действия</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredAppointments.map((appointment) =>
                  <tr
                    key={appointment.id}
                    style={{
                      cursor: 'pointer',
                      transition: 'background-color 0.2s ease'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = getColor('primary', 50);
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'transparent';
                    }}>

                          <td style={tdStyle}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('sm') }}>
                              <Clock size={16} style={{ color: getColor('secondary', 400) }} />
                              {appointment.time}
                            </div>
                          </td>
                          <td style={tdStyle}>{appointment.patientName || 'Пациент'}</td>
                          <td style={tdStyle}>{appointment.type || '—'}</td>
                          <td style={tdStyle}>
                            <Badge variant={getStatusVariant(appointment.status)} size="md">
                              {getStatusText(appointment.status)}
                            </Badge>
                          </td>
                          <td style={tdStyle}>{appointment.notes || '—'}</td>
                          <td style={tdStyle}>
                            <button
                        aria-label={`Edit ${getAppointmentA11yContext(appointment)}`}
                        style={{ ...actionButtonStyle, background: getColor('primary', 100), color: primaryColor }}
                        onClick={(e) => {
                          e.stopPropagation();
                          logger.log('Edit appointment', appointment.id);
                        }}>

                              <Edit size={16} />
                            </button>
                            <button
                        aria-label={`Complete ${getAppointmentA11yContext(appointment)}`}
                        style={{ ...actionButtonStyle, background: getColor('success', 100), color: successColor }}
                        onClick={(e) => {
                          e.stopPropagation();
                          logger.log('Complete appointment', appointment.id);
                        }}>

                              <CheckCircle size={16} />
                            </button>
                            <button
                        aria-label={`Cancel ${getAppointmentA11yContext(appointment)}`}
                        style={{ ...actionButtonStyle, background: getColor('danger', 100), color: dangerColor }}
                        onClick={(e) => {
                          e.stopPropagation();
                          logger.log('Cancel appointment', appointment.id);
                        }}>

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

        {/* ✅ НОВОЕ: Контент таба очереди */}
        {activeTab === 'queue' &&
        <AnimatedTransition type="fade" delay={100}>
            <Card style={patientsTableStyle}>
              <CardHeader style={tableHeaderStyle}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: getSpacing('md') }}>
                  <div>
                    <h2 style={{
                    fontSize: getFontSize('xl'),
                    fontWeight: '700',
                    color: getColor('secondary', 800),
                    margin: 0
                  }}>
                      Очередь пациентов
                    </h2>
                    <div style={{ display: 'flex', gap: getSpacing('md'), marginTop: getSpacing('sm') }}>
                      <Badge variant="warning">Ожидают: {queueStats.waiting}</Badge>
                      <Badge variant="primary">Вызваны: {queueStats.called}</Badge>
                      <Badge variant="success">Обслужены: {queueStats.served}</Badge>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: getSpacing('sm') }}>
                    <Button
                    variant="primary"
                    aria-label="Call next queue patient"
                    onClick={async () => {
                      try {
                        await callNext();
                        logger.log('Вызван следующий пациент');
                      } catch (err) {
                        logger.error('Ошибка вызова:', err);
                      }
                    }}
                    disabled={!canCallNext}>

                      <Phone size={16} />
                      {!isMobile && <span style={{ marginLeft: '4px' }}>Вызвать следующего</span>}
                    </Button>
                    <Button
                    variant="ghost"
                    onClick={loadQueue}
                    aria-label="Refresh doctor queue">

                      <RotateCcw size={16} />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent style={{ padding: 0 }}>
                {queueLoading ?
              <div style={{ padding: getSpacing('xl'), textAlign: 'center' }}>
                    <Skeleton height={40} count={5} />
                  </div> :
              queueError ?
              <div style={{ padding: getSpacing('xl'), textAlign: 'center', color: dangerColor }}>
                    <AlertCircle size={32} style={{ marginBottom: getSpacing('sm') }} />
                    <p>{queueError}</p>
                    <Button variant="ghost" onClick={loadQueue}>Повторить</Button>
                  </div> :
              queueEntries.length === 0 ?
              <div style={{ padding: getSpacing('xl'), textAlign: 'center', color: getColor('secondary', 500) }}>
                    <Users size={48} style={{ opacity: 0.5, marginBottom: getSpacing('md') }} />
                    <p>Очередь пуста</p>
                  </div> :

              <table style={tableStyle}>
                    <thead>
                      <tr>
                        <th style={thStyle}>№</th>
                        <th style={thStyle}>Пациент</th>
                        <th style={thStyle}>Телефон</th>
                        <th style={thStyle}>Услуги</th>
                        <th style={thStyle}>Статус</th>
                        <th style={thStyle}>Действия</th>
                      </tr>
                    </thead>
                    <tbody>
                      {queueEntries.map((entry, index) => {
                    const currentVisitMeta = getCurrentVisitMeta(entry);

                    return (
                  <tr
                    key={entry.id}
                    style={{
                      background: currentVisitMeta ? 'color-mix(in srgb, var(--mac-accent), transparent 92%)' : entry.priority > 0 ? `${warningColor}10` : 'transparent',
                      borderLeft: currentVisitMeta ? `3px solid ${primaryColor}` : entry.priority > 0 ? `3px solid ${warningColor}` : 'none'
                    }}
                    aria-label={currentVisitMeta ? `Current patient ${getQueuePatientContext(entry)}` : undefined}>

                          <td style={tdStyle}>
                            <Badge variant={entry.priority > 0 ? 'warning' : 'default'}>
                              {entry.number || index + 1}
                            </Badge>
                          </td>
                          <td style={tdStyle} aria-label={getQueuePatientContext(entry)}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('xs') }}>
                              <strong>{entry.patient_name}</strong>
                              <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing('xs'), flexWrap: 'wrap' }}>
                                {currentVisitMeta &&
                                <Badge
                                  variant={currentVisitMeta.variant}
                                  role="status"
                                  aria-label={`Current patient context: ${currentVisitMeta.label} for ${getQueuePatientContext(entry)}`}>
                                  {currentVisitMeta.label}
                                </Badge>
                                }
                                {entry.priority > 0 &&
                                <span style={{ fontSize: '10px', color: warningColor }}>
                                  ⚡ Следующий
                                </span>
                                }
                              </div>
                            </div>
                          </td>
                          <td style={tdStyle}>{entry.phone || '—'}</td>
                          <td style={tdStyle}>
                            {entry.service_details?.length > 0 ?
                      entry.service_details.slice(0, 2).map((svc, i) =>
                      <Badge key={i} variant="default" style={{ marginRight: '4px', fontSize: '10px' }}>
                                  {svc.name || svc.code}
                                </Badge>
                      ) :
                      entry.services?.length > 0 ?
                      <span style={{ fontSize: '12px', color: getColor('secondary', 500) }}>
                                {entry.services.slice(0, 2).join(', ')}
                              </span> :
                      '—'}
                          </td>
                          <td style={tdStyle}>
                            <Badge variant={getStatusVariant(entry.status)}>
                              {getStatusText(entry.status)}
                            </Badge>
                            {/* ✅ Таймер для активных статусов */}
                            {(entry.status === 'called' || entry.status === 'diagnostics') && entry.called_at &&
                      <span style={{
                        marginLeft: '8px',
                        fontSize: '11px',
                        color: getColor('secondary', 500),
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '2px'
                      }}>
                                <Clock size={12} />
                                {formatElapsedTime(entry.called_at)}
                              </span>
                      }
                          </td>
                          <td style={tdStyle}>
                            {/* Backend-owned queue action contract */}
                            {hasBackendQueueAction(entry, 'no_show', 'can_no_show') &&
                            !hasBackendQueueAction(entry, 'send_to_diagnostics', 'can_send_to_diagnostics') &&
                      <>
                                <button
                          {...getQueueActionA11yProps('Mark no-show', entry)}
                          aria-label={`Mark no-show for ${getQueuePatientContext(entry)}`}
                          style={{ ...actionButtonStyle, background: getColor('danger', 100), color: dangerColor }}
                          onClick={() => markNoShow(entry.id)}
                          title="Отметить неявку">

                                  <XCircle size={16} />
                                </button>
                              </>
                      }
                            {hasBackendQueueAction(entry, 'send_to_diagnostics', 'can_send_to_diagnostics') &&
                      <>
                                <button
                          {...getQueueActionA11yProps('Send to diagnostics', entry)}
                          aria-label={`Send to diagnostics for ${getQueuePatientContext(entry)}`}
                          style={{ ...actionButtonStyle, background: getColor('info', 100), color: accentColor }}
                          onClick={() => sendToDiagnostics(entry.id)}
                          title="На обследование">

                                  <Stethoscope size={16} />
                                </button>
                                <button
                          {...getQueueActionA11yProps('Complete visit', entry)}
                          aria-label={`Complete visit for ${getQueuePatientContext(entry)}`}
                          style={{ ...actionButtonStyle, background: getColor('success', 100), color: successColor }}
                          onClick={() => completeVisit(entry.id)}
                          title="Завершить приём">

                                  <CheckCircle size={16} />
                                </button>
                                <button
                          {...getQueueActionA11yProps('Mark no-show', entry)}
                          aria-label={`Mark no-show for ${getQueuePatientContext(entry)}`}
                          style={{ ...actionButtonStyle, background: getColor('danger', 100), color: dangerColor }}
                          onClick={() => markNoShow(entry.id)}
                          title="Не явился">

                                  <XCircle size={16} />
                                </button>
                              </>
                      }
                            {hasBackendQueueAction(entry, 'notify_diagnostics_return', 'can_notify_diagnostics_return') &&
                      <>
                                <button
                          {...getQueueActionA11yProps('Call back from diagnostics', entry)}
                          aria-label={`Call back from diagnostics for ${getQueuePatientContext(entry)}`}
                          style={{ ...actionButtonStyle, background: getColor('primary', 100), color: primaryColor }}
                          onClick={() => callFromDiagnostics(entry.id)}
                          title="Вернуть с диагностики (Push)">

                                  <Bell size={16} />
                                </button>
                                <button
                          {...getQueueActionA11yProps('Complete visit', entry)}
                          aria-label={`Complete visit for ${getQueuePatientContext(entry)}`}
                          style={{ ...actionButtonStyle, background: getColor('success', 100), color: successColor }}
                          onClick={() => completeVisit(entry.id)}
                          title="Завершить приём">

                                  <CheckCircle size={16} />
                                </button>
                                <button
                          {...getQueueActionA11yProps('Mark visit incomplete', entry)}
                          aria-label={`Mark visit incomplete for ${getQueuePatientContext(entry)}`}
                          style={{ ...actionButtonStyle, background: getColor('warning', 100), color: warningColor }}
                          onClick={() => markIncomplete(entry.id, 'Не вернулся с обследования')}
                          title="Не вернулся">

                                  <AlertCircle size={16} />
                                </button>
                              </>
                      }
                            {hasBackendQueueAction(entry, 'restore_next', 'can_restore_next') &&
                      <button
                        {...getQueueActionA11yProps('Restore as next patient', entry)}
                        aria-label={`Restore as next patient for ${getQueuePatientContext(entry)}`}
                        style={{ ...actionButtonStyle, background: getColor('warning', 100), color: warningColor }}
                        onClick={() => restoreToNext(entry.id)}
                        title="Восстановить следующим">

                                <RotateCcw size={16} />
                              </button>
                      }
                          </td>
                        </tr>
                    );
                  })}
                    </tbody>
                  </table>
              }
              </CardContent>
            </Card>
          </AnimatedTransition>
        }

        {activeTab === 'ai' &&
        <AnimatedTransition type="fade" delay={100}>
            <Card>
              <CardHeader>
                <h2 style={{
                fontSize: getFontSize('xl'),
                fontWeight: '700',
                color: getColor('secondary', 800),
                margin: 0
              }}>
                  AI Помощник врача
                </h2>
              </CardHeader>
              <CardContent>
                <AIAssistant
                specialty="general"
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
                <h2 style={{
                fontSize: getFontSize('xl'),
                fontWeight: '700',
                color: getColor('secondary', 800),
                margin: 0
              }}>
                  Отчеты и аналитика
                </h2>
              </CardHeader>
              <CardContent>
                <div style={{
                display: 'grid',
                gridTemplateColumns: isMobile ? '1fr' : isTablet ? 'repeat(2, 1fr)' : 'repeat(3, 1fr)',
                gap: getSpacing('lg')
              }}>
                  <Button variant="primary" fullWidth>
                    <FileText size={20} />
                    Отчет по пациентам
                  </Button>
                  <Button variant="secondary" fullWidth>
                    <Calendar size={20} />
                    Отчет по записям
                  </Button>
                  <Button variant="success" fullWidth>
                    <Activity size={20} />
                    Статистика работы
                  </Button>
                  <Button variant="warning" fullWidth>
                    <Pill size={20} />
                    Отчет по лекарствам
                  </Button>
                  <Button variant="info" fullWidth>
                    <Heart size={20} />
                    Медицинская статистика
                  </Button>
                  <Button variant="ghost" fullWidth>
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
      {patientModal.isOpen && patientModal.selectedItem &&
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'color-mix(in srgb, var(--mac-bg-primary), black 42%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999
      }}>
          <div style={{
          backgroundColor: 'var(--mac-card-bg)',
          border: '1px solid var(--mac-card-border)',
          borderRadius: '12px',
          padding: '24px',
          width: '100%',
          maxWidth: '500px',
          margin: '16px',
          boxShadow: 'var(--mac-shadow-xl)'
        }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <h3 style={{ fontSize: '20px', fontWeight: '600', color: 'var(--mac-text-primary)', margin: 0 }}>
                Информация о пациенте
              </h3>
              <button
              aria-label="Close patient information dialog"
              onClick={patientModal.closeModal}
              style={{
                color: 'var(--mac-text-tertiary)',
                cursor: 'pointer',
                border: 'none',
                background: 'none',
                padding: '4px',
                borderRadius: '4px'
              }}>

                <XCircle size={24} />
              </button>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
                <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                backgroundColor: 'var(--mac-accent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--mac-text-on-accent)',
                fontSize: '18px',
                fontWeight: '600'
              }}>
                  {patientModal.selectedItem.name?.charAt(0) || 'П'}
                </div>
                <div>
                  <h4 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--mac-text-primary)', margin: 0 }}>
                    {patientModal.selectedItem.name || 'Неизвестно'}
                  </h4>
                  <p style={{ fontSize: '14px', color: 'var(--mac-text-secondary)', margin: 0 }}>
                    {patientModal.selectedItem.phone || 'Телефон не указан'}
                  </p>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <p style={{ fontSize: '12px', color: 'var(--mac-text-secondary)', margin: '0 0 4px 0', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Возраст
                  </p>
                  <p style={{ fontSize: '16px', color: 'var(--mac-text-primary)', margin: 0, fontWeight: '500' }}>
                    {patientModal.selectedItem.age || 'Не указан'}
                  </p>
                </div>
                <div>
                  <p style={{ fontSize: '12px', color: 'var(--mac-text-secondary)', margin: '0 0 4px 0', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Статус
                  </p>
                  <p style={{ fontSize: '16px', color: 'var(--mac-text-primary)', margin: 0, fontWeight: '500' }}>
                    {patientModal.selectedItem.status === 'active' ? 'Активный' :
                  patientModal.selectedItem.status === 'waiting' ? 'Ожидает' :
                  patientModal.selectedItem.status || 'Неизвестно'}
                  </p>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
              <button
              onClick={patientModal.closeModal}
              style={{
                padding: '8px 16px',
                border: '1px solid var(--mac-border)',
                borderRadius: '6px',
                backgroundColor: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '500'
              }}>

                Закрыть
              </button>
              <button
              style={{
                padding: '8px 16px',
                border: 'none',
                borderRadius: '6px',
                backgroundColor: 'var(--mac-accent)',
                color: 'var(--mac-text-on-accent)',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '500'
              }}>

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
        specialty="general"
        useWebSocket={false}
        position="bottom-right" />

      <RoleNotificationCenter userRole="doctor" />
    </div>);

};

export default DoctorPanel;
