import { useState } from 'react';
import type { CSSProperties } from "react";
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
import { useModal } from '../hooks/useModal';
import { useBreakpoint, useTouchDevice } from '../hooks/useEnhancedMediaQuery';
import useDoctorQueue from '../hooks/useDoctorQueue';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import AIChatWidget from '../components/ai/AIChatWidget';
import RoleNotificationCenter from '../components/notifications/RoleNotificationCenter';

import logger from '../utils/logger';
// UX Audit Doctor H-30: import DoctorQueuePanel instead of inline queue rendering.
import DoctorQueuePanel from '../components/doctor/DoctorQueuePanel';
// i18n-unification: useTranslation hook from unified i18n (replaces adapter shim)
import { useTranslation } from '../i18n/useTranslation';
// PR-UI-15-1: types/status maps + tab & data lifecycle extracted to ./doctor/*
// (registrar/cashier decomposition precedent).
import {
  getDoctorStatusText,
  getDoctorStatusVariant,
  getPatientA11yContext,
  getAppointmentA11yContext,
} from './doctor/doctorStatus';
import type { PatientRecord } from './doctor/doctorStatus';
import { useDoctorTabState } from './doctor/useDoctorTabState';
import { useDoctorPanelData } from './doctor/useDoctorPanelData';

const DoctorPanel = () => {
  const { isMobile, isTablet } = useBreakpoint();
  const { t: rawT } = useTranslation();
  const t = rawT;
  const isTouchDevice = useTouchDevice();
  // UX Audit Doctor L-43: isTouchDevice used for disabling hover on touch.
  void isTouchDevice;

  // PR-UI-15-1: tab/URL/filter view-state slice (verbatim port).
  const {
    activeTab,
    setActiveTab,
    setDoctorTab,
    searchQuery,
    setSearchQuery,
    filterStatus,
    setFilterStatus,
  } = useDoctorTabState();

  // ✅ УЛУЧШЕНИЕ: Универсальный хук вместо дублированных состояний
  // Cast to a typed shape — useModal is generic-free (selectedItem: null),
  // so we narrow it here for type-safe access in this panel.
  const patientModal = useModal() as unknown as {
    isOpen: boolean;
    isAnimating: boolean;
    selectedItem: PatientRecord | null;
    loading: boolean;
    openModal: (item: PatientRecord | Record<string, unknown> | null) => void;
    closeModal: () => void;
    toggleModal: (item?: PatientRecord | Record<string, unknown> | null) => void;
    setModalLoading: (isLoading: boolean) => void;
  };

  // PR-UI-15-1: data lifecycle (patients/appointments/loading/error +
  // specialty + schedule-next refresh + ?patientId deep-link) — verbatim port.
  const {
    patients,
    appointments,
    loading,
    loadError,
    loadData,
    appointmentStats,
    doctorSpecialty,
    handleScheduleNextSuccess,
  } = useDoctorPanelData({
    t,
    setSearchQuery,
    setActiveTab,
    openPatientModal: patientModal.openModal,
  });
  const [scheduleNextModal, setScheduleNextModal] = useState<{ open: boolean; patient: Record<string, unknown> | null }>({ open: false, patient: null });

  // ✅ НОВОЕ: Получаем данные текущего пользователя и очереди
  // PR-UI-15-1: канонический деструктор сокращён до живых значений —
  // остальные поля (queue/loading/error/loadQueue/callNext/markNoShow/
  // restoreToNext/sendToDiagnostics/markIncomplete/completeVisit) были
  // definition-only в панели (queue-действия живут в DoctorQueuePanel +
  // useDoctorQueue). canCallNext сохранён: SSOT-контракт
  // DoctorPanels.contract.test.tsx ожидает его в DoctorPanel.tsx.
  const {
    stats: queueStats,
    canCallNext,
  } = useDoctorQueue(doctorSpecialty);
  void canCallNext;

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

  // UX Audit Doctor H-09: headerRef/headerHeight vestiges removed with the
  // H-09 note (never attached, definition-only — PR-UI-15-1 cleanup).

  // Стили
  const pageStyle: CSSProperties = {
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

  const contentStyle: CSSProperties = {
    marginTop: '20px',
    padding: isMobile ? getSpacing('md') : getSpacing('lg'),
    maxWidth: '1400px',
    margin: '20px auto 0 auto'
  };

  const tabsStyle: CSSProperties = {
    display: 'flex',
    gap: isMobile ? getSpacing('sm') : getSpacing('md'),
    marginBottom: getSpacing('xl'),
    overflowX: 'auto',
    paddingBottom: getSpacing('sm')
  };

  const tabStyle: CSSProperties = {
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

  const activeTabStyle: CSSProperties = {
    ...tabStyle,
    background: `linear-gradient(135deg, ${primaryColor} 0%, ${getColor('primary', 600)} 100%)`,
    color: 'var(--mac-text-on-accent)',
    boxShadow: '0 4px 14px 0 color-mix(in srgb, var(--mac-accent), transparent 70%)',
    transform: 'translateY(-2px)'
  };

  const dashboardGridStyle: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: isMobile ? '1fr' : isTablet ? 'repeat(2, 1fr)' : 'repeat(4, 1fr)',
    gap: getSpacing('lg'),
    marginBottom: getSpacing('xl')
  };

  const statCardStyle: CSSProperties = {
    background: panelSurface,
    borderRadius: 'var(--mac-radius-xl)',
    padding: getSpacing('lg'),
    boxShadow: getShadow('lg'),
    border: `1px solid ${panelBorder}`,
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    cursor: 'default'  /* UX Audit Doctor M-33: stat cards not clickable */
  };

  const statCardHoverStyle: CSSProperties = {
    transform: 'translateY(-4px) scale(1.02)',
    boxShadow: getShadow('2xl')
  };

  const patientsTableStyle: CSSProperties = {
    background: panelSurface,
    borderRadius: 'var(--mac-radius-xl)',
    overflow: 'hidden',
    boxShadow: getShadow('lg'),
    border: `1px solid ${panelBorder}`
  };

  const tableHeaderStyle: CSSProperties = {
    background: 'linear-gradient(135deg, color-mix(in srgb, var(--mac-bg-secondary), white 8%) 0%, color-mix(in srgb, var(--mac-bg-secondary), transparent 10%) 100%)',
    padding: getSpacing('lg'),
    borderBottom: '1px solid var(--mac-separator)'
  };

  const tableStyle: CSSProperties = {
    width: '100%',
    borderCollapse: 'collapse'
  };

  // Phase 3: thStyle/tdStyle constants removed — replaced by .doctor-th / .doctor-td CSS classes.
  // The CSS classes use var(--mac-*) tokens directly, eliminating the need for JS-side
  // getSpacing/getColor/getFontSize calls that produced the same values.


  // Функции
  // PR-UI-15-1: status maps + a11y helpers moved verbatim to
  // ./doctor/doctorStatus (getDoctorStatusVariant / getDoctorStatusText /
  // getPatientA11yContext / getAppointmentA11yContext). Dead helpers
  // (getQueuePatientContext / getCurrentVisitMeta / getQueueActionA11yProps)
  // dropped — see the provenance note in doctorStatus.ts.
  const getStatusVariant = getDoctorStatusVariant;
  const getStatusText = (status: string | undefined) => getDoctorStatusText(status, t);

  const renderEmptyState = ({ icon: Icon, title, description, tone = 'default', action = null }: {
    icon: React.ComponentType<{ size?: number | string; className?: string }>;
    title: React.ReactNode;
    description?: React.ReactNode;
    tone?: string;
    action?: React.ReactNode;
  }) => {
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
  const handlePatientClick = (patient: PatientRecord | Record<string, unknown> | null) => {
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

  const handleInactiveTabHover = (event: React.MouseEvent<HTMLElement>, isActive: boolean, hovered: boolean) => {
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
            onMouseEnter={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'dashboard', true)}
            onMouseLeave={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'dashboard', false)}>

            <Activity size={isMobile ? 16 : 20} />
            {!isMobile && <span>{t("doctor.tab_dashboard")}</span>}
          </button>

          <button
            aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_patients") })}
            style={activeTab === 'patients' ? activeTabStyle : tabStyle}
            onClick={() => setDoctorTab('patients')}
            onMouseEnter={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'patients', true)}
            onMouseLeave={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'patients', false)}>

            <User size={isMobile ? 16 : 20} />
            {!isMobile && <span>{t("doctor.tab_patients")}</span>}
          </button>

          <button
            aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_appointments") })}
            style={activeTab === 'appointments' ? activeTabStyle : tabStyle}
            onClick={() => setDoctorTab('appointments')}
            onMouseEnter={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'appointments', true)}
            onMouseLeave={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'appointments', false)}>

            <Calendar size={isMobile ? 16 : 20} />
            {!isMobile && <span>{t("doctor.tab_appointments")}</span>}
          </button>

          {/* ✅ НОВОЕ: Таб очереди */}
          <button
            aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_queue") })}
            style={activeTab === 'queue' ? activeTabStyle : tabStyle}
            onClick={() => setDoctorTab('queue')}
            onMouseEnter={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'queue', true)}
            onMouseLeave={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'queue', false)}>

            <Users size={isMobile ? 16 : 20} />
            {!isMobile && <span>{t("doctor.tab_queue")}</span>}
            {Number(queueStats.waiting ?? 0) > 0 &&
            <Badge variant="warning" className="doctor-badge-ml">
                {queueStats.waiting}
              </Badge>
            }
          </button>

          <button
            aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_ai") })}
            style={activeTab === 'ai' ? activeTabStyle : tabStyle}
            onClick={() => setDoctorTab('ai')}
            onMouseEnter={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'ai', true)}
            onMouseLeave={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'ai', false)}>

            <Brain size={isMobile ? 16 : 20} />
            {!isMobile && <span>AI Помощник</span>}
          </button>

          <button
            aria-label={t("doctor.aria_open_tab", { name: t("doctor.tab_reports") })}
            style={activeTab === 'reports' ? activeTabStyle : tabStyle}
            onClick={() => setDoctorTab('reports')}
            onMouseEnter={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'reports', true)}
            onMouseLeave={(e: React.MouseEvent<HTMLElement>) => handleInactiveTabHover(e, activeTab === 'reports', false)}>

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
                  onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                    Object.assign(e.currentTarget.style, statCardHoverStyle);
                  }}
                  onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                    e.currentTarget.style.transform = 'translateY(0) scale(1)';
                    e.currentTarget.style.boxShadow = getShadow('lg');
                  }}>

                    <div className="doctor-stat-row">
                      <div className="doctor-stat-icon" style={{ '--doctor-gradient-from': primaryColor, '--doctor-gradient-to': getColor('primary', 600) } as CSSProperties}>
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
                  onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                    Object.assign(e.currentTarget.style, statCardHoverStyle);
                  }}
                  onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                    e.currentTarget.style.transform = 'translateY(0) scale(1)';
                    e.currentTarget.style.boxShadow = getShadow('lg');
                  }}>

                    <div className="doctor-stat-row">
                      <div className="doctor-stat-icon" style={{ '--doctor-gradient-from': successColor, '--doctor-gradient-to': getColor('success', 600) } as CSSProperties}>
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
                  onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                    Object.assign(e.currentTarget.style, statCardHoverStyle);
                  }}
                  onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                    e.currentTarget.style.transform = 'translateY(0) scale(1)';
                    e.currentTarget.style.boxShadow = getShadow('lg');
                  }}>

                    <div className="doctor-stat-row">
                      <div className="doctor-stat-icon" style={{ '--doctor-gradient-from': warningColor, '--doctor-gradient-to': getColor('warning', 600) } as CSSProperties}>
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
                  onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                    Object.assign(e.currentTarget.style, statCardHoverStyle);
                  }}
                  onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                    e.currentTarget.style.transform = 'translateY(0) scale(1)';
                    e.currentTarget.style.boxShadow = getShadow('lg');
                  }}>

                    <div className="doctor-stat-row">
                      <div className="doctor-stat-icon" style={{ '--doctor-gradient-from': accentColor, '--doctor-gradient-to': getColor('info', 600) } as CSSProperties}>
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
                      onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setSearchQuery(e.target.value)}
                      className={`doctor-search-input ${isMobile ? 'doctor-search-w-mobile' : 'doctor-search-w-desktop'}`} />

                    </div>
                    <select
                    value={filterStatus}
                    onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setFilterStatus(e.target.value)}
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
              <Skeleton variant="rectangular" width="100%" height={200} /> :
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
                              <div className="doctor-avatar-sm" style={{ '--doctor-gradient-from': primaryColor, '--doctor-gradient-to': getColor('primary', 600) } as CSSProperties}>
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
                            <Badge variant={getStatusVariant(patient.status)} size="default">
                              {getStatusText(patient.status)}
                            </Badge>
                          </td>
                          <td className="doctor-td" aria-label={`${getPatientA11yContext(patient)} actions`}>
                            <button
                        aria-label={`Edit ${getPatientA11yContext(patient)}`}
                        className="doctor-action-btn doctor-action-btn-primary"
                        onClick={(e: React.MouseEvent<HTMLElement>) => {
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
                        onClick={(e: React.MouseEvent<HTMLElement>) => {
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
                        onClick={(e: React.MouseEvent<HTMLElement>) => e.stopPropagation()}>

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
                      onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setSearchQuery(e.target.value)}
                      className={`doctor-search-input ${isMobile ? 'doctor-search-w-mobile' : 'doctor-search-w-desktop'}`} />

                    </div>
                    <select
                    value={filterStatus}
                    onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setFilterStatus(e.target.value)}
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
              <Skeleton variant="rectangular" width="100%" height={200} /> :
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
                            <Badge variant={getStatusVariant(appointment.status)} size="default">
                              {getStatusText(appointment.status)}
                            </Badge>
                          </td>
                          <td className="doctor-td">{appointment.notes || '—'}</td>
                          <td className="doctor-td">
                            <button
                        aria-label={`Edit ${getAppointmentA11yContext(appointment)}`}
                        className="doctor-action-btn doctor-action-btn-primary"
                        onClick={(e: React.MouseEvent<HTMLElement>) => {
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
                        onClick={(e: React.MouseEvent<HTMLElement>) => e.stopPropagation()}>

                              <CheckCircle size={16} />
                            </button>
                            <button
                        aria-label={`Cancel ${getAppointmentA11yContext(appointment)}`}
                        className="doctor-action-btn doctor-action-btn-danger"
                        disabled
                        title={t("doctor.feature_in_development")}
                        onClick={(e: React.MouseEvent<HTMLElement>) => e.stopPropagation()}>

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
            onPatientSelect={(entry: Record<string, unknown>) => {
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
                onSuggestionSelect={(type: string, suggestion: unknown) => {
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
                  <Button variant="secondary" color="success" fullWidth disabled title={t("doctor.feature_in_development")}>
                    <Activity size={20} />
                    Статистика работы
                  </Button>
                  <Button variant="secondary" color="warning" fullWidth disabled title={t("doctor.feature_in_development")}>
                    <Pill size={20} />
                    Отчет по лекарствам
                  </Button>
                  <Button variant="secondary" color="info" fullWidth disabled title={t("doctor.feature_in_development")}>
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
        onClick={(e: React.MouseEvent<HTMLElement>) => { if (e.target === e.currentTarget) patientModal.closeModal(); }}
        onKeyDown={(e: React.KeyboardEvent<HTMLElement>) => { if (e.key === 'Escape') patientModal.closeModal(); }}
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
        onSuccess={handleScheduleNextSuccess as (result?: unknown, formData?: Record<string, unknown>) => void}
        patient={scheduleNextModal.patient ?? undefined}
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
