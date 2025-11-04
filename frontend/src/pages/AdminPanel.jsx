// AdminPanel.jsx - macOS UI/UX Compliant - Updated: 2025-01-26
import React from 'react';
import { useState, useEffect, useCallback } from 'react';
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
  Palette
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
import AISettings from '../components/admin/AISettings';
import TelegramSettings from '../components/admin/TelegramSettings';
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
import TelegramBotManager from '../components/admin/TelegramBotManager';
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
import ReportsManager from '../components/admin/ReportsManager';
import SystemManagement from '../components/admin/SystemManagement';
import CloudPrintingManager from '../components/admin/CloudPrintingManager';
import MedicalEquipmentManager from '../components/admin/MedicalEquipmentManager';
import DynamicPricingManager from '../components/admin/DynamicPricingManager';
import BillingManager from '../components/admin/BillingManager';
import DiscountBenefitsManager from '../components/admin/DiscountBenefitsManager';
import { useAdminHotkeys } from '../hooks/useHotkeys';
import { HotkeysModal } from '../components/admin/HelpTooltip';
import { MobileNavigation, useScreenSize } from '../components/admin/MobileOptimization';
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
        console.error('Ошибка обновления:', error);
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
  } = useAdminData('/api/v1/admin/stats', {
    refreshInterval: 0, // Отключаем автообновление пока не исправим API
    enabled: false, // Отключаем запросы пока API не готов
    onError: (error) => {
      console.error('Ошибка загрузки статистики:', error);
    }
  });

  // Статистика по умолчанию (fallback)
  const defaultStats = {
    totalUsers: 1247,
    totalDoctors: 23,
    totalPatients: 8921,
    totalRevenue: 1250000,
    appointmentsToday: 156,
    pendingApprovals: 8
  };
  
  const stats = statsData || defaultStats;
  const isLoading = false; // Отключаем загрузку пока используем моковые данные
  
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
  
  // Состояние для генератора отчетов
  const [reportDateRange, setReportDateRange] = useState({ start: '', end: '' });
  const [selectedReportType, setSelectedReportType] = useState('');
  const [showReportGenerator, setShowReportGenerator] = useState(false);
  
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
  
  // Моковые данные для демонстрации
  const [recentActivities] = useState([
    {
      id: 1,
      type: 'user_registration',
      message: 'Новый пользователь зарегистрирован',
      user: 'Ахмедов А.',
      time: '2 минуты назад',
      status: 'success'
    },
    {
      id: 2,
      type: 'appointment_created',
      message: 'Создана новая запись',
      user: 'Иванова М.',
      time: '5 минут назад',
      status: 'info'
    },
    {
      id: 3,
      type: 'payment_received',
      message: 'Получен платеж',
      user: 'Петров В.',
      time: '12 минут назад',
      status: 'success'
    },
    {
      id: 4,
      type: 'system_alert',
      message: 'Системное предупреждение',
      user: 'Система',
      time: '1 час назад',
      status: 'warning'
    }
  ]);
  
  const [systemAlerts] = useState([
    {
      id: 1,
      type: 'warning',
      message: 'База данных требует оптимизации',
      priority: 'medium',
      time: '2 часа назад'
    },
    {
      id: 2,
      type: 'info',
      message: 'Обновление системы завершено',
      priority: 'low',
      time: '1 день назад'
    }
  ]);
  
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
  const handleGenerateReport = (reportConfig) => {
    return asyncAction.executeAction(
      () => generateReport(reportConfig),
      {
        loadingMessage: 'Генерация отчета...',
        successMessage: 'Отчет успешно сгенерирован',
        errorMessage: 'Ошибка при генерации отчета',
        onSuccess: () => setShowReportGenerator(false)
      }
    );
  };

  const handleDownloadReport = (reportId) => {
    return asyncAction.executeAction(
      () => downloadReport(reportId),
      {
        loadingMessage: 'Скачивание отчета...',
        successMessage: 'Отчет успешно скачан',
        errorMessage: 'Ошибка при скачивании отчета'
      }
    );
  };

  const handleDeleteReport = (reportId) => {
    if (window.confirm('Вы уверены, что хотите удалить этот отчет?')) {
      return asyncAction.executeAction(
        () => deleteReport(reportId),
        {
          loadingMessage: 'Удаление отчета...',
          successMessage: 'Отчет успешно удален',
          errorMessage: 'Ошибка при удалении отчета'
        }
      );
    }
  };

  const handleRegenerateReport = (reportId) => {
    return asyncAction.executeAction(
      () => regenerateReport(reportId),
      {
        loadingMessage: 'Повторная генерация отчета...',
        successMessage: 'Отчет успешно регенерирован',
        errorMessage: 'Ошибка при повторной генерации отчета'
      }
    );
  };

  const handleOpenReportGenerator = () => {
    setShowReportGenerator(true);
    // Устанавливаем период по умолчанию (последний месяц)
    const today = new Date();
    const lastMonth = new Date(today.getFullYear(), today.getMonth() - 1, today.getDate());
    setReportDateRange({
      start: lastMonth.toISOString().split('T')[0],
      end: today.toISOString().split('T')[0]
    });
  };

  // Обработчики для настроек
  const handleSaveSettings = async (settingsData) => {
    try {
      await saveSettings(settingsData);
    } catch (error) {
      console.error('Ошибка сохранения настроек:', error);
      throw error;
    }
  };

  const handleResetSettings = async () => {
    if (window.confirm('Вы уверены, что хотите сбросить все настройки к значениям по умолчанию?')) {
      try {
        await resetSettings();
      } catch (error) {
        console.error('Ошибка сброса настроек:', error);
        alert('Ошибка при сбросе настроек');
      }
    }
  };

  const handleExportSettings = async () => {
    try {
      await exportSettings();
    } catch (error) {
      console.error('Ошибка экспорта настроек:', error);
      alert('Ошибка при экспорте настроек');
    }
  };

  const handleImportSettings = async (file) => {
    try {
      await importSettings(file);
    } catch (error) {
      console.error('Ошибка импорта настроек:', error);
      alert('Ошибка при импорте настроек');
    }
  };

  // Обработчики для безопасности
  const handleBlockIP = async (ip, reason) => {
    try {
      await blockIP(ip, reason);
    } catch (error) {
      console.error('Ошибка блокировки IP:', error);
      alert('Ошибка при блокировке IP адреса');
    }
  };

  const handleUnblockIP = async (ipId) => {
    try {
      await unblockIP(ipId);
    } catch (error) {
      console.error('Ошибка разблокировки IP:', error);
      alert('Ошибка при разблокировке IP адреса');
    }
  };

  const handleTerminateSession = async (sessionId) => {
    try {
      await terminateSession(sessionId);
    } catch (error) {
      console.error('Ошибка завершения сессии:', error);
      alert('Ошибка при завершении сессии');
    }
  };

  const handleTerminateAllOtherSessions = async () => {
    if (window.confirm('Вы уверены, что хотите завершить все остальные сессии?')) {
      try {
        await terminateAllOtherSessions();
      } catch (error) {
        console.error('Ошибка завершения сессий:', error);
        alert('Ошибка при завершении сессий');
      }
    }
  };

  const handleUpdateThreatStatus = async (threatId, newStatus) => {
    try {
      await updateThreatStatus(threatId, newStatus);
    } catch (error) {
      console.error('Ошибка обновления статуса угрозы:', error);
      alert('Ошибка при обновлении статуса угрозы');
    }
  };

  const handleExportSecurityLogs = async (format = 'json') => {
    try {
      await exportSecurityLogs(format);
    } catch (error) {
      console.error('Ошибка экспорта логов:', error);
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
        console.error('Ошибка удаления пользователя:', error);
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
      console.error('Ошибка сохранения пользователя:', error);
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
      Nurse: 'Медсестра',
      Receptionist: 'Регистратор',
      Patient: 'Пациент'
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
    if (window.confirm(`Вы уверены, что хотите удалить врача "${doctor.name}"?`)) {
      try {
        await deleteDoctor(doctor.id);
      } catch (error) {
        console.error('Ошибка удаления врача:', error);
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
      console.error('Ошибка сохранения врача:', error);
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
      general: 'Общее',
      surgery: 'Хирургия',
      pediatrics: 'Педиатрия',
      neurology: 'Неврология'
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
        console.error('Ошибка удаления пациента:', error);
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
      console.error('Ошибка сохранения пациента:', error);
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
        console.error('Ошибка удаления записи:', error);
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
      console.error('Ошибка сохранения записи:', error);
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
      pending: 'Ожидает',
      confirmed: 'Подтверждена',
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
      confirmed: 'var(--mac-info)',
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
      confirmed: 'info',
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
        console.error('Ошибка удаления транзакции:', error);
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
      console.error('Ошибка сохранения транзакции:', error);
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
        { to: '/admin/wait-time-analytics', label: 'Время ожидания', icon: Clock },
        { to: '/admin/ai-analytics', label: 'AI Аналитика', icon: Brain },
        { to: '/admin/webhooks', label: 'Webhook\'и', icon: Globe },
        { to: '/admin/reports', label: 'Отчеты', icon: FileText },
        { to: '/admin/system', label: 'Система', icon: Server },
        { to: '/admin/cloud-printing', label: 'Облачная печать', icon: Printer },
              { to: '/admin/medical-equipment', label: 'Медицинское оборудование', icon: Stethoscope },
              { to: '/admin/dynamic-pricing', label: 'Динамическое ценообразование', icon: Package },
              { to: '/admin/billing', label: 'Биллинг и счета', icon: Receipt },
              { to: '/admin/discount-benefits', label: 'Скидки и льготы', icon: Percent },
              { to: '/admin/graphql-explorer', label: 'GraphQL API', icon: Database }
      ]
    },
    {
      title: 'Управление',
      items: [
        { to: '/admin/users', label: 'Пользователи', icon: Users },
        { to: '/admin/doctors', label: 'Врачи', icon: UserPlus },
        { to: '/admin/services', label: 'Услуги', icon: Package },
        { to: '/admin/patients', label: 'Пациенты', icon: Users },
        { to: '/admin/appointments', label: 'Записи', icon: Calendar },
        { to: '/admin/all-free', label: 'Заявки All Free', icon: AlertTriangle },
        { to: '/admin/benefit-settings', label: 'Настройки льгот', icon: Settings },
        { to: '/admin/wizard-settings', label: 'Настройки мастера', icon: Monitor },
        { to: '/admin/payment-providers', label: 'Платежные провайдеры', icon: CreditCard }
      ]
    },
    {
      title: 'Система',
      items: [
        { to: '/admin/clinic-management', label: 'Управление клиникой', icon: Building2 },
        { to: '/admin/clinic-settings', label: 'Настройки клиники', icon: Settings },
        { to: '/admin/queue-settings', label: 'Настройки очередей', icon: Clock },
        { to: '/admin/queue-limits', label: 'Лимиты очередей', icon: Shield },
        { to: '/admin/ai-imaging', label: 'AI Анализ изображений', icon: Brain },
        { to: '/admin/treatment-recommendations', label: 'AI Рекомендации лечения', icon: Heart },
        { to: '/admin/drug-interactions', label: 'AI Проверка взаимодействий', icon: Pill },
        { to: '/admin/risk-assessment', label: 'AI Оценка рисков', icon: Shield },
        { to: '/admin/voice-to-text', label: 'AI Голосовой ввод', icon: Mic },
        { to: '/admin/smart-scheduling', label: 'AI Умное планирование', icon: Calendar },
        { to: '/admin/quality-control', label: 'AI Контроль качества', icon: ClipboardCheck },
        { to: '/admin/analytics-insights', label: 'AI Аналитические инсайты', icon: TrendingUp },
        { to: '/admin/ai-settings', label: 'AI настройки', icon: Brain },
        { to: '/admin/telegram-bot', label: 'Telegram бот', icon: Bot },
        { to: '/admin/fcm-notifications', label: 'FCM Push уведомления', icon: Bell },
        { to: '/admin/phone-verification', label: 'Верификация телефонов', icon: Phone },
                { to: '/admin/user-data-transfer', label: 'Передача данных пользователей', icon: Users },
                { to: '/admin/group-permissions', label: 'Разрешения групп', icon: Shield },
                { to: '/admin/user-export', label: 'Экспорт пользователей', icon: Download },
                { to: '/admin/registrar-notifications', label: 'Уведомления регистратуры', icon: Bell },
        { to: '/admin/telegram-settings', label: 'Telegram', icon: MessageSquare },
        { to: '/admin/display-settings', label: 'Управление табло', icon: Monitor },
        { to: '/admin/activation', label: 'Система активации', icon: Key },
        { to: '/admin/finance', label: 'Финансы', icon: CreditCard },
        { to: '/admin/reports', label: 'Отчеты', icon: FileText },
        { to: '/admin/settings', label: 'Настройки', icon: Settings },
        { to: '/admin/security', label: 'Безопасность', icon: Shield }
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

  // Вычисляем текущую вкладку из URL параметров
  const searchParams = new URLSearchParams(location.search);
  const current = searchParams.get('section') || 'dashboard';

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
              title="Total Users"
              value={stats.totalUsers}
              icon={Users}
              color="blue"
              trend="+5.2%"
              trendType="positive"
              loading={isLoading}
            />
        
            <MacOSStatCard
              title="Doctors"
              value={stats.totalDoctors}
              icon={Stethoscope}
              color="green"
              trend="+2"
              trendType="positive"
              loading={isLoading}
            />
        
            <MacOSStatCard
              title="Patients"
              value={stats.totalPatients}
              icon={Users}
              color="purple"
              trend="+12.3%"
              trendType="positive"
              loading={isLoading}
            />
            
            <MacOSStatCard
              title="Revenue"
              value={formatCurrency(stats.totalRevenue)}
              icon={TrendingUp}
              color="green"
              trend="+8.7%"
              trendType="positive"
              loading={isLoading}
            />
            
            <MacOSStatCard
              title="Today's Appointments"
              value={stats.appointmentsToday}
              icon={Calendar}
              color="orange"
              trend="+15"
              trendType="positive"
              loading={isLoading}
            />
            
            <MacOSStatCard
              title="Pending Approvals"
              value={stats.pendingApprovals}
              icon={Clock}
              color="red"
              trend="-2"
              trendType="negative"
              loading={isLoading}
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
                <p style={{ color: 'var(--mac-text-secondary)' }}>График активности</p>
              </div>
            </div>
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
              { value: 'Nurse', label: 'Медсестра' },
              { value: 'Receptionist', label: 'Регистратор' },
              { value: 'Patient', label: 'Пациент' }
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
    const [isLoading, setIsLoading] = useState(false);
    const [hasData, setHasData] = useState(true); // Показываем данные по умолчанию

    const handleFilterChange = (filterType, value) => {
      setAnalyticsFilters(prev => ({
        ...prev,
        [filterType]: value
      }));
    };

    const applyFilters = () => {
      setIsLoading(true);
      // Симуляция загрузки данных
      setTimeout(() => {
        setIsLoading(false);
        setHasData(true); // Всегда показываем данные для демо
      }, 1000);
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
                // Экспорт данных в CSV
                const csvData = "Период,Записи,Доходы,Пациенты\nСегодня,1,247,₽2.4M,892\nНеделя,8,729,₽16.8M,6,244\nМесяц,37,416,₽74.8M,29,792";
                const blob = new Blob([csvData], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'analytics-export.csv';
                a.click();
                window.URL.revokeObjectURL(url);
              }}
            >
              <Download style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Экспорт
            </MacOSButton>
            <MacOSButton
              onClick={() => {
                // Открыть генератор отчетов
                setActiveSection('reports');
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
                { value: 'ivanov', label: 'Иванов И.И.' },
                { value: 'petrov', label: 'Петров П.П.' }
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
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px', 
          marginBottom: '24px' 
        }}>
          <MacOSStatCard
            title="Всего записей"
            value="1,247"
            icon={Calendar}
            color="var(--mac-accent-blue)"
            trend="+12% за месяц"
            trendColor="var(--mac-accent-blue)"
          />
          
          <MacOSStatCard
            title="Доходы"
            value="₽2.4M"
            icon={CreditCard}
            color="var(--mac-success)"
            trend="+8% за месяц"
            trendColor="var(--mac-success)"
          />
          
          <MacOSStatCard
            title="Пациенты"
            value="892"
            icon={Users}
            color="var(--mac-info)"
            trend="+15% за месяц"
            trendColor="var(--mac-info)"
          />
          
          <MacOSStatCard
            title="Средний чек"
            value="₽1,925"
            icon={TrendingUp}
            color="var(--mac-warning)"
            trend="+5% за месяц"
            trendColor="var(--mac-warning)"
          />
        </div>

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
            {isLoading ? (
              <MacOSLoadingSkeleton height="256px" />
            ) : (
            <div style={{ 
              height: '256px', 
              backgroundColor: 'var(--mac-bg-tertiary)', 
              borderRadius: 'var(--mac-radius-md)', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center' 
            }}>
              <p style={{ color: 'var(--mac-text-secondary)' }}>График записей по дням</p>
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
            }}>Доходы по отделениям</h3>
            {isLoading ? (
              <MacOSLoadingSkeleton height="256px" />
            ) : (
            <div style={{ 
              height: '256px', 
              backgroundColor: 'var(--mac-bg-tertiary)', 
              borderRadius: 'var(--mac-radius-md)', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center' 
            }}>
              <p style={{ color: 'var(--mac-text-secondary)' }}>Круговая диаграмма доходов</p>
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
          
          {isLoading ? (
            <MacOSLoadingSkeleton height="200px" />
          ) : !hasData ? (
            <MacOSEmptyState
              icon={Users}
              title="Нет данных о врачах"
              description="Загрузите данные для отображения статистики по врачам"
            />
          ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {[
              { name: 'Иванов И.И.', department: 'Кардиология', patients: 156, revenue: '₽312,000' },
              { name: 'Петров П.П.', department: 'Дерматология', patients: 134, revenue: '₽268,000' },
              { name: 'Сидоров С.С.', department: 'Стоматология', patients: 98, revenue: '₽196,000' },
              { name: 'Козлов К.К.', department: 'Общее', patients: 87, revenue: '₽174,000' }
            ].map((doctor, index) => (
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
                    }}>{doctor.name}</p>
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)',
                      margin: 0
                    }}>{doctor.department}</p>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <p style={{ 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)',
                    margin: 0
                  }}>{doctor.patients} пациентов</p>
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
        return <AnalyticsSection />;
      case 'users':
        return renderUsers();
      case 'doctors':
        return renderDoctors();
      case 'patients':
        return renderPatients();
      case 'appointments':
        return renderAppointments();
      case 'all-free':
        return <AllFreeApproval />;
      case 'benefit-settings':
        return <BenefitSettings />;
      case 'wizard-settings':
        return <WizardSettings />;
      case 'payment-providers':
        return <PaymentProviderSettings />;
      case 'finance':
        return renderFinance();
      case 'reports':
        return renderReports();
      case 'clinic-management':
        return <ClinicManagement />;
      case 'clinic-settings':
        return <ClinicSettings />;
      case 'queue-settings':
        return <QueueSettings />;
      case 'queue-limits':
        return <QueueLimitsManager />;
      case 'ai-imaging':
        return <MedicalImageAnalyzer />;
      case 'treatment-recommendations':
        return <TreatmentRecommendations />;
      case 'drug-interactions':
        return <DrugInteractionChecker />;
      case 'risk-assessment':
        return <RiskAssessment />;
      case 'voice-to-text':
        return <VoiceToText />;
        case 'smart-scheduling':
          return <SmartScheduling />;
        case 'quality-control':
          return <QualityControl />;
      case 'analytics-insights':
        return <AnalyticsInsights />;
      case 'telegram-bot':
        return <TelegramBotManager />;
      case 'fcm-notifications':
        return <FCMManager />;
      case 'phone-verification':
        return <PhoneVerificationManager />;
      case 'user-data-transfer':
        return <UserDataTransferManager />;
      case 'group-permissions':
        return <GroupPermissionsManager />;
      case 'user-export':
        return <UserExportManager />;
      case 'registrar-notifications':
        return <RegistrarNotificationManager />;
      case 'wait-time-analytics':
        return <WaitTimeAnalytics />;
      case 'ai-analytics':
        return <AIAnalytics />;
      case 'webhooks':
        return <WebhookManager />;
      case 'system':
        return <SystemManagement />;
      case 'cloud-printing':
        return <CloudPrintingManager />;
        case 'medical-equipment':
          return <MedicalEquipmentManager />;
        case 'dynamic-pricing':
          return <DynamicPricingManager />;
        case 'billing':
          return <BillingManager />;
        case 'discount-benefits':
          return <DiscountBenefitsManager />;
        case 'graphql-explorer':
          return <GraphQLExplorer />;
      case 'services':
        return <ServiceCatalog />;
      case 'ai-settings':
        return <AISettings />;
      case 'telegram-settings':
        return <TelegramSettings />;
      case 'display-settings':
        return <DisplayBoardSettings />;
      case 'activation':
        return <ActivationSystem />;
      case 'settings':
        return renderSettings();
      case 'security':
        return renderSecurity();
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
              { value: 'general', label: 'Общее' },
              { value: 'surgery', label: 'Хирургия' },
              { value: 'pediatrics', label: 'Педиатрия' },
              { value: 'neurology', label: 'Неврология' }
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
                            {doctor.name.split(' ').map(n => n[0]).join('').toUpperCase()}
                          </span>
                        </div>
                        <div>
                          <p style={{ 
                            fontWeight: 'var(--mac-font-weight-medium)', 
                            color: 'var(--mac-text-primary)',
                            fontSize: 'var(--mac-font-size-sm)',
                            margin: 0
                          }}>{doctor.name}</p>
                          <p style={{ 
                            fontSize: '12px', 
                            color: 'var(--mac-text-secondary)',
                            margin: '4px 0 0 0'
                          }}>{doctor.email}</p>
                          {doctor.phone && (
                            <p style={{ 
                              fontSize: '11px', 
                              color: 'var(--mac-text-tertiary)',
                              margin: '2px 0 0 0'
                            }}>{doctor.phone}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <MacOSBadge variant="info">
                        {doctor.specialization}
                      </MacOSBadge>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <MacOSBadge variant="success">
                        {getDepartmentLabel(doctor.department)}
                      </MacOSBadge>
                    </td>
                    <td style={{ 
                      padding: '12px 16px', 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)' 
                    }}>
                      {doctor.experience} лет
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <MacOSBadge 
                        variant={doctor.status === 'active' ? 'success' : doctor.status === 'inactive' ? 'warning' : 'info'}
                      >
                        {getDoctorStatusLabel(doctor.status)}
                      </MacOSBadge>
                    </td>
                    <td style={{ 
                      padding: '12px 16px', 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)' 
                    }}>
                      {doctor.patientsCount} пациентов
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
                  label: doctor.name
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

  const renderReports = () => {
    const reportStats = getReportStats();
    const reportTypes = getReportTypes();

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Статистика отчетов */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', 
          gap: '16px' 
        }}>
          <MacOSStatCard
            title="Всего отчетов"
            value={reportStats.total}
            icon={FileText}
            color="blue"
          />
          <MacOSStatCard
            title="Завершено"
            value={reportStats.completed}
            icon={CheckCircle}
            color="green"
          />
          <MacOSStatCard
            title="Генерируется"
            value={reportStats.generating}
            icon={Clock}
            color="orange"
          />
          <MacOSStatCard
            title="Ошибки"
            value={reportStats.failed}
            icon={AlertCircle}
            color="red"
          />
          <MacOSStatCard
            title="Скачиваний"
            value={reportStats.totalDownloads}
            icon={Download}
            color="blue"
          />
        </div>

        {/* Кнопки действий */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <MacOSButton variant="primary" onClick={handleOpenReportGenerator}>
              <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Создать отчет
            </MacOSButton>
            <MacOSButton variant="outline" onClick={() => window.location.reload()}>
              <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Обновить
            </MacOSButton>
          </div>
        </div>

        {/* Аналитическая панель */}
           <MacOSCard style={{ padding: '24px' }}>
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            marginBottom: '16px',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
            Аналитическая панель
          </h3>
          <AnalyticsDashboard 
            data={{}}
            loading={false}
            dateRange={reportDateRange}
          />
        </MacOSCard>

        {/* Список отчетов */}
           <MacOSCard style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
            <h2 style={{ 
              fontSize: 'var(--mac-font-size-xl)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>Отчеты</h2>
          </div>
          
          {/* Поиск и фильтры */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
            <div style={{ flex: 1, position: 'relative' }}>
              <Search style={{ 
                position: 'absolute', 
                left: '12px', 
                top: '50%', 
                transform: 'translateY(-50%)', 
                width: '16px', 
                height: '16px', 
                color: 'var(--mac-text-tertiary)' 
              }} />
              <MacOSInput
                type="text"
                placeholder="Поиск отчетов..."
                value={reportsSearchTerm}
                onChange={(e) => setReportsSearchTerm(e.target.value)}
                icon={Search}
                iconPosition="left"
                style={{ 
                  width: '100%',
                  paddingLeft: '40px',
                  paddingRight: '16px',
                  paddingTop: '8px',
                  paddingBottom: '8px',
                  borderRadius: 'var(--mac-radius-md)',
                  border: '1px solid var(--mac-border)', 
                  background: 'var(--mac-bg-primary)', 
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)',
                  transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                }}
              />
            </div>
            <MacOSSelect
              value={reportFilterType}
              onChange={(e) => setReportFilterType(e.target.value)}
              options={[
                { value: '', label: 'Все типы' },
                ...reportTypes.map(type => ({
                  value: type.value,
                  label: type.label
                }))
              ]}
              style={{ 
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-md)',
                border: '1px solid var(--mac-border)', 
                background: 'var(--mac-bg-primary)', 
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
            />
            <MacOSSelect
              value={reportFilterStatus}
              onChange={(e) => setReportFilterStatus(e.target.value)}
              options={[
                { value: '', label: 'Все статусы' },
                { value: 'completed', label: 'Завершен' },
                { value: 'generating', label: 'Генерируется' },
                { value: 'failed', label: 'Ошибка' },
                { value: 'pending', label: 'Ожидает' }
              ]}
              style={{ 
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-md)',
                border: '1px solid var(--mac-border)', 
                background: 'var(--mac-bg-primary)', 
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
            />
            <MacOSSelect
              value={reportFilterDateRange}
              onChange={(e) => setReportFilterDateRange(e.target.value)}
              options={[
                { value: '', label: 'Все время' },
                { value: 'today', label: 'Сегодня' },
                { value: 'week', label: 'Неделя' },
                { value: 'month', label: 'Месяц' }
              ]}
              style={{ 
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-md)',
                border: '1px solid var(--mac-border)', 
                background: 'var(--mac-bg-primary)', 
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
            />
          </div>

          {/* Таблица отчетов */}
          <div style={{ overflowX: 'auto' }}>
            {reportsLoading ? (
              <MacOSLoadingSkeleton type="table" count={5} />
            ) : reportsError ? (
              <EmptyState
                type="error"
                title="Ошибка загрузки отчетов"
                description="Не удалось загрузить список отчетов"
                action={
                  <MacOSButton onClick={() => window.location.reload()}>
                    <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                    Обновить
                  </MacOSButton>
                }
              />
            ) : reports.length === 0 ? (
              <EmptyState
                type="filetext"
                title="Отчеты не найдены"
                description={reportsSearchTerm || reportFilterType || reportFilterStatus || reportFilterDateRange 
                  ? 'Попробуйте изменить параметры поиска' 
                  : 'В системе пока нет отчетов'
                }
                action={
                  <MacOSButton onClick={handleOpenReportGenerator}>
                    <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                    Создать первый отчет
                  </MacOSButton>
                }
              />
            ) : (
              <table style={{ width: '100%' }} role="table" aria-label="Таблица отчетов">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--mac-separator)' }}>
                    <th scope="col" style={{ 
                      textAlign: 'left', 
                      padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', 
                      fontWeight: 'var(--mac-font-weight-semibold)',
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-secondary)'
                    }}>Название</th>
                    <th scope="col" style={{ 
                      textAlign: 'left', 
                      padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', 
                      fontWeight: 'var(--mac-font-weight-semibold)',
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-secondary)'
                    }}>Тип</th>
                    <th scope="col" style={{ 
                      textAlign: 'left', 
                      padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', 
                      fontWeight: 'var(--mac-font-weight-semibold)',
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-secondary)'
                    }}>Статус</th>
                    <th scope="col" style={{ 
                      textAlign: 'left', 
                      padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', 
                      fontWeight: 'var(--mac-font-weight-semibold)',
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-secondary)'
                    }}>Период</th>
                    <th scope="col" style={{ 
                      textAlign: 'left', 
                      padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', 
                      fontWeight: 'var(--mac-font-weight-semibold)',
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-secondary)'
                    }}>Размер</th>
                    <th scope="col" style={{ 
                      textAlign: 'left', 
                      padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', 
                      fontWeight: 'var(--mac-font-weight-semibold)',
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-secondary)'
                    }}>Скачиваний</th>
                    <th scope="col" style={{ 
                      textAlign: 'left', 
                      padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', 
                      fontWeight: 'var(--mac-font-weight-semibold)',
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-secondary)'
                    }}>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.map((report) => (
                    <tr 
                      key={report.id} 
                      style={{ 
                        borderBottom: '1px solid var(--mac-separator)',
                        transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                    >
                      <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                        <div>
                          <p style={{ 
                            fontWeight: 'var(--mac-font-weight-medium)', 
                            fontSize: 'var(--mac-font-size-base)',
                            color: 'var(--mac-text-primary)',
                            margin: 0
                          }}>{report.name}</p>
                          <p style={{ 
                            fontSize: 'var(--mac-font-size-sm)', 
                            color: 'var(--mac-text-secondary)',
                            margin: '4px 0 0 0'
                          }}>{report.description}</p>
                        </div>
                      </td>
                      <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                        <MacOSBadge variant="info">
                          {getReportTypeLabel(report.type)}
                        </MacOSBadge>
                      </td>
                      <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                        <MacOSBadge variant={getStatusVariant(report.status)}>
                          {getStatusLabel(report.status)}
                        </MacOSBadge>
                      </td>
                      <td style={{ 
                        padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', 
                        fontSize: 'var(--mac-font-size-sm)', 
                        color: 'var(--mac-text-secondary)' 
                      }}>
                        {formatDateRange(report.dateRange)}
                      </td>
                      <td style={{ 
                        padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', 
                        fontSize: 'var(--mac-font-size-sm)', 
                        color: 'var(--mac-text-secondary)' 
                      }}>
                        {report.fileSize || '-'}
                      </td>
                      <td style={{ 
                        padding: 'var(--mac-spacing-3) var(--mac-spacing-4)', 
                        fontSize: 'var(--mac-font-size-sm)', 
                        color: 'var(--mac-text-secondary)' 
                      }}>
                        {report.downloadCount}
                      </td>
                      <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
                          {report.status === 'completed' && (
                            <button 
                              onClick={() => handleDownloadReport(report.id)}
                              style={{ 
                                padding: 'var(--mac-spacing-2)',
                                borderRadius: 'var(--mac-radius-sm)',
                                backgroundColor: 'transparent',
                                border: 'none',
                                cursor: 'pointer',
                                color: 'var(--mac-text-secondary)',
                                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                              }}
                              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)'}
                              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                              title="Скачать"
                            >
                              <Download style={{ width: '16px', height: '16px' }} />
                            </button>
                          )}
                          {report.status === 'failed' && (
                            <button 
                              onClick={() => handleRegenerateReport(report.id)}
                              style={{ 
                                padding: 'var(--mac-spacing-2)',
                                borderRadius: 'var(--mac-radius-sm)',
                                backgroundColor: 'transparent',
                                border: 'none',
                                cursor: 'pointer',
                                color: 'var(--mac-warning)',
                                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                              }}
                              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)'}
                              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                              title="Повторить генерацию"
                            >
                              <RefreshCw style={{ width: '16px', height: '16px' }} />
                            </button>
                          )}
                          <button 
                            onClick={() => handleDeleteReport(report.id)}
                            style={{ 
                              padding: 'var(--mac-spacing-2)',
                              borderRadius: 'var(--mac-radius-sm)',
                              backgroundColor: 'transparent',
                              border: 'none',
                              cursor: 'pointer',
                              color: 'var(--mac-danger)',
                              transition: 'all var(--mac-duration-normal) var(--mac-ease)'
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

        {/* Генератор отчетов */}
        {showReportGenerator && (
           <MacOSCard style={{ padding: '24px' }}>
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'space-between', 
              marginBottom: '24px' 
            }}>
              <h2 style={{ 
                fontSize: 'var(--mac-font-size-xl)', 
                fontWeight: 'var(--mac-font-weight-semibold)', 
                color: 'var(--mac-text-primary)',
                margin: 0
              }}>
                Генератор отчетов
              </h2>
              <button
                onClick={() => setShowReportGenerator(false)}
                style={{ 
                  padding: 'var(--mac-spacing-2)',
                  borderRadius: 'var(--mac-radius-lg)',
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--mac-text-secondary)',
                  transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                <X style={{ width: '20px', height: '20px' }} />
              </button>
            </div>
            <ReportGenerator
              onGenerateReport={handleGenerateReport}
              loading={reportsLoading}
              reportTypes={reportTypes.map(t => t.value)}
              dateRange={reportDateRange}
              onDateRangeChange={setReportDateRange}
              selectedReportType={selectedReportType}
              onReportTypeChange={setSelectedReportType}
            />
          </MacOSCard>
        )}
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
            padding: current === 'analytics' || current === 'payment-providers' || current === 'clinic-management' || current === 'clinic-settings' || current === 'queue-settings' || current === 'queue-limits' || current === 'ai-imaging' || current === 'treatment-recommendations' ? '0' : '12px'
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
