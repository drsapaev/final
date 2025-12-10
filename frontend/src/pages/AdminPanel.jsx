// AdminPanel.jsx - macOS UI/UX Compliant - Updated: 2025-01-26
import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { 
  Badge, 
  Progress,
  Icon,
  Sidebar,
  MacOSTab,
  MacOSStatCard,
  MacOSMetricCard,
  MacOSTable,
  MacOSInput,
  MacOSSelect,
  MacOSTextarea,
  MacOSCheckbox,
  MacOSRadio,
  MacOSBreadcrumb,
  MacOSPagination,
  MacOSList,
  MacOSEmptyState,
  MacOSLoadingSkeleton,
  MacOSAlert,
  MacOSModal,
  MacOSButton,
  MacOSBadge,
  Card as MacOSCard
} from '../components/ui/macos';
import { useBreakpoint, useTouchDevice } from '../hooks/useEnhancedMediaQuery';
import { useTheme } from '../contexts/ThemeContext';
import { 
  BarChart3, 
  TrendingUp, 
  Clock, 
  Brain, 
  Globe, 
  FileText, 
  Server, 
  Printer, 
  Stethoscope, 
  Package, 
  Receipt, 
  Percent, 
  Database, 
  Users, 
  UserPlus, 
  Calendar, 
  AlertTriangle, 
  Settings, 
  Monitor, 
  CreditCard, 
  Building2, 
  Shield, 
  Heart, 
  Pill, 
  Mic, 
  ClipboardCheck, 
  Bot, 
  Bell, 
  Phone, 
  Download, 
  MessageSquare, 
  Key, 
  CheckCircle, 
  Activity,
  Eye,
  Plus,
  Search,
  RefreshCw,
  Edit,
  Trash2,
  Filter,
  DollarSign,
  AlertCircle,
  X,
  Upload,
  TrendingDown,
  XCircle,
  Palette,
  FolderTree
} from 'lucide-react';

// ✅ УЛУЧШЕНИЕ: Универсальные хуки для устранения дублирования
import { useModal } from '../hooks/useModal.jsx';
import useAsyncAction from '../hooks/useAsyncAction';

// ✅ УЛУЧШЕНИЕ: Унифицированные компоненты (будут использованы в следующих итерациях)
// import UnifiedLayout from '../components/layout/UnifiedLayout';
// import { MedicalCard, MetricCard, MedicalTable } from '../components/medical';
// import AdminSection from '../components/admin/AdminSection';
import KPICard from '../components/admin/KPICard';
import AdminNavigation from '../components/admin/AdminNavigation';
import ErrorBoundary from '../components/admin/ErrorBoundary';
import EmptyState from '../components/admin/EmptyState';
import useAdminData from '../hooks/useAdminData';
import useUsers from '../hooks/useUsers';
import useDoctors from '../hooks/useDoctors';
import usePatients from '../hooks/usePatients';
import useAppointments from '../hooks/useAppointments';
import useFinance from '../hooks/useFinance';
import useReports from '../hooks/useReports';
import useSettings from '../hooks/useSettings';
import useSecurity from '../hooks/useSecurity';
import UserModal from '../components/admin/UserModal';
import DoctorModal from '../components/admin/DoctorModal';
import PatientModal from '../components/admin/PatientModal';
import AppointmentModal from '../components/admin/AppointmentModal';
import FinanceModal from '../components/admin/FinanceModal';
import ReportGenerator from '../components/admin/ReportGenerator';
import AnalyticsDashboard from '../components/admin/AnalyticsDashboard';
import ClinicSettings from '../components/admin/ClinicSettings';
import QueueSettings from '../components/admin/QueueSettings';
import ServiceCatalog from '../components/admin/ServiceCatalog';
import DepartmentManagement from '../components/admin/DepartmentManagement';
import AISettings from '../components/admin/AISettings';
import DisplayBoardSettings from '../components/admin/DisplayBoardSettings';
import ActivationSystem from '../components/admin/ActivationSystem';
import SecuritySettings from '../components/admin/SecuritySettings';
import SecurityMonitor from '../components/admin/SecurityMonitor';
import ColorSchemeSelector from '../components/admin/ColorSchemeSelector';
import AllFreeApproval from '../components/admin/AllFreeApproval';
import BenefitSettings from '../components/admin/BenefitSettings';
import WizardSettings from '../components/admin/WizardSettings';
import PaymentProviderSettings from '../components/admin/PaymentProviderSettings';
import QueueLimitsManager from '../components/admin/QueueLimitsManager';
import MedicalImageAnalyzer from '../components/ai/MedicalImageAnalyzer';
import TreatmentRecommendations from '../components/ai/TreatmentRecommendations';
import DrugInteractionChecker from '../components/ai/DrugInteractionChecker';
import RiskAssessment from '../components/ai/RiskAssessment';
import VoiceToText from '../components/ai/VoiceToText';
import SmartScheduling from '../components/ai/SmartScheduling';
import QualityControl from '../components/ai/QualityControl';
import AnalyticsInsights from '../components/ai/AnalyticsInsights';
import UnifiedTelegramManagement from '../components/admin/UnifiedTelegramManagement';
import UnifiedSettings from '../components/admin/UnifiedSettings';
import UnifiedFinance from '../components/admin/UnifiedFinance';
import UnifiedNotifications from '../components/admin/UnifiedNotifications';
import UnifiedAITools from '../components/admin/UnifiedAITools';
import UnifiedUserManagement from '../components/admin/UnifiedUserManagement';
import FCMManager from '../components/admin/FCMManager';
import PhoneVerificationManager from '../components/admin/PhoneVerificationManager';
import UserDataTransferManager from '../components/admin/UserDataTransferManager';
import GroupPermissionsManager from '../components/admin/GroupPermissionsManager';
import UserExportManager from '../components/admin/UserExportManager';
import RegistrarNotificationManager from '../components/admin/RegistrarNotificationManager';
import ClinicManagement from '../components/admin/ClinicManagement';
import BranchManagement from '../components/admin/BranchManagement';
import EquipmentManagement from '../components/admin/EquipmentManagement';
import LicenseManagement from '../components/admin/LicenseManagement';
import BackupManagement from '../components/admin/BackupManagement';
import WaitTimeAnalytics from '../components/analytics/WaitTimeAnalytics';
import AIAnalytics from '../components/analytics/AIAnalytics'; 
import GraphQLExplorer from '../components/admin/GraphQLExplorer'; 
import WebhookManager from '../components/admin/WebhookManager';
import UnifiedReports from '../components/admin/UnifiedReports';
import SystemManagement from '../components/admin/SystemManagement';
import CloudPrintingManager from '../components/admin/CloudPrintingManager';
import MedicalEquipmentManager from '../components/admin/MedicalEquipmentManager';
import DynamicPricingManager from '../components/admin/DynamicPricingManager';
import BillingManager from '../components/admin/BillingManager';
import DiscountBenefitsManager from '../components/admin/DiscountBenefitsManager';
import { useAdminHotkeys } from '../hooks/useHotkeys';
import { HotkeysModal } from '../components/admin/HelpTooltip';
import { MobileNavigation, useScreenSize } from '../components/admin/MobileOptimization';
import logger from '../utils/logger';
import '../styles/admin-styles.css';

const AdminPanel = () => {
  const location = useLocation();
  const navigate = useNavigate();
  
  // Состояние для UX улучшений
  const [showHotkeysModal, setShowHotkeysModal] = useState(false);
  
  // Обработчики горячих клавиш
  const hotkeyHandlers = {
    save: () => {
      // Логика сохранения для текущего раздела
    },
    search: () => {
      // Фокус на поле поиска
      const searchInput = document.querySelector('input[placeholder*="поиск" i], input[placeholder*="search" i]');
      if (searchInput) {
        searchInput.focus();
      }
    },
    refresh: async () => {
      try {
        await refreshStats();
      } catch (error) {
        logger.error('Ошибка обновления:', error);
      }
    },
    dashboard: () => navigate('/admin'),
    users: () => navigate('/admin/users'),
    doctors: () => navigate('/admin/doctors'),
    services: () => navigate('/admin/services'),
    settings: () => navigate('/admin/settings'),
    shortcuts: () => setShowHotkeysModal(true),
    closeModal: () => setShowHotkeysModal(false),
    help: () => setShowHotkeysModal(true)
  };
  
  // Активируем горячие клавиши
  useAdminHotkeys(hotkeyHandlers);
  
  // Используем новый хук для загрузки данных
  const { 
    data: statsData, 
    loading: statsLoading, 
    error: statsError, 
    refresh: refreshStats 
  } = useAdminData('/admin/stats', {
    refreshInterval: 0, // Автообновление отключено, можно включить при необходимости
    enabled: true, // Включена загрузка реальных данных
    onError: (error) => {
      logger.error('Ошибка загрузки статистики:', error);
    }
  });

  // Статистика по умолчанию (fallback только при ошибке)
  const defaultStats = {
    totalUsers: 0,
    totalDoctors: 0,
    totalPatients: 0,
    totalRevenue: 0,
    appointmentsToday: 0,
    pendingApprovals: 0
  };
  
  const stats = statsData || defaultStats;
  const isLoading = statsLoading;
  
  // Хук для управления пользователями
  const {
    users,
    loading: usersLoading,
    error: usersError,
    searchTerm,
    setSearchTerm,
    filterRole,
    setFilterRole,
    filterStatus,
    setFilterStatus,
    pagination,
    changePage,
    createUser,
    updateUser,
    deleteUser
  } = useUsers();
  
  // ✅ УЛУЧШЕНИЕ: Универсальное управление модальным окном пользователей
  const userModal = useModal();
  
  // Хук для управления врачами
  const {
    doctors,
    loading: doctorsLoading,
    error: doctorsError,
    searchTerm: doctorsSearchTerm,
    setSearchTerm: setDoctorsSearchTerm,
    filterSpecialization,
    setFilterSpecialization,
    filterDepartment,
    setFilterDepartment,
    filterStatus: doctorsFilterStatus,
    setFilterStatus: setDoctorsFilterStatus,
    createDoctor,
    updateDoctor,
    deleteDoctor
  } = useDoctors();
  
  // ✅ УЛУЧШЕНИЕ: Универсальное управление модальным окном врачей
  const doctorModal = useModal();
  
  // Хук для управления пациентами
  const {
    patients,
    loading: patientsLoading,
    error: patientsError,
    searchTerm: patientsSearchTerm,
    setSearchTerm: setPatientsSearchTerm,
    filterGender,
    setFilterGender,
    filterAgeRange,
    setFilterAgeRange,
    filterBloodType,
    setFilterBloodType,
    createPatient,
    updatePatient,
    deletePatient,
    calculateAge
  } = usePatients();
  
  // ✅ УЛУЧШЕНИЕ: Универсальное управление модальным окном пациентов
  const patientModal = useModal();
  
  // Хук для управления записями
  const {
    appointments,
    loading: appointmentsLoading,
    error: appointmentsError,
    searchTerm: appointmentsSearchTerm,
    setSearchTerm: setAppointmentsSearchTerm,
    filterStatus: appointmentFilterStatus,
    setFilterStatus: setAppointmentFilterStatus,
    filterDate: appointmentFilterDate,
    setFilterDate: setAppointmentFilterDate,
    filterDoctor: appointmentFilterDoctor,
    setFilterDoctor: setAppointmentFilterDoctor,
    createAppointment,
    updateAppointment,
    deleteAppointment,
    getStatusStats,
    getTodayAppointments,
    getTomorrowAppointments
  } = useAppointments();
  
  // ✅ УЛУЧШЕНИЕ: Универсальное управление модальным окном записей
  const appointmentModal = useModal();
  
  // Хук для управления финансами
  const {
    transactions,
    loading: financeLoading,
    error: financeError,
    searchTerm: financeSearchTerm,
    setSearchTerm: setFinanceSearchTerm,
    filterType,
    setFilterType,
    filterCategory,
    setFilterCategory,
    filterDateRange,
    setFilterDateRange,
    filterStatus: financeFilterStatus,
    setFilterStatus: setFinanceFilterStatus,
    createTransaction,
    updateTransaction,
    deleteTransaction,
    getFinancialStats,
    getCategoryStats,
    getDailyStats
  } = useFinance();
  
  // ✅ УЛУЧШЕНИЕ: Универсальное управление модальным окном финансов
  const financeModal = useModal();

  // ✅ УЛУЧШЕНИЕ: Универсальный хук для async действий
  const asyncAction = useAsyncAction();
  
  // Хук для управления отчетами
  const {
    reports,
    loading: reportsLoading,
    error: reportsError,
    searchTerm: reportsSearchTerm,
    setSearchTerm: setReportsSearchTerm,
    filterType: reportFilterType,
    setFilterType: setReportFilterType,
    filterStatus: reportFilterStatus,
    setFilterStatus: setReportFilterStatus,
    filterDateRange: reportFilterDateRange,
    setFilterDateRange: setReportFilterDateRange,
    generateReport,
    downloadReport,
    deleteReport,
    regenerateReport,
    getReportStats,
    getReportTypes,
    getStatusLabel,
    getStatusVariant,
    formatDateRange
  } = useReports();
  
  
  // Хук для управления настройками
  const {
    settings,
    loading: settingsLoading,
    error: settingsError,
    activeTab: settingsActiveTab,
    setActiveTab: setSettingsActiveTab,
    saveSettings,
    resetSettings,
    exportSettings,
    importSettings,
    getSettingsStats,
    validateSettings
  } = useSettings();
  
  // Состояние для настроек
  const [settingsSubTab, setSettingsSubTab] = useState(() => {
    // Восстанавливаем вкладку из URL или localStorage
    const params = new URLSearchParams(location.search);
    const tabFromUrl = params.get('settingsTab');
    if (tabFromUrl) {
      return tabFromUrl;
    }
    return localStorage.getItem('settingsSubTab') || 'general';
  });

  // Сохраняем выбранную вкладку
  useEffect(() => {
    localStorage.setItem('settingsSubTab', settingsSubTab);
  }, [settingsSubTab]);

  // Состояние для вкладок секции Services
  const [servicesTab, setServicesTab] = useState(() => {
    const params = new URLSearchParams(location.search);
    const tabFromUrl = params.get('servicesTab');
    if (tabFromUrl) {
      return tabFromUrl;
    }
    return localStorage.getItem('servicesTab') || 'catalog';
  });

  // Сохраняем выбранную вкладку services
  useEffect(() => {
    localStorage.setItem('servicesTab', servicesTab);
  }, [servicesTab]);
  
  // Состояние для логотипа
  const [logoFile, setLogoFile] = useState(null);
  const [logoPreview, setLogoPreview] = useState(null);
  
  // Настройки по умолчанию
  const defaultSettings = {
    clinicName: '',
    clinicAddress: '',
    clinicPhone: '',
    clinicEmail: '',
    timezone: 'Europe/Moscow',
    language: 'ru',
    currency: 'RUB',
    logoUrl: ''
  };
  
  // Функции для работы с логотипом
  const handleLogoSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      // Проверяем тип файла
      if (!file.type.startsWith('image/')) {
        alert('Выберите файл изображения');
        return;
      }

      // Проверяем размер (макс 5MB)
      if (file.size > 5 * 1024 * 1024) {
        alert('Размер файла не должен превышать 5MB');
        return;
      }

      setLogoFile(file);
      
      // Создаем превью
      const reader = new FileReader();
      reader.onload = (e) => {
        setLogoPreview(e.target.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const resetLogo = () => {
    setLogoFile(null);
    setLogoPreview(null);
  };
  
  // Хук для управления безопасностью
  const {
    securityData,
    loading: securityLoading,
    error: securityError,
    searchTerm: securitySearchTerm,
    setSearchTerm: setSecuritySearchTerm,
    filterStatus: securityFilterStatus,
    setFilterStatus: setSecurityFilterStatus,
    filterSeverity: securityFilterSeverity,
    setFilterSeverity: setSecurityFilterSeverity,
    filterDateRange: securityFilterDateRange,
    setFilterDateRange: setSecurityFilterDateRange,
    filteredThreats,
    filteredLogs,
    loadSecurityData,
    blockIP,
    unblockIP,
    terminateSession,
    terminateAllOtherSessions,
    updateThreatStatus,
    exportSecurityLogs,
    getSecurityStats,
    getSecurityTrends
  } = useSecurity();
  
  // Загрузка последних действий с бэкенда
  const { 
    data: recentActivitiesData, 
    loading: recentActivitiesLoading, 
    error: recentActivitiesError 
  } = useAdminData('/admin/recent-activities?limit=10', {
    refreshInterval: 0,
    enabled: true,
    initialData: { activities: [] }
  });

  const recentActivities = recentActivitiesData?.activities || [];

  // Загрузка системных уведомлений с бэкенда
  const { 
    data: systemAlertsData, 
    loading: systemAlertsLoading, 
    error: systemAlertsError 
  } = useAdminData('/notifications/history/stats?days=7', {
    refreshInterval: 0,
    enabled: true,
    initialData: { recent_activity: [] }
  });

  // Функция для форматирования времени "сколько времени назад"
  const formatTimeAgo = React.useCallback((date) => {
    if (!date) return 'Недавно';
    // Если date - строка, преобразуем в Date
    const dateObj = typeof date === 'string' ? new Date(date) : date;
    if (isNaN(dateObj.getTime())) return 'Недавно';
    
    const now = new Date();
    const diff = now - dateObj;
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (seconds < 60) return 'только что';
    if (minutes < 60) return `${minutes} ${minutes === 1 ? 'минуту' : minutes < 5 ? 'минуты' : 'минут'} назад`;
    if (hours < 24) return `${hours} ${hours === 1 ? 'час' : hours < 5 ? 'часа' : 'часов'} назад`;
    if (days < 7) return `${days} ${days === 1 ? 'день' : days < 5 ? 'дня' : 'дней'} назад`;
    return dateObj.toLocaleDateString('ru-RU');
  }, []);

  // Преобразуем данные уведомлений в формат для отображения
  const systemAlerts = React.useMemo(() => {
    if (!systemAlertsData?.recent_activity) return [];
    
    return systemAlertsData.recent_activity.slice(0, 5).map((alert, index) => ({
      id: alert.id || index + 1,
      type: alert.status === 'failed' ? 'error' : alert.status === 'pending' ? 'warning' : 'info',
      message: alert.message || alert.notification_type || 'Системное уведомление',
      priority: alert.status === 'failed' ? 'high' : alert.status === 'pending' ? 'medium' : 'low',
      time: alert.created_at ? formatTimeAgo(new Date(alert.created_at)) : 'Недавно'
    }));
  }, [systemAlertsData, formatTimeAgo]);

  // Загрузка данных для графика активности
  const { 
    data: activityChartData, 
    loading: activityChartLoading, 
    error: activityChartError 
  } = useAdminData('/admin/activity-chart?days=7', {
    refreshInterval: 0,
    enabled: true,
    initialData: { labels: [], data: [] }
  });
  
  const { 
    designTokens,
    isDark 
  } = useTheme();

  // Вспомогательные функции для работы с токенами
  const getSpacing = (size) => {
    return designTokens.spacing[size] || '16px';
  };

  const getFontSize = (size) => {
    return designTokens.typography.fontSize[size] || '16px';
  };
  
  // Анимации (используются в компонентах)
  const [animationsStarted, setAnimationsStarted] = useState(false);

  useEffect(() => {
    // Запуск анимаций при загрузке компонента
    if (!animationsStarted) {
      const timer = setTimeout(() => {
        setAnimationsStarted(true);
      }, 100);
      
      return () => clearTimeout(timer);
    }
  }, [animationsStarted]);

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'UZS',
      minimumFractionDigits: 0
    }).format(amount);
  };

  // ✅ УЛУЧШЕНИЕ: Обработчики для отчетов с универсальным async хуком

  // Обработчики для настроек
  const handleSaveSettings = async (settingsData) => {
    try {
      await saveSettings(settingsData);
    } catch (error) {
      logger.error('Ошибка сохранения настроек:', error);
      throw error;
    }
  };

  const handleResetSettings = async () => {
    if (window.confirm('Вы уверены, что хотите сбросить все настройки к значениям по умолчанию?')) {
      try {
        await resetSettings();
      } catch (error) {
        logger.error('Ошибка сброса настроек:', error);
        alert('Ошибка при сбросе настроек');
      }
    }
  };

  const handleExportSettings = async () => {
    try {
      await exportSettings();
    } catch (error) {
      logger.error('Ошибка экспорта настроек:', error);
      alert('Ошибка при экспорте настроек');
    }
  };

  const handleImportSettings = async (file) => {
    try {
      await importSettings(file);
    } catch (error) {
      logger.error('Ошибка импорта настроек:', error);
      alert('Ошибка при импорте настроек');
    }
  };

  // Обработчики для безопасности
  const handleBlockIP = async (ip, reason) => {
    try {
      await blockIP(ip, reason);
    } catch (error) {
      logger.error('Ошибка блокировки IP:', error);
      alert('Ошибка при блокировке IP адреса');
    }
  };

  const handleUnblockIP = async (ipId) => {
    try {
      await unblockIP(ipId);
    } catch (error) {
      logger.error('Ошибка разблокировки IP:', error);
      alert('Ошибка при разблокировке IP адреса');
    }
  };

  const handleTerminateSession = async (sessionId) => {
    try {
      await terminateSession(sessionId);
    } catch (error) {
      logger.error('Ошибка завершения сессии:', error);
      alert('Ошибка при завершении сессии');
    }
  };

  const handleTerminateAllOtherSessions = async () => {
    if (window.confirm('Вы уверены, что хотите завершить все остальные сессии?')) {
      try {
        await terminateAllOtherSessions();
      } catch (error) {
        logger.error('Ошибка завершения сессий:', error);
        alert('Ошибка при завершении сессий');
      }
    }
  };

  const handleUpdateThreatStatus = async (threatId, newStatus) => {
    try {
      await updateThreatStatus(threatId, newStatus);
    } catch (error) {
      logger.error('Ошибка обновления статуса угрозы:', error);
      alert('Ошибка при обновлении статуса угрозы');
    }
  };

  const handleExportSecurityLogs = async (format = 'json') => {
    try {
      await exportSecurityLogs(format);
    } catch (error) {
      logger.error('Ошибка экспорта логов:', error);
      alert('Ошибка при экспорте логов безопасности');
    }
  };

  const getReportTypeLabel = (type) => {
    const typeLabels = {
      'financial': 'Финансовый',
      'medical': 'Медицинский', 
      'operational': 'Операционный',
      'analytics': 'Аналитический',
      'security': 'Безопасность',
      'audit': 'Аудит'
    };
    return typeLabels[type] || type;
  };

  const getStatusIcon = (status) => {
    const colorMap = {
      success: 'var(--mac-success)',
      warning: 'var(--mac-warning)',
      error: 'var(--mac-error)',
      info: 'var(--mac-info)',
      default: 'var(--mac-text-tertiary)'
    };
    if (status === 'success') return <CheckCircle style={{ width: '16px', height: '16px', color: colorMap.success }} />;
    if (status === 'warning') return <AlertTriangle style={{ width: '16px', height: '16px', color: colorMap.warning }} />;
    if (status === 'error') return <AlertTriangle style={{ width: '16px', height: '16px', color: colorMap.error }} />;
    if (status === 'info') return <Clock style={{ width: '16px', height: '16px', color: colorMap.info }} />;
    return <Clock style={{ width: '16px', height: '16px', color: colorMap.default }} />;
  };

  // ✅ УЛУЧШЕНИЕ: Обработчики для пользователей с универсальным хуком
  const handleCreateUser = () => {
    userModal.openModal(null);
  };

  const handleEditUser = (user) => {
    userModal.openModal(user);
  };

  const handleDeleteUser = async (user) => {
    if (window.confirm(`Вы уверены, что хотите удалить пользователя "${user.name}"?`)) {
      try {
        await deleteUser(user.id);
      } catch (error) {
        logger.error('Ошибка удаления пользователя:', error);
        alert('Ошибка при удалении пользователя');
      }
    }
  };

  const handleSaveUser = async (userData) => {
    userModal.setModalLoading(true);
    try {
      if (userModal.selectedItem) {
        await updateUser(userModal.selectedItem.id, userData);
      } else {
        await createUser(userData);
      }
      userModal.closeModal();
    } catch (error) {
      logger.error('Ошибка сохранения пользователя:', error);
      throw error;
    } finally {
      userModal.setModalLoading(false);
    }
  };

  const handleCloseUserModal = () => {
    userModal.closeModal();
  };

  const getRoleLabel = (role) => {
    const roleMap = {
      Admin: 'Администратор',
      Doctor: 'Врач',
      Registrar: 'Регистратор',
      Cashier: 'Кассир',
      Lab: 'Лаборатория',
      Patient: 'Пациент',
      cardio: 'Кардиолог',
      derma: 'Дерматолог',
      dentist: 'Стоматолог'
    };
    return roleMap[role] || role;
  };

  const getUserStatusLabel = (status) => {
    return status ? 'Активен' : 'Неактивен';
  };


  const getStatusColor = (isActive) => {
    return isActive ? 'var(--mac-success)' : 'var(--mac-warning)';
  };

  // ✅ УЛУЧШЕНИЕ: Обработчики для врачей с универсальным хуком
  const handleCreateDoctor = () => {
    doctorModal.openModal(null);
  };

  const handleEditDoctor = (doctor) => {
    doctorModal.openModal(doctor);
  };

  const handleDeleteDoctor = async (doctor) => {
    const doctorName = doctor.user?.full_name || doctor.name || doctor.user?.username || 'этого врача';
    if (window.confirm(`Вы уверены, что хотите удалить врача "${doctorName}"?`)) {
      try {
        await deleteDoctor(doctor.id);
      } catch (error) {
        logger.error('Ошибка удаления врача:', error);
        alert('Ошибка при удалении врача');
      }
    }
  };

  const handleSaveDoctor = async (doctorData) => {
    doctorModal.setModalLoading(true);
    try {
      if (doctorModal.selectedItem) {
        await updateDoctor(doctorModal.selectedItem.id, doctorData);
      } else {
        await createDoctor(doctorData);
      }
      doctorModal.closeModal();
    } catch (error) {
      logger.error('Ошибка сохранения врача:', error);
      throw error;
    } finally {
      doctorModal.setModalLoading(false);
    }
  };

  const handleCloseDoctorModal = () => {
    doctorModal.closeModal();
  };

  const getDepartmentLabel = (department) => {
    const departmentMap = {
      cardiology: 'Кардиология',
      dermatology: 'Дерматология',
      dentistry: 'Стоматология',
      stomatology: 'Стоматология',
      laboratory: 'Лаборатория',
      cosmetology: 'Косметология',
      procedures: 'Процедуры',
      physiotherapy: 'Физиотерапия',
      functional_diagnostics: 'Функциональная диагностика',
      general: 'Общее'
    };
    return departmentMap[department] || department;
  };

  const getDoctorStatusLabel = (status) => {
    const statusMap = {
      active: 'Активен',
      inactive: 'Неактивен',
      on_leave: 'В отпуске'
    };
    return statusMap[status] || status;
  };

  const getDoctorStatusColor = (status) => {
    const colorMap = {
      active: 'var(--mac-success)',
      inactive: 'var(--mac-warning)',
      on_leave: 'var(--mac-info)'
    };
    return colorMap[status] || 'var(--mac-text-tertiary)';
  };

  // ✅ УЛУЧШЕНИЕ: Обработчики для пациентов с универсальным хуком
  const handleCreatePatient = () => {
    patientModal.openModal(null);
  };

  const handleEditPatient = (patient) => {
    patientModal.openModal(patient);
  };

  const handleDeletePatient = async (patient) => {
    if (window.confirm(`Вы уверены, что хотите удалить пациента "${patient.firstName} ${patient.lastName}"?`)) {
      try {
        await deletePatient(patient.id);
      } catch (error) {
        logger.error('Ошибка удаления пациента:', error);
        alert('Ошибка при удалении пациента');
      }
    }
  };

  const handleSavePatient = async (patientData) => {
    patientModal.setModalLoading(true);
    try {
      if (patientModal.selectedItem) {
        await updatePatient(patientModal.selectedItem.id, patientData);
      } else {
        await createPatient(patientData);
      }
      patientModal.closeModal();
    } catch (error) {
      logger.error('Ошибка сохранения пациента:', error);
      throw error;
    } finally {
      patientModal.setModalLoading(false);
    }
  };

  const handleClosePatientModal = () => {
    patientModal.closeModal();
  };

  const getGenderLabel = (gender) => {
    const genderMap = {
      male: 'Мужской',
      female: 'Женский'
    };
    return genderMap[gender] || gender;
  };

  const getAgeRangeLabel = (ageRange) => {
    const ageRangeMap = {
      '0-18': '0-18 лет',
      '19-35': '19-35 лет',
      '36-50': '36-50 лет',
      '51-65': '51-65 лет',
      '65+': '65+ лет'
    };
    return ageRangeMap[ageRange] || ageRange;
  };

  // Обработчики для записей
  // ✅ УЛУЧШЕНИЕ: Обработчики для записей с универсальным хуком
  const handleCreateAppointment = () => {
    appointmentModal.openModal(null);
  };

  const handleEditAppointment = (appointment) => {
    appointmentModal.openModal(appointment);
  };

  const handleDeleteAppointment = async (appointment) => {
    if (window.confirm(`Вы уверены, что хотите удалить запись "${appointment.patientName} - ${appointment.doctorName}"?`)) {
      try {
        await deleteAppointment(appointment.id);
      } catch (error) {
        logger.error('Ошибка удаления записи:', error);
        alert('Ошибка при удалении записи');
      }
    }
  };

  const handleSaveAppointment = async (appointmentData) => {
    appointmentModal.setModalLoading(true);
    try {
      if (appointmentModal.selectedItem) {
        await updateAppointment(appointmentModal.selectedItem.id, appointmentData);
      } else {
        await createAppointment(appointmentData);
      }
      appointmentModal.closeModal();
    } catch (error) {
      logger.error('Ошибка сохранения записи:', error);
      throw error;
    } finally {
      appointmentModal.setModalLoading(false);
    }
  };

  const handleCloseAppointmentModal = () => {
    appointmentModal.closeModal();
  };

  const getAppointmentStatusLabel = (status) => {
    const statusMap = {
      pending: 'Ожидает оплаты',
      scheduled: 'Запланирована', // Старый статус -> маппится на pending
      confirmed: 'Подтверждена', // Старый статус -> маппится на paid
      paid: 'Оплачена',
      in_visit: 'На приеме',
      completed: 'Завершена',
      cancelled: 'Отменена',
      no_show: 'Не явился'
    };
    return statusMap[status] || status;
  };

  const getAppointmentStatusColor = (status) => {
    const colorMap = {
      pending: 'var(--mac-warning)',
      scheduled: 'var(--mac-warning)', // Старый статус -> маппится на pending
      confirmed: 'var(--mac-info)', // Старый статус -> маппится на paid
      paid: 'var(--mac-success)',
      in_visit: 'var(--mac-accent-blue)',
      completed: 'var(--mac-success)',
      cancelled: 'var(--mac-danger)',
      no_show: 'var(--mac-text-tertiary)'
    };
    return colorMap[status] || 'var(--mac-text-tertiary)';
  };

  const getAppointmentStatusVariant = (status) => {
    const variantMap = {
      pending: 'warning',
      scheduled: 'warning', // Старый статус -> маппится на pending
      confirmed: 'info', // Старый статус -> маппится на paid
      paid: 'success',
      in_visit: 'primary',
      completed: 'success',
      cancelled: 'error',
      no_show: 'secondary'
    };
    return variantMap[status] || 'secondary';
  };

  // ✅ УЛУЧШЕНИЕ: Обработчики для финансов с универсальным хуком
  const handleCreateTransaction = () => {
    financeModal.openModal(null);
  };

  const handleEditTransaction = (transaction) => {
    financeModal.openModal(transaction);
  };

  const handleDeleteTransaction = async (transaction) => {
    if (window.confirm(`Вы уверены, что хотите удалить транзакцию "${transaction.description}"?`)) {
      try {
        await deleteTransaction(transaction.id);
      } catch (error) {
        logger.error('Ошибка удаления транзакции:', error);
        alert('Ошибка при удалении транзакции');
      }
    }
  };

  const handleSaveTransaction = async (transactionData) => {
    financeModal.setModalLoading(true);
    try {
      if (financeModal.selectedItem) {
        await updateTransaction(financeModal.selectedItem.id, transactionData);
      } else {
        await createTransaction(transactionData);
      }
      financeModal.closeModal();
    } catch (error) {
      logger.error('Ошибка сохранения транзакции:', error);
      throw error;
    } finally {
      financeModal.setModalLoading(false);
    }
  };

  const handleCloseFinanceModal = () => {
    financeModal.closeModal();
  };

  const getTransactionTypeLabel = (type) => {
    const typeMap = {
      income: 'Доход',
      expense: 'Расход'
    };
    return typeMap[type] || type;
  };

  const getTransactionStatusLabel = (status) => {
    const statusMap = {
      pending: 'Ожидает',
      completed: 'Завершена',
      cancelled: 'Отменена',
      refunded: 'Возврат'
    };
    return statusMap[status] || status;
  };

  const getTransactionStatusVariant = (status) => {
    const variantMap = {
      pending: 'warning',
      completed: 'success',
      cancelled: 'error',
      refunded: 'info'
    };
    return variantMap[status] || 'secondary';
  };

  const getPaymentMethodLabel = (method) => {
    const methodMap = {
      cash: 'Наличные',
      card: 'Карта',
      transfer: 'Перевод',
      mobile: 'Мобильный'
    };
    return methodMap[method] || method;
  };

  // Новая структура навигации
  const navigationSections = [
    {
      title: 'Обзор',
      items: [
        { to: '/admin', label: 'Дашборд', icon: BarChart3 },
        { to: '/admin/analytics', label: 'Аналитика', icon: TrendingUp },
        { to: '/admin/webhooks', label: 'Webhook\'и', icon: Globe },
        { to: '/admin/reports', label: 'Отчеты', icon: FileText },
        { to: '/admin/system', label: 'Система', icon: Server },
        { to: '/admin/cloud-printing', label: 'Облачная печать', icon: Printer },
        { to: '/admin/medical-equipment', label: 'Медицинское оборудование', icon: Stethoscope },
        { to: '/admin/graphql-explorer', label: 'GraphQL API', icon: Database }
      ]
    },
    {
      title: 'Управление',
      items: [
        { to: '/admin/users', label: 'Пользователи', icon: Users },
        { to: '/admin/doctors', label: 'Врачи', icon: UserPlus },
        { to: '/admin/services', label: 'Услуги', icon: Package },
        { to: '/admin/departments', label: 'Отделения', icon: FolderTree },
        { to: '/admin/patients', label: 'Пациенты', icon: Users },
        { to: '/admin/appointments', label: 'Записи', icon: Calendar },
        { to: '/admin/all-free', label: 'Заявки All Free', icon: AlertTriangle }
      ]
    },
    {
      title: 'Система',
      items: [
        { to: '/admin/clinic-management', label: 'Управление клиникой', icon: Building2 },
        { to: '/admin/ai-imaging', label: 'AI Инструменты', icon: Brain },
        { to: '/admin/telegram-bot', label: 'Telegram', icon: Bot },
        { to: '/admin/fcm-notifications', label: 'Уведомления', icon: Bell },
        { to: '/admin/phone-verification', label: 'Верификация телефонов', icon: Phone },
        { to: '/admin/activation', label: 'Система активации', icon: Key },
        { to: '/admin/finance', label: 'Финансы', icon: CreditCard },
        { to: '/admin/settings', label: 'Настройки', icon: Settings }
      ]
    }
  ];

  // Получаем все табы для совместимости
  const tabs = navigationSections.flatMap(section => 
    section.items.map(item => ({
      id: item.to === '/admin' ? 'dashboard' : item.to.split('/')[2],
      label: item.label,
      icon: item.icon
    }))
  );

  // Вычисляем текущую вкладку из URL параметров или пути
  const searchParams = new URLSearchParams(location.search);
  const sectionFromQuery = searchParams.get('section');
  
  // Если секция указана в query параметре, используем её
  // Иначе пытаемся извлечь из пути URL
  let current = sectionFromQuery;
  if (!current) {
    const pathParts = location.pathname.split('/').filter(Boolean);
    if (pathParts.length >= 2 && pathParts[0] === 'admin') {
      current = pathParts[1] || 'dashboard';
    } else {
      current = 'dashboard';
    }
  }

  const renderDashboard = () => (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Красивые KPI карточки */}
        {statsLoading ? (
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
            gap: '24px' 
          }}>
            <MacOSLoadingSkeleton type="card" count={6} />
          </div>
        ) : statsError ? (
          <MacOSEmptyState
            icon={AlertCircle}
            title="Ошибка загрузки статистики"
            description="Не удалось загрузить данные. Проверьте подключение к серверу."
            action={
              <MacOSButton onClick={refreshStats} variant="primary">
                <RefreshCw size={16} />
                Повторить попытку
              </MacOSButton>
            }
          />
        ) : (
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
            gap: '24px' 
          }}>
            <MacOSStatCard
              title="Всего пользователей"
              value={stats.totalUsers || 0}
              icon={Users}
              color="blue"
              loading={statsLoading}
            />
        
            <MacOSStatCard
              title="Врачи"
              value={stats.totalDoctors || 0}
              icon={Stethoscope}
              color="green"
              loading={statsLoading}
            />
        
            <MacOSStatCard
              title="Пациенты"
              value={stats.totalPatients || 0}
              icon={Users}
              color="purple"
              loading={statsLoading}
            />
            
            <MacOSStatCard
              title="Доход"
              value={formatCurrency(stats.totalRevenue || 0)}
              icon={TrendingUp}
              color="green"
              loading={statsLoading}
            />
            
            <MacOSStatCard
              title="Записи сегодня"
              value={stats.appointmentsToday || 0}
              icon={Calendar}
              color="orange"
              loading={statsLoading}
            />
            
            <MacOSStatCard
              title="Ожидают подтверждения"
              value={stats.pendingApprovals || 0}
              icon={Clock}
              color="red"
              loading={statsLoading}
            />
          </div>
        )}

        {/* Графики и аналитика */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
          gap: '24px' 
        }}>
           <MacOSCard style={{ padding: '24px' }}>
            <div style={{ padding: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 style={{ 
                fontSize: 'var(--mac-font-size-lg)', 
                fontWeight: 'var(--mac-font-weight-semibold)', 
                color: 'var(--mac-text-primary)',
                margin: 0
              }}>Активность системы</h3>
              <MacOSButton variant="outline" size="sm">
                <Download style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                Экспорт
              </MacOSButton>
            </div>
            {activityChartLoading ? (
              <div style={{ 
                height: '256px', 
                borderRadius: 'var(--mac-radius-md)', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                background: 'var(--mac-bg-secondary)' 
              }}>
                <MacOSLoadingSkeleton type="text" count={3} />
              </div>
            ) : activityChartError ? (
              <div style={{ 
                height: '256px', 
                borderRadius: 'var(--mac-radius-md)', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                background: 'var(--mac-bg-secondary)' 
              }}>
                <MacOSEmptyState
                  icon={AlertTriangle}
                  title="Ошибка загрузки графика"
                  description="Не удалось загрузить данные активности"
                />
              </div>
            ) : activityChartData?.data && activityChartData.data.length > 0 ? (
              <div style={{ 
                height: '256px', 
                borderRadius: 'var(--mac-radius-md)', 
                padding: '16px',
                background: 'var(--mac-bg-secondary)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between'
              }}>
                {/* Простой график в виде столбцов */}
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'flex-end', 
                  justifyContent: 'space-around',
                  height: '200px',
                  gap: '4px'
                }}>
                  {activityChartData.data.map((item, index) => {
                    const maxValue = Math.max(...activityChartData.data.map(d => d.total || 0));
                    const height = maxValue > 0 ? (item.total / maxValue) * 180 : 0;
                    return (
                      <div key={index} style={{ 
                        flex: 1, 
                        display: 'flex', 
                        flexDirection: 'column', 
                        alignItems: 'center',
                        gap: '4px'
                      }}>
                        <div style={{
                          width: '100%',
                          height: `${height}px`,
                          background: 'linear-gradient(to top, var(--mac-primary), var(--mac-primary-light))',
                          borderRadius: '4px 4px 0 0',
                          minHeight: '4px',
                          transition: 'height 0.3s ease'
                        }} />
                        <span style={{ 
                          fontSize: '10px', 
                          color: 'var(--mac-text-tertiary)',
                          textAlign: 'center'
                        }}>
                          {activityChartData.labels[index]}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-around', 
                  marginTop: '8px',
                  fontSize: '12px',
                  color: 'var(--mac-text-secondary)'
                }}>
                  <span>Записи: {activityChartData.data.reduce((sum, d) => sum + (d.appointments || 0), 0)}</span>
                  <span>Платежи: {activityChartData.data.reduce((sum, d) => sum + (d.payments || 0), 0)}</span>
                  <span>Пользователи: {activityChartData.data.reduce((sum, d) => sum + (d.users || 0), 0)}</span>
                </div>
              </div>
            ) : (
              <div style={{ 
                height: '256px', 
                borderRadius: 'var(--mac-radius-md)', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                background: 'var(--mac-bg-secondary)' 
              }}>
                <div style={{ textAlign: 'center' }}>
                  <Activity style={{ 
                    width: '48px', 
                    height: '48px', 
                    margin: '0 auto 16px auto', 
                    color: 'var(--mac-text-tertiary)' 
                  }} />
                  <p style={{ color: 'var(--mac-text-secondary)' }}>Нет данных за выбранный период</p>
                </div>
              </div>
            )}
          </MacOSCard>

          <MacOSCard 
            style={{ padding: 0 }}
          >
            <div style={{ padding: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 style={{ 
                fontSize: 'var(--mac-font-size-lg)', 
                fontWeight: 'var(--mac-font-weight-semibold)', 
                color: 'var(--mac-text-primary)',
                margin: 0
              }}>Последние действия</h3>
              <MacOSButton variant="outline" size="sm">
                <Eye style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                Все
              </MacOSButton>
            </div>
            {recentActivitiesLoading ? (
              <div style={{ padding: '16px' }}>
                <MacOSLoadingSkeleton type="text" count={4} />
              </div>
            ) : recentActivitiesError ? (
              <div style={{ padding: '16px' }}>
                <MacOSEmptyState
                  icon={AlertTriangle}
                  title="Ошибка загрузки"
                  description="Не удалось загрузить последние действия"
                />
              </div>
            ) : recentActivities.length === 0 ? (
              <div style={{ padding: '16px', textAlign: 'center' }}>
                <p style={{ color: 'var(--mac-text-secondary)' }}>Нет последних действий</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {recentActivities.map((activity) => (
                  <div key={activity.id} style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '12px', 
                    padding: '12px', 
                    borderRadius: 'var(--mac-radius-md)',
                    background: 'var(--mac-bg-secondary)' 
                  }}>
                    {getStatusIcon(activity.status)}
                    <div style={{ flex: '1' }}>
                      <p style={{ 
                        fontSize: 'var(--mac-font-size-sm)', 
                        fontWeight: 'var(--mac-font-weight-medium)', 
                        color: 'var(--mac-text-primary)',
                        margin: 0
                      }}>{activity.message}</p>
                      <p style={{ 
                        fontSize: 'var(--mac-font-size-xs)', 
                        color: 'var(--mac-text-secondary)',
                        margin: '4px 0 0 0'
                      }}>{activity.user} • {activity.time}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </MacOSCard>
        </div>

        {/* Системные уведомления */}
        <MacOSCard 
          style={{ padding: 0, marginTop: '24px' }}
        >
          <div style={{ padding: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>Системные уведомления</h3>
            <MacOSBadge variant="warning">{systemAlerts.length}</MacOSBadge>
          </div>
            {systemAlertsLoading ? (
              <div style={{ padding: '16px' }}>
                <MacOSLoadingSkeleton type="text" count={3} />
              </div>
            ) : systemAlertsError ? (
              <div style={{ padding: '16px' }}>
                <MacOSEmptyState
                  icon={AlertTriangle}
                  title="Ошибка загрузки"
                  description="Не удалось загрузить системные уведомления"
                />
              </div>
            ) : systemAlerts.length === 0 ? (
              <div style={{ padding: '16px', textAlign: 'center' }}>
                <p style={{ color: 'var(--mac-text-secondary)' }}>Нет системных уведомлений</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {systemAlerts.map((alert) => (
                  <div key={alert.id} style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '12px', 
                    padding: '12px', 
                    border: '1px solid var(--mac-border)', 
                    borderRadius: 'var(--mac-radius-md)' 
                  }}>
                    <AlertTriangle style={{ width: '20px', height: '20px', color: 'var(--mac-warning)' }} />
                    <div style={{ flex: '1' }}>
                      <p style={{ 
                        fontSize: 'var(--mac-font-size-sm)', 
                        fontWeight: 'var(--mac-font-weight-medium)', 
                        color: 'var(--mac-text-primary)',
                        margin: 0
                      }}>{alert.message}</p>
                      <p style={{ 
                        fontSize: '12px', 
                        color: 'var(--mac-text-secondary)',
                        margin: '4px 0 0 0'
                      }}>{alert.time}</p>
                    </div>
                    <MacOSBadge variant={alert.priority === 'high' ? 'error' : alert.priority === 'medium' ? 'warning' : 'info'}>
                      {alert.priority}
                    </MacOSBadge>
                  </div>
                ))}
              </div>
            )}
          </MacOSCard>
        </div>
    </ErrorBoundary>
  );

  const renderUsers = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard 
        variant="default"
        style={{ padding: '24px' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <h2 style={{ 
            fontSize: 'var(--mac-font-size-xl)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>Управление пользователями</h2>
          <MacOSButton onClick={handleCreateUser}>
            <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            Добавить пользователя
          </MacOSButton>
        </div>
        
        {/* Поиск и фильтры */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
          <div style={{ flex: '1' }}>
            <MacOSInput
              type="text"
              placeholder="Поиск пользователей..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              icon={Search}
              iconPosition="left"
              style={{
                width: '100%',
                paddingLeft: '40px',
                paddingRight: '16px',
                paddingTop: '8px',
                paddingBottom: '8px',
                borderRadius: 'var(--mac-radius-sm)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                outline: 'none',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
            />
          </div>
          <MacOSSelect
            value={filterRole}
            onChange={(e) => setFilterRole(e.target.value)}
            options={[
              { value: '', label: 'Все роли' },
              { value: 'Admin', label: 'Администратор' },
              { value: 'Doctor', label: 'Врач' },
              { value: 'Registrar', label: 'Регистратор' },
              { value: 'Cashier', label: 'Кассир' },
              { value: 'Lab', label: 'Лаборатория' },
              { value: 'Patient', label: 'Пациент' },
              { value: 'cardio', label: 'Кардиолог' },
              { value: 'derma', label: 'Дерматолог' },
              { value: 'dentist', label: 'Стоматолог' }
            ]}
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--mac-radius-sm)',
              border: '1px solid var(--mac-border)',
              background: 'var(--mac-bg-primary)',
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-sm)',
              outline: 'none'
            }}
          />
          <MacOSSelect
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            options={[
              { value: '', label: 'Все статусы' },
              { value: 'true', label: 'Активен' },
              { value: 'false', label: 'Неактивен' }
            ]}
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--mac-radius-sm)',
              border: '1px solid var(--mac-border)',
              background: 'var(--mac-bg-primary)',
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-sm)',
              outline: 'none'
            }}
          />
        </div>

        {/* Таблица пользователей */}
        <div style={{ overflowX: 'auto' }}>
          {usersLoading ? (
            <MacOSLoadingSkeleton type="table" count={5} />
          ) : usersError ? (
            <EmptyState
              type="error"
              title="Ошибка загрузки пользователей"
              description="Не удалось загрузить список пользователей"
              action={
                <MacOSButton onClick={() => window.location.reload()}>
                  <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                  Обновить
                </MacOSButton>
              }
            />
          ) : users.length === 0 ? (
            <EmptyState
              type="users"
              title="Пользователи не найдены"
              description={searchTerm || filterRole || filterStatus 
                ? 'Попробуйте изменить параметры поиска' 
                : 'В системе пока нет пользователей'
              }
              action={
                <MacOSButton onClick={handleCreateUser}>
                  <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                  Добавить первого пользователя
                </MacOSButton>
              }
            />
          ) : (
            <table style={{ 
              width: '100%', 
              borderCollapse: 'collapse',
              border: '1px solid var(--mac-border)'
            }} role="table" aria-label="Таблица пользователей">
              <thead>
                <tr style={{ 
                  backgroundColor: 'var(--mac-bg-tertiary)', 
                  borderBottom: '1px solid var(--mac-border)' 
                }}>
                  <th scope="col" style={{ 
                    textAlign: 'left', 
                    padding: '12px 16px', 
                    color: 'var(--mac-text-primary)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    fontSize: 'var(--mac-font-size-sm)',
                    borderRight: '1px solid var(--mac-border)',
                    borderBottom: '1px solid var(--mac-border)'
                  }}>Пользователь</th>
                  <th scope="col" style={{ 
                    textAlign: 'left', 
                    padding: '12px 16px', 
                    color: 'var(--mac-text-primary)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    fontSize: 'var(--mac-font-size-sm)',
                    borderRight: '1px solid var(--mac-border)',
                    borderBottom: '1px solid var(--mac-border)'
                  }}>Роль</th>
                  <th scope="col" style={{ 
                    textAlign: 'left', 
                    padding: '12px 16px', 
                    color: 'var(--mac-text-primary)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    fontSize: 'var(--mac-font-size-sm)',
                    borderRight: '1px solid var(--mac-border)',
                    borderBottom: '1px solid var(--mac-border)'
                  }}>Статус</th>
                  <th scope="col" style={{ 
                    textAlign: 'left', 
                    padding: '12px 16px', 
                    color: 'var(--mac-text-primary)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    fontSize: 'var(--mac-font-size-sm)',
                    borderRight: '1px solid var(--mac-border)',
                    borderBottom: '1px solid var(--mac-border)'
                  }}>Последний вход</th>
                  <th scope="col" style={{ 
                    textAlign: 'left', 
                    padding: '12px 16px', 
                    color: 'var(--mac-text-primary)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    fontSize: 'var(--mac-font-size-sm)',
                    borderBottom: '1px solid var(--mac-border)'
                  }}>Действия</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} style={{ 
                    borderBottom: '1px solid var(--mac-border)', 
                    transition: 'background-color var(--mac-duration-normal) var(--mac-ease)'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    <td style={{ 
                      padding: '12px 16px',
                      borderRight: '1px solid var(--mac-border)',
                      borderBottom: '1px solid var(--mac-border)'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <div style={{
                          width: '32px',
                          height: '32px',
                          borderRadius: '50%',
                          backgroundColor: 'var(--mac-accent)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'white',
                          fontSize: 'var(--mac-font-size-sm)',
                          fontWeight: '500'
                        }}>
                          <span>
                            {(user.profile?.full_name || user.full_name || user.username || 'U').split(' ').map(n => n[0]).join('').toUpperCase()}
                          </span>
                        </div>
                        <div>
                          <p style={{ 
                            fontWeight: 'var(--mac-font-weight-medium)', 
                            color: 'var(--mac-text-primary)',
                            fontSize: 'var(--mac-font-size-sm)',
                            margin: 0
                          }}>
                            {user.profile?.full_name || user.full_name || user.username}
                          </p>
                          <p style={{ 
                            fontSize: '12px', 
                            color: 'var(--mac-text-secondary)',
                            margin: '4px 0 0 0'
                          }}>{user.email}</p>
                        </div>
                      </div>
                    </td>
                    <td style={{ 
                      padding: '12px 16px',
                      borderRight: '1px solid var(--mac-border)',
                      borderBottom: '1px solid var(--mac-border)'
                    }}>
                      <MacOSBadge 
                        variant={user.role === 'Admin' ? 'error' : user.role === 'Doctor' ? 'success' : 'info'}
                      >
                        {getRoleLabel(user.role)}
                      </MacOSBadge>
                    </td>
                    <td style={{ 
                      padding: '12px 16px',
                      borderRight: '1px solid var(--mac-border)',
                      borderBottom: '1px solid var(--mac-border)'
                    }}>
                      <MacOSBadge 
                        variant={user.is_active ? 'success' : 'warning'}
                      >
                        {getUserStatusLabel(user.is_active)}
                      </MacOSBadge>
                    </td>
                    <td style={{ 
                      padding: '12px 16px', 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)',
                      borderRight: '1px solid var(--mac-border)',
                      borderBottom: '1px solid var(--mac-border)'
                    }}>
                      {user.profile?.last_login ? new Date(user.profile.last_login).toLocaleString('ru-RU') : 'Никогда'}
                    </td>
                    <td style={{ 
                      padding: '12px 16px',
                      borderBottom: '1px solid var(--mac-border)'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <button 
                          onClick={() => handleEditUser(user)}
                          style={{ 
                            padding: '4px', 
                            borderRadius: 'var(--mac-radius-sm)', 
                            transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
                            color: 'var(--mac-text-secondary)',
                            backgroundColor: 'transparent',
                            border: 'none',
                            cursor: 'pointer'
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)'}
                          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                          title="Редактировать"
                        >
                          <Edit style={{ width: '16px', height: '16px' }} />
                        </button>
                        <button 
                          onClick={() => handleDeleteUser(user)}
                          style={{ 
                            padding: '4px', 
                            borderRadius: 'var(--mac-radius-sm)', 
                            transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
                            color: 'var(--mac-error)',
                            backgroundColor: 'transparent',
                            border: 'none',
                            cursor: 'pointer'
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)'}
                          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                          title="Удалить"
                        >
                          <Trash2 style={{ width: '16px', height: '16px' }} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Пагинация */}
        {pagination.total_pages > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '24px' }}>
            <div style={{ fontSize: '14px', color: 'var(--mac-text-secondary)' }}>
              Показано {((pagination.page - 1) * pagination.per_page) + 1}-{Math.min(pagination.page * pagination.per_page, pagination.total)} из {pagination.total} пользователей
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <MacOSButton
                variant="outline"
                onClick={() => changePage(pagination.page - 1)}
                disabled={pagination.page <= 1}
                style={{ padding: '4px 12px' }}
              >
                Назад
              </MacOSButton>
              
              {/* Номера страниц */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                  let pageNum;
                  if (pagination.total_pages <= 5) {
                    pageNum = i + 1;
                  } else if (pagination.page <= 3) {
                    pageNum = i + 1;
                  } else if (pagination.page >= pagination.total_pages - 2) {
                    pageNum = pagination.total_pages - 4 + i;
                  } else {
                    pageNum = pagination.page - 2 + i;
                  }
                  
                  return (
                    <button
                      key={pageNum}
                      onClick={() => changePage(pageNum)}
                      style={{
                        padding: '4px 12px',
                        borderRadius: 'var(--mac-radius-sm)',
                        background: pageNum === pagination.page ? 'var(--mac-accent-blue)' : 'transparent',
                        color: pageNum === pagination.page ? 'white' : 'var(--mac-text-primary)',
                        border: 'none',
                        cursor: 'pointer',
                        fontSize: 'var(--mac-font-size-sm)',
                        transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                      }}
                      onMouseEnter={(e) => {
                        if (pageNum !== pagination.page) {
                          e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (pageNum !== pagination.page) {
                          e.currentTarget.style.backgroundColor = 'transparent';
                        }
                      }}
                    >
                      {pageNum}
                    </button>
                  );
                })}
              </div>
              
              <MacOSButton
                variant="outline"
                onClick={() => changePage(pagination.page + 1)}
                disabled={pagination.page >= pagination.total_pages}
                style={{ padding: '4px 12px' }}
              >
                Далее
              </MacOSButton>
            </div>
          </div>
        )}
      </MacOSCard>

      {/* ✅ УЛУЧШЕНИЕ: Модальное окно пользователя с универсальным хуком */}
      <UserModal
        isOpen={userModal.isOpen}
        onClose={handleCloseUserModal}
        user={userModal.selectedItem}
        onSave={handleSaveUser}
        loading={userModal.loading}
      />
    </div>
  );

  const AnalyticsSection = () => {
    const [analyticsFilters, setAnalyticsFilters] = useState({
      period: 'week',
      department: 'all',
      doctor: 'all'
    });
    
    // Загружаем список врачей для фильтра
    const { data: doctorsList } = useAdminData('/doctors?limit=100&active_only=true', {
      enabled: true,
      initialData: []
    });

    const handleFilterChange = (filterType, value) => {
      setAnalyticsFilters(prev => ({
        ...prev,
        [filterType]: value
      }));
    };

    // Загрузка данных аналитики
    const { 
      data: analyticsData, 
      loading: analyticsLoading, 
      error: analyticsError,
      refresh: refreshAnalytics
    } = useAdminData(`/admin/analytics/overview?period=${analyticsFilters.period}&department=${analyticsFilters.department === 'all' ? '' : analyticsFilters.department}&doctor_id=${analyticsFilters.doctor === 'all' ? '' : analyticsFilters.doctor}`, {
      refreshInterval: 0,
      enabled: true,
      initialData: {
        metrics: {
          totalAppointments: 0,
          totalRevenue: 0,
          totalPatients: 0,
          averageCheck: 0
        },
        topDoctors: [],
        appointmentsByStatus: []
      }
    });

    // Загрузка данных для графиков
    const { 
      data: chartsData, 
      loading: chartsLoading, 
      error: chartsError,
      refresh: refreshCharts
    } = useAdminData(`/admin/analytics/charts?period=${analyticsFilters.period}&chart_type=appointments&department=${analyticsFilters.department === 'all' ? '' : analyticsFilters.department}&doctor_id=${analyticsFilters.doctor === 'all' ? '' : analyticsFilters.doctor}`, {
      refreshInterval: 0,
      enabled: true,
      initialData: {
        labels: [],
        data: []
      }
    });

    const applyFilters = () => {
      refreshAnalytics();
      refreshCharts();
    };

    const formatCurrency = (amount) => {
      return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'UZS',
        minimumFractionDigits: 0
      }).format(amount);
    };

    return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <MacOSCard 
        variant="default"
          style={{ padding: '24px' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <h2 style={{ 
            fontSize: 'var(--mac-font-size-xl)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>Аналитика и отчеты</h2>
          <div style={{ display: 'flex', gap: '16px' }}>
            <MacOSButton 
              variant="outline"
              onClick={() => {
                // Экспорт реальных данных аналитики в CSV
                if (!analyticsData) {
                  alert('Нет данных для экспорта');
                  return;
                }
                
                const csvRows = [
                  ['Период', 'Записи', 'Доходы', 'Пациенты', 'Средний чек'],
                  [
                    analyticsFilters.period,
                    analyticsData.metrics?.totalAppointments || 0,
                    analyticsData.metrics?.totalRevenue || 0,
                    analyticsData.metrics?.totalPatients || 0,
                    analyticsData.metrics?.averageCheck || 0
                  ]
                ];
                
                const csvData = csvRows.map(row => row.join(',')).join('\n');
                const blob = new Blob([csvData], { type: 'text/csv;charset=utf-8;' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `analytics-export-${analyticsFilters.period}-${new Date().toISOString().split('T')[0]}.csv`;
                a.click();
                window.URL.revokeObjectURL(url);
              }}
              disabled={!analyticsData || analyticsLoading}
            >
              <Download style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Экспорт
            </MacOSButton>
            <MacOSButton
              onClick={() => {
                // Открыть генератор отчетов
                navigate('/admin/reports');
              }}
            >
              <BarChart3 style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Создать отчет
            </MacOSButton>
          </div>
        </div>

        {/* Фильтры */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px', 
          marginBottom: '24px' 
        }} role="group" aria-label="Фильтры аналитики">
          <div>
            <label htmlFor="period" style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              marginBottom: '4px', 
              color: 'var(--mac-text-primary)' 
            }}>Период</label>
            <MacOSSelect
              id="period"
              aria-label="Период"
              value={analyticsFilters.period}
              onChange={(value) => handleFilterChange('period', value)}
              options={[
                { value: 'today', label: 'Сегодня' },
                { value: 'week', label: 'Неделя' },
                { value: 'month', label: 'Месяц' },
                { value: 'quarter', label: 'Квартал' },
                { value: 'year', label: 'Год' }
              ]}
            />
          </div>
          <div>
            <label htmlFor="department" style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              marginBottom: '4px', 
              color: 'var(--mac-text-primary)' 
            }}>Отделение</label>
            <MacOSSelect
              id="department"
              aria-label="Отделение"
              value={analyticsFilters.department}
              onChange={(value) => handleFilterChange('department', value)}
              options={[
                { value: 'all', label: 'Все отделения' },
                { value: 'cardiology', label: 'Кардиология' },
                { value: 'dermatology', label: 'Дерматология' },
                { value: 'stomatology', label: 'Стоматология' },
                { value: 'dentistry', label: 'Стоматология' },
                { value: 'laboratory', label: 'Лаборатория' },
                { value: 'cosmetology', label: 'Косметология' },
                { value: 'procedures', label: 'Процедуры' },
                { value: 'physiotherapy', label: 'Физиотерапия' },
                { value: 'functional_diagnostics', label: 'Функциональная диагностика' },
                { value: 'general', label: 'Общее' }
              ]}
            />
          </div>
          <div>
            <label htmlFor="doctor" style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              marginBottom: '4px', 
              color: 'var(--mac-text-primary)' 
            }}>Врач</label>
            <MacOSSelect
              id="doctor"
              aria-label="Врач"
              value={analyticsFilters.doctor}
              onChange={(value) => handleFilterChange('doctor', value)}
              options={[
                { value: 'all', label: 'Все врачи' },
                ...(Array.isArray(doctorsList) ? doctorsList : []).map(doctor => ({
                  value: doctor.user_id?.toString() || doctor.id?.toString() || '',
                  label: doctor.user?.full_name || doctor.user?.username || `Врач #${doctor.id || doctor.user_id}`
                })).filter(opt => opt.value && opt.label)
              ]}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'end' }}>
            <MacOSButton 
              style={{ width: '100%' }} 
              aria-label="Применить фильтры"
              onClick={applyFilters}
            >
              <Filter style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Применить
            </MacOSButton>
          </div>
        </div>

        {/* Ключевые метрики */}
        {analyticsLoading ? (
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
            gap: '16px', 
            marginBottom: '24px' 
          }}>
            <MacOSLoadingSkeleton type="card" count={4} />
          </div>
        ) : analyticsError ? (
          <MacOSEmptyState
            icon={AlertTriangle}
            title="Ошибка загрузки аналитики"
            description="Не удалось загрузить данные. Проверьте подключение к серверу."
            action={
              <MacOSButton onClick={refreshAnalytics} variant="primary">
                <RefreshCw size={16} />
                Повторить попытку
              </MacOSButton>
            }
          />
        ) : (
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
            gap: '16px', 
            marginBottom: '24px' 
          }}>
            <MacOSStatCard
              title="Всего записей"
              value={analyticsData?.metrics?.totalAppointments?.toLocaleString() || '0'}
              icon={Calendar}
              color="var(--mac-accent-blue)"
              loading={analyticsLoading}
            />
            
            <MacOSStatCard
              title="Доходы"
              value={formatCurrency(analyticsData?.metrics?.totalRevenue || 0)}
              icon={CreditCard}
              color="var(--mac-success)"
              loading={analyticsLoading}
            />
            
            <MacOSStatCard
              title="Пациенты"
              value={analyticsData?.metrics?.totalPatients?.toLocaleString() || '0'}
              icon={Users}
              color="var(--mac-info)"
              loading={analyticsLoading}
            />
            
            <MacOSStatCard
              title="Средний чек"
              value={formatCurrency(analyticsData?.metrics?.averageCheck || 0)}
              icon={TrendingUp}
              color="var(--mac-warning)"
              loading={analyticsLoading}
            />
          </div>
        )}

        {/* Графики */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
          gap: '24px' 
        }}>
          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '16px',
              margin: 0
            }}>Динамика записей</h3>
            {chartsLoading ? (
              <MacOSLoadingSkeleton height="256px" />
            ) : chartsError ? (
              <MacOSEmptyState
                icon={AlertTriangle}
                title="Ошибка загрузки графика"
                description="Не удалось загрузить данные графика"
              />
            ) : chartsData?.data && chartsData.data.length > 0 ? (
              <div style={{ 
                height: '256px', 
                padding: '16px',
                backgroundColor: 'var(--mac-bg-tertiary)', 
                borderRadius: 'var(--mac-radius-md)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between'
              }}>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'flex-end', 
                  justifyContent: 'space-around',
                  height: '200px',
                  gap: '4px'
                }}>
                  {chartsData.data.map((item, index) => {
                    const maxValue = Math.max(...chartsData.data.map(d => d.appointments || 0));
                    const height = maxValue > 0 ? (item.appointments / maxValue) * 180 : 0;
                    return (
                      <div key={index} style={{ 
                        flex: 1, 
                        display: 'flex', 
                        flexDirection: 'column', 
                        alignItems: 'center',
                        gap: '4px'
                      }}>
                        <div style={{
                          width: '100%',
                          height: `${height}px`,
                          background: 'linear-gradient(to top, var(--mac-primary), var(--mac-primary-light))',
                          borderRadius: '4px 4px 0 0',
                          minHeight: '4px',
                          transition: 'height 0.3s ease'
                        }} />
                        <span style={{ 
                          fontSize: '10px', 
                          color: 'var(--mac-text-tertiary)',
                          textAlign: 'center'
                        }}>
                          {chartsData.labels[index]}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'center', 
                  marginTop: '8px',
                  fontSize: '12px',
                  color: 'var(--mac-text-secondary)'
                }}>
                  <span>Всего записей: {chartsData.data.reduce((sum, d) => sum + (d.appointments || 0), 0)}</span>
                </div>
              </div>
            ) : (
              <div style={{ 
                height: '256px', 
                backgroundColor: 'var(--mac-bg-tertiary)', 
                borderRadius: 'var(--mac-radius-md)', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center' 
              }}>
                <p style={{ color: 'var(--mac-text-secondary)' }}>Нет данных за выбранный период</p>
              </div>
            )}
          </MacOSCard>
          
          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '16px',
              margin: 0
            }}>Статусы записей</h3>
            {analyticsLoading ? (
              <MacOSLoadingSkeleton height="256px" />
            ) : analyticsError ? (
              <MacOSEmptyState
                icon={AlertTriangle}
                title="Ошибка загрузки"
                description="Не удалось загрузить данные"
              />
            ) : analyticsData?.appointmentsByStatus && analyticsData.appointmentsByStatus.length > 0 ? (
              <div style={{ 
                display: 'flex', 
                flexDirection: 'column', 
                gap: '12px',
                padding: '16px'
              }}>
                {analyticsData.appointmentsByStatus.map((item, index) => {
                  const total = analyticsData.appointmentsByStatus.reduce((sum, s) => sum + s.count, 0);
                  const percentage = total > 0 ? (item.count / total) * 100 : 0;
                  return (
                    <div key={index} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <div 
                          style={{ 
                            width: '12px', 
                            height: '12px', 
                            borderRadius: 'var(--mac-radius-full)',
                            background: index === 0 ? 'var(--mac-success)' : 
                                       index === 1 ? 'var(--mac-warning)' : 'var(--mac-danger)'
                          }}
                        ></div>
                        <span style={{ 
                          fontSize: 'var(--mac-font-size-sm)', 
                          fontWeight: 'var(--mac-font-weight-medium)', 
                          color: 'var(--mac-text-primary)' 
                        }}>
                          {item.status}
                        </span>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <span style={{ 
                          fontSize: 'var(--mac-font-size-sm)', 
                          fontWeight: 'var(--mac-font-weight-medium)', 
                          color: 'var(--mac-text-primary)' 
                        }}>
                          {item.count}
                        </span>
                        <span style={{ 
                          fontSize: 'var(--mac-font-size-xs)', 
                          marginLeft: '8px', 
                          color: 'var(--mac-text-secondary)' 
                        }}>
                          ({percentage.toFixed(1)}%)
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={{ 
                height: '256px', 
                backgroundColor: 'var(--mac-bg-tertiary)', 
                borderRadius: 'var(--mac-radius-md)', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center' 
              }}>
                <p style={{ color: 'var(--mac-text-secondary)' }}>Нет данных</p>
              </div>
            )}
          </MacOSCard>
        </div>

        {/* Топ врачи */}
        <MacOSCard 
          style={{ padding: '24px', marginTop: '24px' }}
        >
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)', 
            marginBottom: '16px',
            margin: 0
          }}>Топ врачи по количеству приемов</h3>
          
          {analyticsLoading ? (
            <MacOSLoadingSkeleton height="200px" />
          ) : analyticsError ? (
            <MacOSEmptyState
              icon={Users}
              title="Ошибка загрузки"
              description="Не удалось загрузить данные о врачах"
            />
          ) : !analyticsData?.topDoctors || analyticsData.topDoctors.length === 0 ? (
            <MacOSEmptyState
              icon={Users}
              title="Нет данных о врачах"
              description="За выбранный период нет данных о врачах"
            />
          ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {analyticsData.topDoctors.map((doctor, index) => (
              <div key={index} style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between', 
                padding: '12px', 
                backgroundColor: 'var(--mac-bg-tertiary)', 
                borderRadius: 'var(--mac-radius-md)' 
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ 
                    width: '32px', 
                    height: '32px', 
                    backgroundColor: 'var(--mac-accent)', 
                    borderRadius: '50%', 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center' 
                  }}>
                    <span style={{ 
                      color: 'white', 
                      fontSize: 'var(--mac-font-size-sm)', 
                        fontWeight: 'var(--mac-font-weight-medium)' 
                    }}>{index + 1}</span>
                  </div>
                  <div>
                    <p style={{ 
                      fontWeight: 'var(--mac-font-weight-medium)', 
                      color: 'var(--mac-text-primary)',
                      margin: 0
                    }}>{doctor.user?.full_name || doctor.name || doctor.user?.username || 'Неизвестно'}</p>
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)',
                      margin: 0
                    }}>{doctor.specialty || doctor.department || 'Неизвестно'}</p>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <p style={{ 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)',
                    margin: 0
                  }}>{doctor.patients} записей</p>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>{doctor.revenue}</p>
                </div>
              </div>
            ))}
          </div>
          )}
        </MacOSCard>
      </MacOSCard>
    </div>
  );
  };

  const renderContent = () => {
    switch (current) {
      case 'dashboard':
        return renderDashboard();
      case 'analytics':
        return <AnalyticsDashboard />;
      case 'wait-time-analytics':
        return <WaitTimeAnalytics />;
      case 'ai-analytics':
        return <AIAnalytics />;
      case 'analytics-insights':
        return <AnalyticsInsights />;
      case 'users':
      case 'user-data-transfer':
      case 'user-export':
      case 'group-permissions':
        return <UnifiedUserManagement renderUsersList={renderUsers} />;
      case 'doctors':
        return renderDoctors();
      case 'patients':
        return renderPatients();
      case 'appointments':
        return renderAppointments();
      case 'all-free':
        return <AllFreeApproval />;
      case 'benefit-settings':
        return <UnifiedSettings />;
      case 'wizard-settings':
        return <UnifiedSettings />;
      case 'payment-providers':
        return <UnifiedSettings />;
      case 'finance':
      case 'billing':
      case 'dynamic-pricing':
      case 'discount-benefits':
        return <UnifiedFinance renderFinance={renderFinance} />;
      case 'reports':
        return <UnifiedReports />;
      case 'clinic-management':
        return <ClinicManagement />;
      case 'queue-settings':
      case 'queue-limits':
        return <UnifiedSettings />;
      case 'ai-imaging':
      case 'treatment-recommendations':
      case 'drug-interactions':
      case 'risk-assessment':
      case 'voice-to-text':
      case 'smart-scheduling':
      case 'quality-control':
        return <UnifiedAITools />;
      case 'telegram-bot':
      case 'telegram-settings':
        return <UnifiedTelegramManagement />;
      case 'fcm-notifications':
      case 'registrar-notifications':
        return <UnifiedNotifications />;
      case 'phone-verification':
        return <PhoneVerificationManager />;
      case 'webhooks':
        return <WebhookManager />;
      case 'system':
        return <SystemManagement />;
      case 'cloud-printing':
        return <CloudPrintingManager />;
        case 'medical-equipment':
          return <MedicalEquipmentManager />;
        case 'graphql-explorer':
          return <GraphQLExplorer />;
      case 'services':
        // Вкладки для секции Services
        const serviceTabs = [
          { key: 'catalog', label: 'Справочник услуг', icon: Package },
          { key: 'departments', label: 'Управление отделениями', icon: Building2 }
        ];

        return (
          <div>
            {/* Вкладки */}
            <div style={{
              display: 'flex',
              gap: '8px',
              marginBottom: '24px',
              borderBottom: '1px solid var(--mac-border)',
              paddingBottom: '0'
            }}>
              {serviceTabs.map(tab => {
                const TabIcon = tab.icon;
                const isActive = servicesTab === tab.key;
                return (
                  <button
                    key={tab.key}
                    onClick={() => {
                      setServicesTab(tab.key);
                      // Обновляем URL
                      const params = new URLSearchParams(location.search);
                      params.set('servicesTab', tab.key);
                      navigate(`?${params.toString()}`, { replace: true });
                    }}
                    style={{
                      padding: '12px 20px',
                      background: 'transparent',
                      border: 'none',
                      borderBottom: isActive ? '2px solid var(--mac-accent)' : '2px solid transparent',
                      color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      fontSize: '14px',
                      fontWeight: isActive ? '600' : '500',
                      transition: 'all 0.2s ease',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                    }}
                    onMouseEnter={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.color = 'var(--mac-text-primary)';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isActive) {
                        e.currentTarget.style.color = 'var(--mac-text-secondary)';
                      }
                    }}
                  >
                    <TabIcon size={18} />
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* Содержимое вкладок */}
            {servicesTab === 'catalog' && <ServiceCatalog />}
            {servicesTab === 'departments' && <DepartmentManagement />}
          </div>
        );
      case 'departments':
        return <DepartmentManagement />;
      case 'ai-settings':
        return <UnifiedSettings />;
      case 'display-settings':
        return <UnifiedSettings />;
      case 'activation':
        return <ActivationSystem />;
      case 'settings':
      case 'security':
        return <UnifiedSettings />;
      default:
        return (
          <MacOSCard style={{ padding: '48px' }}>
            <div style={{ textAlign: 'center' }}>
              <h2 style={{ 
                fontSize: '24px', 
                fontWeight: '600', 
                marginBottom: '16px',
                color: 'var(--mac-text-primary)',
                margin: 0
              }}>
                {tabs.find(tab => tab.id === current)?.label || 'Неизвестный раздел'}
              </h2>
              <p style={{ color: 'var(--mac-text-secondary)' }}>Этот раздел находится в разработке</p>
            </div>
          </MacOSCard>
        );
    }
  };

  // Заглушки для остальных разделов
  const renderDoctors = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard 
        variant="default"
        style={{ padding: '24px' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <h2 style={{ 
            fontSize: 'var(--mac-font-size-xl)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>Управление врачами</h2>
          <MacOSButton onClick={handleCreateDoctor}>
            <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            Добавить врача
          </MacOSButton>
        </div>
        
        {/* Поиск и фильтры */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
          <div style={{ flex: '1' }}>
            <MacOSInput
              type="text"
              placeholder="Поиск врачей..."
              value={doctorsSearchTerm}
              onChange={(e) => setDoctorsSearchTerm(e.target.value)}
              icon={Search}
              iconPosition="left"
            />
          </div>
          <MacOSInput
            type="text"
            placeholder="Специализация..."
            value={filterSpecialization}
            onChange={(e) => setFilterSpecialization(e.target.value)}
          />
          <MacOSSelect
            value={filterDepartment}
            onChange={(e) => setFilterDepartment(e.target.value)}
            options={[
              { value: '', label: 'Все отделения' },
              { value: 'cardiology', label: 'Кардиология' },
              { value: 'dermatology', label: 'Дерматология' },
              { value: 'dentistry', label: 'Стоматология' },
              { value: 'stomatology', label: 'Стоматология' },
              { value: 'laboratory', label: 'Лаборатория' },
              { value: 'cosmetology', label: 'Косметология' },
              { value: 'procedures', label: 'Процедуры' },
              { value: 'physiotherapy', label: 'Физиотерапия' },
              { value: 'functional_diagnostics', label: 'Функциональная диагностика' },
              { value: 'general', label: 'Общее' }
            ]}
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--mac-radius-sm)',
              border: '1px solid var(--mac-border)',
              background: 'var(--mac-bg-primary)',
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-sm)',
              outline: 'none'
            }}
          />
          <MacOSSelect
            value={doctorsFilterStatus}
            onChange={(e) => setDoctorsFilterStatus(e.target.value)}
            options={[
              { value: '', label: 'Все статусы' },
              { value: 'active', label: 'Активен' },
              { value: 'inactive', label: 'Неактивен' },
              { value: 'on_leave', label: 'В отпуске' }
            ]}
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--mac-radius-sm)',
              border: '1px solid var(--mac-border)',
              background: 'var(--mac-bg-primary)',
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-sm)',
              outline: 'none'
            }}
          />
        </div>

        {/* Таблица врачей */}
        <div style={{ overflowX: 'auto' }}>
          {doctorsLoading ? (
            <MacOSLoadingSkeleton type="table" count={5} />
          ) : doctorsError ? (
            <EmptyState
              type="error"
              title="Ошибка загрузки врачей"
              description="Не удалось загрузить список врачей"
              action={
                <MacOSButton onClick={() => window.location.reload()}>
                  <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                  Обновить
                </MacOSButton>
              }
            />
          ) : doctors.length === 0 ? (
            <EmptyState
              type="users"
              title="Врачи не найдены"
              description={doctorsSearchTerm || filterSpecialization || filterDepartment || doctorsFilterStatus 
                ? 'Попробуйте изменить параметры поиска' 
                : 'В системе пока нет врачей'
              }
              action={
                <MacOSButton onClick={handleCreateDoctor}>
                  <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                  Добавить первого врача
                </MacOSButton>
              }
            />
          ) : (
            <table style={{ width: '100%' }} role="table" aria-label="Таблица врачей">
              <thead>
                <tr style={{ 
                  backgroundColor: 'var(--mac-bg-tertiary)', 
                  borderBottom: '1px solid var(--mac-border)' 
                }}>
                  <th scope="col" style={{ 
                    textAlign: 'left', 
                    padding: '12px 16px', 
                    color: 'var(--mac-text-primary)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>Врач</th>
                  <th scope="col" style={{ 
                    textAlign: 'left', 
                    padding: '12px 16px', 
                    color: 'var(--mac-text-primary)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>Специализация</th>
                  <th scope="col" style={{ 
                    textAlign: 'left', 
                    padding: '12px 16px', 
                    color: 'var(--mac-text-primary)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>Отделение</th>
                  <th scope="col" style={{ 
                    textAlign: 'left', 
                    padding: '12px 16px', 
                    color: 'var(--mac-text-primary)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>Опыт</th>
                  <th scope="col" style={{ 
                    textAlign: 'left', 
                    padding: '12px 16px', 
                    color: 'var(--mac-text-primary)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>Статус</th>
                  <th scope="col" style={{ 
                    textAlign: 'left', 
                    padding: '12px 16px', 
                    color: 'var(--mac-text-primary)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>Пациенты</th>
                  <th scope="col" style={{ 
                    textAlign: 'left', 
                    padding: '12px 16px', 
                    color: 'var(--mac-text-primary)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>Действия</th>
                </tr>
              </thead>
              <tbody>
                {doctors.map((doctor) => (
                  <tr key={doctor.id} style={{ 
                    borderBottom: '1px solid var(--mac-border)', 
                    transition: 'background-color var(--mac-duration-normal) var(--mac-ease)'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <div style={{
                          width: '40px',
                          height: '40px',
                          borderRadius: '50%',
                          backgroundColor: 'var(--mac-accent)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'white',
                          fontSize: 'var(--mac-font-size-sm)',
                          fontWeight: '500'
                        }}>
                          <span>
                            {(() => {
                              const name = doctor.user?.full_name || doctor.name || doctor.user?.username || 'Д';
                              return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
                            })()}
                          </span>
                        </div>
                        <div>
                          <p style={{ 
                            fontWeight: 'var(--mac-font-weight-medium)', 
                            color: 'var(--mac-text-primary)',
                            fontSize: 'var(--mac-font-size-sm)',
                            margin: 0
                          }}>{doctor.user?.full_name || doctor.name || doctor.user?.username || 'Неизвестно'}</p>
                          <p style={{ 
                            fontSize: '12px', 
                            color: 'var(--mac-text-secondary)',
                            margin: '4px 0 0 0'
                          }}>{doctor.user?.email || doctor.email || 'Нет email'}</p>
                          {doctor.user?.phone && (
                            <p style={{ 
                              fontSize: '11px', 
                              color: 'var(--mac-text-tertiary)',
                              margin: '2px 0 0 0'
                            }}>{doctor.user.phone}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <MacOSBadge variant="info">
                        {doctor.specialty || doctor.specialization || 'Не указано'}
                      </MacOSBadge>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <MacOSBadge variant="success">
                        {doctor.specialty ? getDepartmentLabel(doctor.specialty) : (doctor.department ? getDepartmentLabel(doctor.department) : 'Не указано')}
                      </MacOSBadge>
                    </td>
                    <td style={{ 
                      padding: '12px 16px', 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)' 
                    }}>
                      {doctor.experience ? `${doctor.experience} лет` : 'Не указано'}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <MacOSBadge 
                        variant={doctor.active ? 'success' : 'warning'}
                      >
                        {doctor.active ? 'Активен' : 'Неактивен'}
                      </MacOSBadge>
                    </td>
                    <td style={{ 
                      padding: '12px 16px', 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)' 
                    }}>
                      {doctor.patientsCount || 0} пациентов
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <button 
                          onClick={() => handleEditDoctor(doctor)}
                          style={{ 
                            padding: '4px', 
                            borderRadius: 'var(--mac-radius-sm)', 
                            transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
                            color: 'var(--mac-text-secondary)',
                            backgroundColor: 'transparent',
                            border: 'none',
                            cursor: 'pointer'
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)'}
                          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                          title="Редактировать"
                        >
                          <Edit style={{ width: '16px', height: '16px' }} />
                        </button>
                        <button 
                          onClick={() => handleDeleteDoctor(doctor)}
                          style={{ 
                            padding: '4px', 
                            borderRadius: 'var(--mac-radius-sm)', 
                            transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
                            color: 'var(--mac-error)',
                            backgroundColor: 'transparent',
                            border: 'none',
                            cursor: 'pointer'
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)'}
                          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                          title="Удалить"
                        >
                          <Trash2 style={{ width: '16px', height: '16px' }} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </MacOSCard>

      {/* ✅ УЛУЧШЕНИЕ: Модальное окно врача с универсальным хуком */}
      <DoctorModal
        isOpen={doctorModal.isOpen}
        onClose={handleCloseDoctorModal}
        doctor={doctorModal.selectedItem}
        onSave={handleSaveDoctor}
        loading={doctorModal.loading}
      />
    </div>
  );

  const renderPatients = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard 
        variant="default"
        style={{ padding: '24px' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <h2 style={{ 
            fontSize: 'var(--mac-font-size-xl)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>Управление пациентами</h2>
          <MacOSButton onClick={handleCreatePatient}>
            <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            Добавить пациента
          </MacOSButton>
        </div>
        
        {/* Поиск и фильтры */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
          <div style={{ flex: '1' }}>
            <MacOSInput
              type="text"
              placeholder="Поиск пациентов..."
              value={patientsSearchTerm}
              onChange={(e) => setPatientsSearchTerm(e.target.value)}
              icon={Search}
              iconPosition="left"
              style={{
                width: '100%',
                paddingLeft: '40px',
                paddingRight: '16px',
                paddingTop: '8px',
                paddingBottom: '8px',
                borderRadius: 'var(--mac-radius-sm)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                outline: 'none',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
            />
          </div>
          <MacOSSelect
            value={filterGender}
            onChange={(e) => setFilterGender(e.target.value)}
            options={[
              { value: '', label: 'Все полы' },
              { value: 'male', label: 'Мужской' },
              { value: 'female', label: 'Женский' }
            ]}
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--mac-radius-sm)',
              border: '1px solid var(--mac-border)',
              background: 'var(--mac-bg-primary)',
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-sm)',
              outline: 'none'
            }}
          />
          <MacOSSelect
            value={filterAgeRange}
            onChange={(e) => setFilterAgeRange(e.target.value)}
            options={[
              { value: '', label: 'Все возрасты' },
              { value: '0-18', label: '0-18 лет' },
              { value: '19-35', label: '19-35 лет' },
              { value: '36-50', label: '36-50 лет' },
              { value: '51-65', label: '51-65 лет' },
              { value: '65+', label: '65+ лет' }
            ]}
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--mac-radius-sm)',
              border: '1px solid var(--mac-border)',
              background: 'var(--mac-bg-primary)',
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-sm)',
              outline: 'none'
            }}
          />
          <MacOSSelect
            value={filterBloodType}
            onChange={(e) => setFilterBloodType(e.target.value)}
            options={[
              { value: '', label: 'Все группы крови' },
              { value: 'A+', label: 'A+' },
              { value: 'A-', label: 'A-' },
              { value: 'B+', label: 'B+' },
              { value: 'B-', label: 'B-' },
              { value: 'AB+', label: 'AB+' },
              { value: 'AB-', label: 'AB-' },
              { value: 'O+', label: 'O+' },
              { value: 'O-', label: 'O-' }
            ]}
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--mac-radius-sm)',
              border: '1px solid var(--mac-border)',
              background: 'var(--mac-bg-primary)',
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-sm)',
              outline: 'none'
            }}
          />
        </div>

        {/* Таблица пациентов */}
        <div style={{ overflowX: 'auto' }}>
          {patientsLoading ? (
            <MacOSLoadingSkeleton type="table" count={5} />
          ) : patientsError ? (
            <MacOSEmptyState
              type="error"
              title="Ошибка загрузки пациентов"
              description="Не удалось загрузить список пациентов"
              action={
                <MacOSButton onClick={() => window.location.reload()}>
                  <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                  Обновить
                </MacOSButton>
              }
            />
          ) : patients.length === 0 ? (
            <MacOSEmptyState
              type="users"
              title="Пациенты не найдены"
              description={patientsSearchTerm || filterGender || filterAgeRange || filterBloodType 
                ? 'Попробуйте изменить параметры поиска' 
                : 'В системе пока нет пациентов'
              }
              action={
                <MacOSButton onClick={handleCreatePatient}>
                  <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                  Добавить первого пациента
                </MacOSButton>
              }
            />
          ) : (
            <MacOSTable
              columns={[
                { key: 'patient', title: 'Пациент', width: '30%' },
                { key: 'age', title: 'Возраст', width: '8%' },
                { key: 'gender', title: 'Пол', width: '8%' },
                { key: 'phone', title: 'Телефон', width: '12%' },
                { key: 'bloodType', title: 'Группа крови', width: '10%' },
                { key: 'lastVisit', title: 'Последний визит', width: '12%' },
                { key: 'visits', title: 'Визиты', width: '10%' },
                { key: 'actions', title: 'Действия', width: '10%' }
              ]}
              data={patients.map((patient) => ({
                id: patient.id,
                patient: (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <div style={{
                          width: '40px',
                          height: '40px',
                          borderRadius: '50%',
                          backgroundColor: 'var(--mac-accent)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'white',
                          fontSize: 'var(--mac-font-size-sm)',
                          fontWeight: '500'
                        }}>
                          <span>
                            {patient.firstName[0]}{patient.lastName[0]}
                          </span>
                        </div>
                        <div>
                          <p style={{ 
                            fontWeight: 'var(--mac-font-weight-medium)', 
                            color: 'var(--mac-text-primary)',
                            fontSize: 'var(--mac-font-size-sm)',
                            margin: 0
                          }}>
                            {patient.lastName} {patient.firstName} {patient.middleName}
                          </p>
                          <p style={{ 
                            fontSize: '12px', 
                            color: 'var(--mac-text-secondary)',
                            margin: '4px 0 0 0'
                          }}>
                            {patient.email || 'Email не указан'}
                          </p>
                          {patient.address && (
                            <p style={{ 
                              fontSize: '11px', 
                              color: 'var(--mac-text-tertiary)',
                              margin: '2px 0 0 0'
                            }}>
                              {patient.address}
                            </p>
                          )}
                        </div>
                      </div>
                ),
                age: (
                  <div style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)' 
                    }}>
                      {calculateAge(patient.birthDate)} лет
                  </div>
                ),
                gender: (
                  <MacOSBadge variant={patient.gender === 'male' ? 'info' : 'success'}>
                        {getGenderLabel(patient.gender)}
                  </MacOSBadge>
                ),
                phone: (
                  <div style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)' 
                    }}>
                      {patient.phone}
                  </div>
                ),
                bloodType: (
                  patient.bloodType ? (
                    <MacOSBadge variant="warning">
                          {patient.bloodType}
                    </MacOSBadge>
                      ) : (
                        <span style={{ 
                          fontSize: 'var(--mac-font-size-sm)', 
                          color: 'var(--mac-text-tertiary)' 
                        }}>Не указано</span>
                  )
                ),
                lastVisit: (
                  <div style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)' 
                    }}>
                      {patient.lastVisit ? new Date(patient.lastVisit).toLocaleDateString('ru-RU') : 'Нет визитов'}
                  </div>
                ),
                visits: (
                  <div style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)' 
                    }}>
                      {patient.visitsCount} визитов
                  </div>
                ),
                actions: (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <MacOSButton
                      variant="outline"
                          onClick={() => handleEditPatient(patient)}
                          style={{ 
                        padding: '6px',
                        minWidth: 'auto',
                        width: '32px',
                        height: '32px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}
                          title="Редактировать"
                        >
                          <Edit style={{ width: '16px', height: '16px' }} />
                    </MacOSButton>
                    <MacOSButton
                      variant="outline"
                          onClick={() => handleDeletePatient(patient)}
                          style={{ 
                        padding: '6px',
                        minWidth: 'auto',
                        width: '32px',
                        height: '32px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                            color: 'var(--mac-error)',
                        borderColor: 'var(--mac-error)'
                          }}
                          title="Удалить"
                        >
                          <Trash2 style={{ width: '16px', height: '16px' }} />
                    </MacOSButton>
                      </div>
                )
              }))}
            />
          )}
        </div>
      </MacOSCard>

      {/* Модальное окно пациента */}
      {/* ✅ УЛУЧШЕНИЕ: Модальное окно пациента с универсальным хуком */}
      <PatientModal
        isOpen={patientModal.isOpen}
        onClose={handleClosePatientModal}
        patient={patientModal.selectedItem}
        onSave={handleSavePatient}
        loading={patientModal.loading}
      />
    </div>
  );

  const renderAppointments = () => {
    const statusStats = getStatusStats();
    const todayAppointments = getTodayAppointments();
    const tomorrowAppointments = getTomorrowAppointments();

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Статистика записей */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>Всего записей</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-text-primary)',
                  margin: '4px 0 0 0'
                }}>{appointments.length}</p>
              </div>
              <Calendar style={{ width: '32px', height: '32px', color: 'var(--mac-accent)' }} />
            </div>
          </MacOSCard>
          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>На сегодня</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-text-primary)',
                  margin: '4px 0 0 0'
                }}>{todayAppointments.length}</p>
              </div>
              <Clock style={{ width: '32px', height: '32px', color: 'var(--mac-success)' }} />
            </div>
          </MacOSCard>
          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>На завтра</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-text-primary)',
                  margin: '4px 0 0 0'
                }}>{tomorrowAppointments.length}</p>
              </div>
              <Calendar style={{ width: '32px', height: '32px', color: 'var(--mac-text-primary)' }} />
            </div>
          </MacOSCard>
          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>Ожидают</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-text-primary)',
                  margin: '4px 0 0 0'
                }}>{statusStats.pending}</p>
              </div>
              <Clock style={{ width: '32px', height: '32px', color: 'var(--mac-warning)' }} />
            </div>
          </MacOSCard>
        </div>

        <MacOSCard 
          variant="default"
          style={{ padding: '24px' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
            <h2 style={{ 
              fontSize: '20px', 
              fontWeight: '600', 
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>Управление записями</h2>
            <MacOSButton onClick={handleCreateAppointment}>
              <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Создать запись
            </MacOSButton>
          </div>
          
          {/* Поиск и фильтры */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
            <div style={{ flex: '1', position: 'relative' }}>
              <Search style={{ 
                position: 'absolute', 
                left: '12px', 
                top: '50%', 
                transform: 'translateY(-50%)', 
                width: '16px', 
                height: '16px', 
                color: 'var(--mac-text-tertiary)',
                zIndex: 1
              }} />
              <MacOSInput
                type="text"
                placeholder="Поиск записей..."
                value={appointmentsSearchTerm}
                onChange={(e) => setAppointmentsSearchTerm(e.target.value)}
                style={{
                  width: '100%',
                  paddingLeft: '40px',
                  paddingRight: '16px'
                }}
              />
            </div>
            <MacOSSelect
              value={appointmentFilterStatus}
              onChange={(e) => setAppointmentFilterStatus(e.target.value)}
              options={[
                { value: '', label: 'Все статусы' },
                { value: 'pending', label: 'Ожидает' },
                { value: 'confirmed', label: 'Подтверждена' },
                { value: 'paid', label: 'Оплачена' },
                { value: 'in_visit', label: 'На приеме' },
                { value: 'completed', label: 'Завершена' },
                { value: 'cancelled', label: 'Отменена' },
                { value: 'no_show', label: 'Не явился' }
              ]}
              style={{ minWidth: '140px' }}
            />
            <MacOSInput
              type="date"
              value={appointmentFilterDate}
              onChange={(e) => setAppointmentFilterDate(e.target.value)}
              style={{ minWidth: '140px' }}
            />
            <MacOSSelect
              value={appointmentFilterDoctor}
              onChange={(e) => setAppointmentFilterDoctor(e.target.value)}
              options={[
                { value: '', label: 'Все врачи' },
                ...doctors.map(doctor => ({
                  value: doctor.id,
                  label: doctor.user?.full_name || doctor.name || doctor.user?.username || `Врач #${doctor.id}`
                }))
              ]}
              style={{ minWidth: '140px' }}
            />
          </div>

          {/* Таблица записей */}
          <div style={{ overflowX: 'auto' }}>
            {appointmentsLoading ? (
              <MacOSLoadingSkeleton type="table" count={5} />
            ) : appointmentsError ? (
              <EmptyState
                type="error"
                title="Ошибка загрузки записей"
                description="Не удалось загрузить список записей"
                action={
                  <MacOSButton onClick={() => window.location.reload()}>
                    <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                    Обновить
                  </MacOSButton>
                }
              />
            ) : appointments.length === 0 ? (
              <MacOSEmptyState
                type="calendar"
                title="Записи не найдены"
                description={appointmentsSearchTerm || appointmentFilterStatus || appointmentFilterDate || appointmentFilterDoctor 
                  ? 'Попробуйте изменить параметры поиска' 
                  : 'В системе пока нет записей'
                }
                action={
                  <MacOSButton onClick={handleCreateAppointment}>
                    <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                    Создать первую запись
                  </MacOSButton>
                }
              />
            ) : (
              <MacOSTable
                columns={[
                  { key: 'patient', title: 'Пациент', width: '25%' },
                  { key: 'doctor', title: 'Врач', width: '20%' },
                  { key: 'datetime', title: 'Дата и время', width: '20%' },
                  { key: 'status', title: 'Статус', width: '15%' },
                  { key: 'reason', title: 'Причина', width: '15%' },
                  { key: 'actions', title: 'Действия', width: '5%' }
                ]}
                data={appointments.map((appointment) => ({
                  id: appointment.id,
                  patient: (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div style={{ 
                            width: '32px', 
                            height: '32px', 
                            borderRadius: '50%', 
                            display: 'flex', 
                            alignItems: 'center', 
                            justifyContent: 'center', 
                            background: 'var(--mac-accent-blue)' 
                          }}>
                            <span style={{ 
                              color: 'white', 
                              fontSize: 'var(--mac-font-size-sm)', 
                              fontWeight: 'var(--mac-font-weight-medium)' 
                            }}>
                              {appointment.patientName.split(' ').map(n => n[0]).join('').toUpperCase()}
                            </span>
                          </div>
                          <div>
                            <p style={{ 
                              fontWeight: 'var(--mac-font-weight-medium)', 
                              color: 'var(--mac-text-primary)',
                              margin: 0
                            }}>{appointment.patientName}</p>
                            {appointment.phone && (
                              <p style={{ 
                                fontSize: 'var(--mac-font-size-sm)', 
                                color: 'var(--mac-text-secondary)',
                                margin: '4px 0 0 0'
                              }}>{appointment.phone}</p>
                            )}
                          </div>
                        </div>
                  ),
                  doctor: (
                        <div>
                          <p style={{ 
                            fontWeight: 'var(--mac-font-weight-medium)', 
                            color: 'var(--mac-text-primary)',
                            margin: 0
                          }}>{appointment.doctorName}</p>
                          <p style={{ 
                            fontSize: 'var(--mac-font-size-sm)', 
                            color: 'var(--mac-text-secondary)',
                            margin: '4px 0 0 0'
                          }}>{appointment.doctorSpecialization}</p>
                        </div>
                  ),
                  datetime: (
                        <div>
                          <p style={{ 
                            fontWeight: 'var(--mac-font-weight-medium)', 
                            color: 'var(--mac-text-primary)',
                            margin: 0
                          }}>
                            {new Date(appointment.appointmentDate).toLocaleDateString('ru-RU')}
                          </p>
                          <p style={{ 
                            fontSize: 'var(--mac-font-size-sm)', 
                            color: 'var(--mac-text-secondary)',
                            margin: '4px 0 0 0'
                          }}>
                            {appointment.appointmentTime} ({appointment.duration} мин)
                          </p>
                        </div>
                  ),
                  status: (
                    <MacOSBadge variant={getAppointmentStatusVariant(appointment.status)}>
                          {getAppointmentStatusLabel(appointment.status)}
                    </MacOSBadge>
                  ),
                  reason: (
                        <p style={{ 
                          fontSize: 'var(--mac-font-size-sm)', 
                          color: 'var(--mac-text-secondary)',
                          margin: 0
                        }}>
                          {appointment.reason.length > 50 
                            ? `${appointment.reason.substring(0, 50)}...` 
                            : appointment.reason
                          }
                        </p>
                  ),
                  actions: (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <MacOSButton
                        variant="outline"
                            onClick={() => handleEditAppointment(appointment)}
                            style={{ 
                          padding: '6px',
                          minWidth: 'auto',
                          width: '32px',
                          height: '32px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center'
                        }}
                            title="Редактировать"
                          >
                            <Edit style={{ width: '16px', height: '16px' }} />
                      </MacOSButton>
                      <MacOSButton
                        variant="outline"
                            onClick={() => handleDeleteAppointment(appointment)}
                            style={{ 
                          padding: '6px',
                          minWidth: 'auto',
                          width: '32px',
                          height: '32px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'var(--mac-error)',
                          borderColor: 'var(--mac-error)'
                        }}
                            title="Удалить"
                          >
                            <Trash2 style={{ width: '16px', height: '16px' }} />
                      </MacOSButton>
                        </div>
                  )
                }))}
              />
            )}
          </div>
        </MacOSCard>

        {/* Модальное окно записи */}
        {/* ✅ УЛУЧШЕНИЕ: Модальное окно записи с универсальным хуком */}
        <AppointmentModal
          isOpen={appointmentModal.isOpen}
          onClose={handleCloseAppointmentModal}
          appointment={appointmentModal.selectedItem}
          onSave={handleSaveAppointment}
          loading={appointmentModal.loading}
          doctors={doctors}
          patients={patients}
        />
      </div>
    );
  };

  const renderFinance = () => {
    const financialStats = getFinancialStats();
    const categoryStats = getCategoryStats();
    const dailyStats = getDailyStats(7);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Финансовая статистика */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>Общий доход</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-success)',
                  margin: '4px 0 0 0'
                }}>
                  {formatCurrency(financialStats.totalIncome)}
                </p>
              </div>
              <DollarSign style={{ width: '32px', height: '32px', color: 'var(--mac-success)' }} />
            </div>
          </MacOSCard>
          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>Общие расходы</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-error)',
                  margin: '4px 0 0 0'
                }}>
                  {formatCurrency(financialStats.totalExpense)}
                </p>
              </div>
              <CreditCard style={{ width: '32px', height: '32px', color: 'var(--mac-error)' }} />
            </div>
          </MacOSCard>
          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>Чистая прибыль</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: financialStats.netProfit >= 0 ? 'var(--mac-success)' : 'var(--mac-error)',
                  margin: '4px 0 0 0'
                }}>
                  {formatCurrency(financialStats.netProfit)}
                </p>
              </div>
              <Calendar style={{ 
                width: '32px', 
                height: '32px', 
                color: financialStats.netProfit >= 0 ? 'var(--mac-success)' : 'var(--mac-error)' 
              }} />
            </div>
          </MacOSCard>
          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>Всего транзакций</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-text-primary)',
                  margin: '4px 0 0 0'
                }}>
                  {financialStats.transactionCount}
                </p>
              </div>
              <Receipt style={{ width: '32px', height: '32px', color: 'var(--mac-accent)' }} />
            </div>
          </MacOSCard>
        </div>

        <MacOSCard 
          variant="default"
          style={{ padding: 0 }}
        >
          <div style={{ padding: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
            <h2 style={{ 
              fontSize: '20px', 
              fontWeight: '600', 
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>Финансовый учет</h2>
            <MacOSButton onClick={handleCreateTransaction}>
              <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Добавить транзакцию
            </MacOSButton>
          </div>
          
          {/* Поиск и фильтры */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
            <div style={{ flex: '1' }}>
              <MacOSInput
                type="text"
                placeholder="Поиск транзакций..."
                value={financeSearchTerm}
                onChange={(e) => setFinanceSearchTerm(e.target.value)}
                icon={Search}
                iconPosition="left"
                style={{
                  width: '100%',
                  paddingLeft: '40px',
                  paddingRight: '16px',
                  paddingTop: '8px',
                  paddingBottom: '8px',
                  borderRadius: 'var(--mac-radius-sm)',
                  border: '1px solid var(--mac-border)',
                  background: 'var(--mac-bg-primary)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-sm)',
                  outline: 'none',
                  transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                }}
              />
            </div>
            <MacOSSelect
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              options={[
                { value: '', label: 'Все типы' },
                { value: 'income', label: 'Доходы' },
                { value: 'expense', label: 'Расходы' }
              ]}
              style={{
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-sm)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                outline: 'none'
              }}
            />
            <MacOSSelect
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              options={[
                { value: '', label: 'Все категории' },
                { value: 'Консультация врача', label: 'Консультация врача' },
                { value: 'Диагностика', label: 'Диагностика' },
                { value: 'Лечение', label: 'Лечение' },
                { value: 'Анализы', label: 'Анализы' },
                { value: 'Процедуры', label: 'Процедуры' },
                { value: 'Зарплата персонала', label: 'Зарплата персонала' },
                { value: 'Коммунальные услуги', label: 'Коммунальные услуги' },
                { value: 'Медикаменты', label: 'Медикаменты' }
              ]}
              style={{
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-sm)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                outline: 'none'
              }}
            />
            <MacOSSelect
              value={filterDateRange}
              onChange={(e) => setFilterDateRange(e.target.value)}
              options={[
                { value: '', label: 'Все время' },
                { value: 'today', label: 'Сегодня' },
                { value: 'week', label: 'Неделя' },
                { value: 'month', label: 'Месяц' },
                { value: 'year', label: 'Год' }
              ]}
              style={{
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-sm)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                outline: 'none'
              }}
            />
            <MacOSSelect
              value={financeFilterStatus}
              onChange={(e) => setFinanceFilterStatus(e.target.value)}
              options={[
                { value: '', label: 'Все статусы' },
                { value: 'pending', label: 'Ожидает' },
                { value: 'completed', label: 'Завершена' },
                { value: 'cancelled', label: 'Отменена' },
                { value: 'refunded', label: 'Возврат' }
              ]}
              style={{
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-sm)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                outline: 'none'
              }}
            />
          </div>

          {/* Таблица транзакций */}
          <div style={{ overflowX: 'auto' }}>
            {financeLoading ? (
              <MacOSLoadingSkeleton type="table" count={5} />
            ) : financeError ? (
              <EmptyState
                type="error"
                title="Ошибка загрузки транзакций"
                description="Не удалось загрузить список транзакций"
                action={
                  <MacOSButton onClick={() => window.location.reload()}>
                    <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                    Обновить
                  </MacOSButton>
                }
              />
            ) : transactions.length === 0 ? (
              <EmptyState
                type="creditcard"
                title="Транзакции не найдены"
                description={financeSearchTerm || filterType || filterCategory || filterDateRange || financeFilterStatus 
                  ? 'Попробуйте изменить параметры поиска' 
                  : 'В системе пока нет транзакций'
                }
                action={
                  <MacOSButton onClick={handleCreateTransaction}>
                    <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                    Добавить первую транзакцию
                  </MacOSButton>
                }
              />
            ) : (
              <table style={{ width: '100%' }} role="table" aria-label="Таблица транзакций">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--mac-separator)' }}>
                    <th scope="col" style={{ textAlign: 'left', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', fontWeight: 'var(--mac-font-weight-medium)', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>Тип</th>
                    <th scope="col" style={{ textAlign: 'left', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', fontWeight: 'var(--mac-font-weight-medium)', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>Категория</th>
                    <th scope="col" style={{ textAlign: 'left', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', fontWeight: 'var(--mac-font-weight-medium)', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>Сумма</th>
                    <th scope="col" style={{ textAlign: 'left', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', fontWeight: 'var(--mac-font-weight-medium)', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>Описание</th>
                    <th scope="col" style={{ textAlign: 'left', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', fontWeight: 'var(--mac-font-weight-medium)', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>Дата</th>
                    <th scope="col" style={{ textAlign: 'left', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', fontWeight: 'var(--mac-font-weight-medium)', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>Статус</th>
                    <th scope="col" style={{ textAlign: 'left', padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', fontWeight: 'var(--mac-font-weight-medium)', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((transaction) => (
                    <tr
                      key={transaction.id}
                      style={{ borderBottom: '1px solid var(--mac-separator)', transition: 'all var(--mac-duration-normal) var(--mac-ease)' }}
                      onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)')}
                      onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                    >
                      <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                        <MacOSBadge variant={transaction.type === 'income' ? 'success' : 'error'}>
                          {getTransactionTypeLabel(transaction.type)}
                        </MacOSBadge>
                      </td>
                      <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                        <div>
                          <p style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)', margin: 0 }}>{transaction.category}</p>
                          {transaction.patientName && (
                            <p style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', margin: '4px 0 0 0' }}>{transaction.patientName}</p>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                        <p style={{ fontWeight: 'var(--mac-font-weight-medium)', color: transaction.type === 'income' ? 'var(--mac-success)' : 'var(--mac-danger)', margin: 0 }}>
                          {transaction.type === 'income' ? '+' : '-'}{formatCurrency(transaction.amount)}
                        </p>
                        <p style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', margin: '4px 0 0 0' }}>
                          {getPaymentMethodLabel(transaction.paymentMethod)}
                        </p>
                      </td>
                      <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                        <p style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', margin: 0 }}>
                          {transaction.description.length > 50 
                            ? `${transaction.description.substring(0, 50)}...` 
                            : transaction.description
                          }
                        </p>
                        {transaction.reference && (
                          <p style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', margin: '4px 0 0 0' }}>
                            {transaction.reference}
                          </p>
                        )}
                      </td>
                      <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                        {new Date(transaction.transactionDate).toLocaleDateString('ru-RU')}
                      </td>
                      <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                        <MacOSBadge variant={getTransactionStatusVariant(transaction.status)}>
                          {getTransactionStatusLabel(transaction.status)}
                        </MacOSBadge>
                      </td>
                      <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
                          <button 
                            onClick={() => handleEditTransaction(transaction)}
                            style={{ padding: 'var(--mac-spacing-2)', borderRadius: 'var(--mac-radius-sm)', backgroundColor: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--mac-text-secondary)', transition: 'all var(--mac-duration-normal) var(--mac-ease)' }}
                            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)')}
                            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                            title="Редактировать"
                          >
                            <Edit style={{ width: '16px', height: '16px' }} />
                          </button>
                          <button 
                            onClick={() => handleDeleteTransaction(transaction)}
                            style={{ padding: 'var(--mac-spacing-2)', borderRadius: 'var(--mac-radius-sm)', backgroundColor: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--mac-danger)', transition: 'all var(--mac-duration-normal) var(--mac-ease)' }}
                            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)')}
                            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                            title="Удалить"
                          >
                            <Trash2 style={{ width: '16px', height: '16px' }} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </MacOSCard>

        {/* Модальное окно транзакции */}
        {/* ✅ УЛУЧШЕНИЕ: Модальное окно финансов с универсальным хуком */}
        <FinanceModal
          isOpen={financeModal.isOpen}
          onClose={handleCloseFinanceModal}
          transaction={financeModal.selectedItem}
          onSave={handleSaveTransaction}
          loading={financeModal.loading}
          patients={patients}
          doctors={doctors}
        />
      </div>
    );
  };


  const renderSettings = () => {
    const settingsStats = getSettingsStats();

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Статистика настроек */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>Всего настроек</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-text-primary)',
                  margin: '4px 0 0 0'
                }}>{settingsStats.totalSettings}</p>
              </div>
              <Settings style={{ width: '32px', height: '32px', color: 'var(--mac-accent)' }} />
            </div>
          </MacOSCard>
          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>Настроено</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-success)',
                  margin: '4px 0 0 0'
                }}>{settingsStats.configuredSettings}</p>
              </div>
              <CheckCircle style={{ width: '32px', height: '32px', color: 'var(--mac-success)' }} />
            </div>
          </MacOSCard>
          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>Завершенность</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-info)',
                  margin: '4px 0 0 0'
                }}>{settingsStats.configurationPercentage}%</p>
              </div>
              <BarChart3 style={{ width: '32px', height: '32px', color: 'var(--mac-info)' }} />
            </div>
          </MacOSCard>
          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>Безопасность</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: settingsStats.securityEnabled ? 'var(--mac-success)' : 'var(--mac-warning)',
                  margin: '4px 0 0 0'
                }}>
                  {settingsStats.securityEnabled ? 'Вкл' : 'Выкл'}
                </p>
              </div>
              <Shield style={{ 
                width: '32px', 
                height: '32px', 
                color: settingsStats.securityEnabled ? 'var(--mac-success)' : 'var(--mac-warning)' 
              }} />
            </div>
          </MacOSCard>
        </div>

        {/* Кнопки действий */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <MacOSButton onClick={() => setSettingsSubTab('general')}>
              <Settings style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Общие настройки
            </MacOSButton>
            <MacOSButton onClick={() => setSettingsSubTab('security')}>
              <Shield style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Безопасность
            </MacOSButton>
            <MacOSButton onClick={() => setSettingsSubTab('theme')}>
              <Palette style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Цветовые схемы
            </MacOSButton>
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MacOSButton variant="outline" onClick={handleExportSettings}>
              <Download style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Экспорт
            </MacOSButton>
            <input
              type="file"
              accept=".json"
              onChange={(e) => e.target.files[0] && handleImportSettings(e.target.files[0])}
              style={{ display: 'none' }}
              id="import-settings"
            />
            <MacOSButton variant="outline" onClick={() => document.getElementById('import-settings').click()}>
              <Upload style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Импорт
            </MacOSButton>
            <MacOSButton variant="outline" onClick={handleResetSettings}>
              <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Сбросить
            </MacOSButton>
          </div>
        </div>

        {/* Общие настройки */}
        {settingsSubTab === 'general' && (
           <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              marginBottom: '20px',
              color: 'var(--mac-text-primary)'
            }}>
              Общие настройки системы
            </h3>
            <div style={{ display: 'grid', gap: '16px' }}>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  marginBottom: '8px',
                  color: 'var(--mac-text-primary)'
                }}>
                  Название клиники
                </label>
                <MacOSInput
                  value={settings?.clinicName || ''}
                  onChange={(e) => handleSaveSettings({ ...settings, clinicName: e.target.value })}
                  placeholder="Введите название клиники"
                />
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  marginBottom: '8px',
                  color: 'var(--mac-text-primary)'
                }}>
                  Адрес клиники
                </label>
                <MacOSTextarea
                  value={settings?.clinicAddress || ''}
                  onChange={(e) => handleSaveSettings({ ...settings, clinicAddress: e.target.value })}
                  placeholder="Введите адрес клиники"
                  rows={3}
                />
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  marginBottom: '8px',
                  color: 'var(--mac-text-primary)'
                }}>
                  Телефон клиники
                </label>
                <MacOSInput
                  value={settings?.clinicPhone || ''}
                  onChange={(e) => handleSaveSettings({ ...settings, clinicPhone: e.target.value })}
                  placeholder="Введите телефон клиники"
                />
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  marginBottom: '8px',
                  color: 'var(--mac-text-primary)'
                }}>
                  Email клиники
                </label>
                <MacOSInput
                  type="email"
                  value={settings?.clinicEmail || ''}
                  onChange={(e) => handleSaveSettings({ ...settings, clinicEmail: e.target.value })}
                  placeholder="Введите email клиники"
                />
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  marginBottom: '8px',
                  color: 'var(--mac-text-primary)'
                }}>
                  Часовой пояс
                </label>
                <MacOSSelect
                  value={settings?.timezone || 'Europe/Moscow'}
                  onChange={(e) => handleSaveSettings({ ...settings, timezone: e.target.value })}
                  options={[
                    { value: 'Europe/Moscow', label: 'Москва (UTC+3)' },
                    { value: 'Asia/Tashkent', label: 'Ташкент (UTC+5)' },
                    { value: 'Asia/Almaty', label: 'Алматы (UTC+6)' },
                    { value: 'Asia/Dubai', label: 'Дубай (UTC+4)' },
                    { value: 'UTC', label: 'UTC (UTC+0)' }
                  ]}
                  placeholder="Выберите часовой пояс"
                />
                <p style={{ 
                  fontSize: 'var(--mac-font-size-xs)', 
                  color: 'var(--mac-text-tertiary)',
                  marginTop: '4px',
                  marginBottom: 0
                }}>
                  Используется для расписания и онлайн-очереди
                </p>
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  marginBottom: '8px',
                  color: 'var(--mac-text-primary)'
                }}>
                  Логотип клиники
                </label>
                
                {/* Текущий логотип */}
                {(settings?.logoUrl || logoPreview) && (
                  <div style={{ marginBottom: '12px' }}>
                    <div style={{ 
                      width: '128px', 
                      height: '80px', 
                      border: '2px dashed var(--mac-border)', 
                      borderRadius: 'var(--mac-radius-md)',
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center', 
                      backgroundColor: 'var(--mac-bg-secondary)',
                      overflow: 'hidden'
                    }}>
                      <img
                        src={logoPreview || settings.logoUrl}
                        alt="Логотип клиники"
                        style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                      />
                    </div>
                    {logoPreview && (
                      <MacOSButton 
                        variant="outline" 
                        size="sm" 
                        onClick={resetLogo}
                        style={{ marginTop: '8px' }}
                      >
                        Отменить
                      </MacOSButton>
                    )}
                  </div>
                )}
                
                {/* Загрузка логотипа */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleLogoSelect}
                    style={{ display: 'none' }}
                    id="logo-upload"
                  />
                  <MacOSButton 
                    variant="outline"
                    onClick={() => document.getElementById('logo-upload').click()}
                  >
                    <Upload style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                    Выбрать файл
                  </MacOSButton>
                </div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-xs)', 
                  color: 'var(--mac-text-tertiary)',
                  marginTop: '4px',
                  marginBottom: 0
                }}>
                  Поддерживаются форматы: JPG, PNG, GIF. Максимальный размер: 5MB
                </p>
              </div>
            </div>
            <div style={{ marginTop: '24px', display: 'flex', gap: '12px' }}>
              <MacOSButton 
                onClick={() => handleSaveSettings(settings)}
                loading={settingsLoading}
              >
                Сохранить настройки
              </MacOSButton>
              <MacOSButton 
                variant="outline" 
                onClick={() => setSettings(prev => ({ ...prev, ...defaultSettings }))}
              >
                Сбросить к умолчанию
              </MacOSButton>
              <MacOSButton 
                variant="outline" 
                onClick={() => window.location.reload()}
              >
                <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                Обновить
              </MacOSButton>
            </div>
          </MacOSCard>
        )}

        {/* Настройки безопасности */}
        {settingsSubTab === 'security' && (
          <SecuritySettings
            settings={settings}
            onSave={handleSaveSettings}
            loading={settingsLoading}
          />
        )}

        {/* Настройки цветовых схем */}
        {settingsSubTab === 'theme' && (
          <ColorSchemeSelector />
        )}
      </div>
    );
  };

  const renderSecurity = () => {
    const securityStats = getSecurityStats();
    const securityTrends = getSecurityTrends();

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Статистика безопасности */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>Всего угроз</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-text-primary)',
                  margin: '4px 0 0 0'
                }}>{securityStats.totalThreats}</p>
                <div style={{ display: 'flex', alignItems: 'center', marginTop: '4px' }}>
                  {securityTrends.threats.change > 0 ? (
                    <TrendingUp style={{ width: '12px', height: '12px', marginRight: '4px', color: 'var(--mac-error)' }} />
                  ) : (
                    <TrendingDown style={{ width: '12px', height: '12px', marginRight: '4px', color: 'var(--mac-success)' }} />
                  )}
                  <span style={{ 
                    fontSize: '12px', 
                    color: securityTrends.threats.change > 0 ? 'var(--mac-error)' : 'var(--mac-success)' 
                  }}>
                    {Math.abs(securityTrends.threats.change).toFixed(1)}%
                  </span>
                </div>
              </div>
              <AlertTriangle style={{ width: '32px', height: '32px', color: 'var(--mac-warning)' }} />
            </div>
          </MacOSCard>

          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>Критические</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-error)',
                  margin: '4px 0 0 0'
                }}>{securityStats.criticalThreats}</p>
              </div>
              <XCircle style={{ width: '32px', height: '32px', color: 'var(--mac-error)' }} />
            </div>
          </MacOSCard>

          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>Заблокированные IP</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-text-primary)',
                  margin: '4px 0 0 0'
                }}>{securityStats.blockedIPs}</p>
                <div style={{ display: 'flex', alignItems: 'center', marginTop: '4px' }}>
                  {securityTrends.blockedIPs.change > 0 ? (
                    <TrendingUp style={{ width: '12px', height: '12px', marginRight: '4px', color: 'var(--mac-error)' }} />
                  ) : (
                    <TrendingDown style={{ width: '12px', height: '12px', marginRight: '4px', color: 'var(--mac-success)' }} />
                  )}
                  <span style={{ 
                    fontSize: '12px', 
                    color: securityTrends.blockedIPs.change > 0 ? 'var(--mac-error)' : 'var(--mac-success)' 
                  }}>
                    {Math.abs(securityTrends.blockedIPs.change).toFixed(1)}%
                  </span>
                </div>
              </div>
              <Globe style={{ width: '32px', height: '32px', color: 'var(--mac-info)' }} />
            </div>
          </MacOSCard>

          <MacOSCard 
            style={{ padding: '24px' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>Оценка безопасности</p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: securityStats.securityScore >= 80 ? 'var(--mac-success)' : 'var(--mac-warning)',
                  margin: '4px 0 0 0'
                }}>
                  {securityStats.securityScore}%
                </p>
                <div style={{ display: 'flex', alignItems: 'center', marginTop: '4px' }}>
                  {securityTrends.securityScore.change > 0 ? (
                    <TrendingUp style={{ width: '12px', height: '12px', marginRight: '4px', color: 'var(--mac-success)' }} />
                  ) : (
                    <TrendingDown style={{ width: '12px', height: '12px', marginRight: '4px', color: 'var(--mac-error)' }} />
                  )}
                  <span style={{ 
                    fontSize: '12px', 
                    color: securityTrends.securityScore.change > 0 ? 'var(--mac-success)' : 'var(--mac-error)' 
                  }}>
                    {Math.abs(securityTrends.securityScore.change).toFixed(1)}%
                  </span>
                </div>
              </div>
              <Shield style={{ width: '32px', height: '32px', color: securityStats.securityScore >= 80 ? 'var(--mac-success)' : 'var(--mac-warning)' }} />
            </div>
          </MacOSCard>
        </div>

        {/* Кнопки действий */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <MacOSButton onClick={() => loadSecurityData()}>
              <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Обновить данные
            </MacOSButton>
            <MacOSButton variant="outline" onClick={() => handleExportSecurityLogs('json')}>
              <Download style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Экспорт JSON
            </MacOSButton>
            <MacOSButton variant="outline" onClick={() => handleExportSecurityLogs('csv')}>
              <Download style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Экспорт CSV
            </MacOSButton>
          </div>
        </div>

        {/* Монитор безопасности */}
        <SecurityMonitor
          data={securityData}
          loading={securityLoading}
          onRefresh={loadSecurityData}
        />
      </div>
    );
  };

  if (isLoading) {
    return (
      <div style={{ 
        minHeight: '100vh', 
        backgroundColor: 'var(--mac-bg-primary)', 
        padding: '24px' 
      }}>
        <div style={{ 
          maxWidth: '1280px', 
          margin: '0 auto', 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '24px' 
        }}>
          <MacOSLoadingSkeleton style={{ height: '32px', width: '256px' }} />
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', 
            gap: '16px' 
          }}>
            {[...Array(6)].map((_, i) => (
              <MacOSLoadingSkeleton key={i} style={{ height: '96px' }} />
            ))}
          </div>
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
            gap: '24px' 
          }}>
            <MacOSLoadingSkeleton style={{ height: '320px' }} />
            <MacOSLoadingSkeleton style={{ height: '320px' }} />
          </div>
        </div>
      </div>
    );
  }

  const pageStyle = {
    background: 'var(--mac-bg-sidebar)',
    borderRight: '1px solid var(--mac-separator)',
    borderLeft: '1px solid var(--mac-separator)',
    borderTop: '1px solid var(--mac-separator)',
    borderBottom: '1px solid var(--mac-separator)',
    borderRadius: 'var(--mac-radius-lg)',
    boxShadow: 'var(--mac-shadow-md)',
    backdropFilter: 'var(--mac-blur-light)',
    WebkitBackdropFilter: 'var(--mac-blur-light)',
    padding: 0,
    margin: 0,
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    color: 'var(--mac-text-primary)',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)'
  };

  const containerStyle = {
    maxWidth: '1400px',
    margin: '0 auto'
  };

  return (
    <div style={pageStyle}>
      <div style={containerStyle}>
        
        {/* Навигация теперь через глобальный сайдбар в App.jsx */}

        {/* Мобильная навигация */}
        <MobileNavigation 
          sections={navigationSections}
          currentSection={current}
          onNavigate={(path) => navigate(path)}
        />

        {/* Основной контент */}
        <div style={{ 
          opacity: animationsStarted ? 1 : 0, 
          transform: animationsStarted ? 'translateY(0)' : 'translateY(20px)',
          transition: 'opacity 0.3s ease, transform 0.4s ease'
        }}>
          <div style={{ 
            padding: current === 'analytics' || current === 'clinic-management' || current === 'ai-imaging' || current === 'settings' || current === 'finance' || current === 'reports' || current === 'telegram-bot' || current === 'fcm-notifications' ? '0' : '12px'
        }}>
          {renderContent()}
          </div>
        </div>
        
        {/* Модальное окно горячих клавиш */}
        <HotkeysModal 
          isOpen={showHotkeysModal} 
          onClose={() => setShowHotkeysModal(false)} 
        />
      </div>
    </div>
  );
};

export default AdminPanel;
