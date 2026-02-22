// AdminPanel.jsx - macOS UI/UX Compliant - Updated: 2025-01-26
import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {





  MacOSStatCard,

  MacOSTable,
  MacOSInput,
  MacOSSelect,






  MacOSEmptyState,
  MacOSLoadingSkeleton,


  MacOSButton,
  MacOSBadge,
  Card as MacOSCard } from
'../components/ui/macos';

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

  Database,
  Users,
  UserPlus,
  Calendar,
  AlertTriangle,
  Settings,

  CreditCard,
  Building2,





  Bot,
  Bell,
  Phone,
  Download,

  Key,
  CheckCircle,
  Activity,
  Eye,
  Plus,
  Search,
  RefreshCw,
  Edit,
  Trash2,

  DollarSign,
  AlertCircle,





  FolderTree } from
'lucide-react';

// ✅ УЛУЧШЕНИЕ: Универсальные хуки для устранения дублирования
import { useModal } from '../hooks/useModal.jsx';
import useAsyncAction from '../hooks/useAsyncAction';

// ✅ УЛУЧШЕНИЕ: Унифицированные компоненты (будут использованы в следующих итерациях)
// import UnifiedLayout from '../components/layout/UnifiedLayout';
// import { MedicalCard, MetricCard, MedicalTable } from '../components/medical';
// import AdminSection from '../components/admin/AdminSection';


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

import DoctorModal from '../components/admin/DoctorModal';
import PatientModal from '../components/admin/PatientModal';
import AppointmentModal from '../components/admin/AppointmentModal';
import FinanceModal from '../components/admin/FinanceModal';

import AnalyticsDashboard from '../components/admin/AnalyticsDashboard';


import ServiceCatalog from '../components/admin/ServiceCatalog';
// ⭐ DEPRECATED: DepartmentManagement replaced by QueueProfilesManager (SSOT)
// import DepartmentManagement from '../components/admin/DepartmentManagement';


import ActivationSystem from '../components/admin/ActivationSystem';



import AllFreeApproval from '../components/admin/AllFreeApproval';











import AnalyticsInsights from '../components/ai/AnalyticsInsights';
import UnifiedTelegramManagement from '../components/admin/UnifiedTelegramManagement';
import UnifiedSettings from '../components/admin/UnifiedSettings';
import UnifiedFinance from '../components/admin/UnifiedFinance';
import UnifiedNotifications from '../components/admin/UnifiedNotifications';
import UnifiedAITools from '../components/admin/UnifiedAITools';
import UnifiedUserManagement from '../components/admin/UnifiedUserManagement';

import PhoneVerificationManager from '../components/admin/PhoneVerificationManager';




import ClinicManagement from '../components/admin/ClinicManagement';




import WaitTimeAnalytics from '../components/analytics/WaitTimeAnalytics';
import AIAnalytics from '../components/analytics/AIAnalytics';
import GraphQLExplorer from '../components/admin/GraphQLExplorer';
import WebhookManager from '../components/admin/WebhookManager';
import UnifiedReports from '../components/admin/UnifiedReports';
import SystemManagement from '../components/admin/SystemManagement';
import CloudPrintingManager from '../components/admin/CloudPrintingManager';
import MedicalEquipmentManager from '../components/admin/MedicalEquipmentManager';



import QueueProfilesManager from '../components/admin/QueueProfilesManager'; // ⭐ SSOT: Dynamic queue tabs management
import { useAdminHotkeys } from '../hooks/useHotkeys';
import { HotkeysModal } from '../components/admin/HelpTooltip';
import { MobileNavigation } from '../components/admin/MobileOptimization';
import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';
import '../styles/admin-styles.css';

const AdminPanel = () => {
  const location = useLocation();
  const navigate = useNavigate();

  // ✅ Получаем patientId из URL для автоматического поиска
  const getPatientIdFromUrl = useCallback(() => {
    const params = new URLSearchParams(location.search);
    return params.get('patientId') ? parseInt(params.get('patientId'), 10) : null;
  }, [location.search]);

  // Состояние для UX улучшений
  const [showHotkeysModal, setShowHotkeysModal] = useState(false);

  // Обработчики горячих клавиш
  const hotkeyHandlers = {
    save: () => {






      // Логика сохранения для текущего раздела
    }, search: () => {// Фокус на поле поиска
      const searchInput = document.querySelector('input[placeholder*="поиск" i], input[placeholder*="search" i]');if (searchInput) {searchInput.focus();}},
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

  // ✅ Эффект для автоматической загрузки пациента из URL
  useEffect(() => {
    const loadPatientFromUrl = async () => {
      const patientIdFromUrl = getPatientIdFromUrl();
      if (!patientIdFromUrl) return;

      try {
        const token = tokenManager.getAccessToken();
        if (!token) return;

        const API_BASE = import.meta?.env?.VITE_API_BASE_URL || 'http://localhost:8000';
        const response = await fetch(`${API_BASE}/api/v1/patients/${patientIdFromUrl}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
          const patientData = await response.json();
          const patientName = `${patientData.last_name || ''} ${patientData.first_name || ''}`.trim();

          // Устанавливаем поисковый запрос для фильтрации пациентов
          setPatientsSearchTerm(patientName);

          // Навигируем на страницу пациентов, сохраняя patientId
          if (location.pathname !== '/admin/patients') {
            navigate(`/admin/patients?patientId=${patientIdFromUrl}`);
          }

          logger.info('[Admin] Загружен пациент из URL:', patientName);
        }
      } catch (error) {
        logger.error('[Admin] Не удалось загрузить пациента:', error);
      }
    };

    loadPatientFromUrl();
  }, [location.search, location.pathname, getPatientIdFromUrl, navigate, setPatientsSearchTerm]);

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
  void useAsyncAction();

  // Хук для управления отчетами
  void




















  useReports();


  // Хук для управления настройками
  const {
    saveSettings,
    resetSettings,
    exportSettings,
    importSettings
  } = useSettings();

  // Состояние для настроек
  const [settingsSubTab] = useState(() => {
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
  const [, setLogoFile] = useState(null);
  const [, setLogoPreview] = useState(null);

  // Настройки по умолчанию
  void {
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
  void ((event) => {
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
  });void (

  () => {
    setLogoFile(null);
    setLogoPreview(null);
  });

  // Хук для управления безопасностью
  const {
    exportSecurityLogs
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

  const { isDark } = useTheme();

  // Вспомогательные функции для работы с токенами








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
  void (async (settingsData) => {
    try {
      await saveSettings(settingsData);
    } catch (error) {
      logger.error('Ошибка сохранения настроек:', error);
      throw error;
    }
  });void (

  async () => {
    if (window.confirm('Вы уверены, что хотите сбросить все настройки к значениям по умолчанию?')) {
      try {
        await resetSettings();
      } catch (error) {
        logger.error('Ошибка сброса настроек:', error);
        alert('Ошибка при сбросе настроек');
      }
    }
  });void (

  async () => {
    try {
      await exportSettings();
    } catch (error) {
      logger.error('Ошибка экспорта настроек:', error);
      alert('Ошибка при экспорте настроек');
    }
  });void (

  async (file) => {
    try {
      await importSettings(file);
    } catch (error) {
      logger.error('Ошибка импорта настроек:', error);
      alert('Ошибка при импорте настроек');
    }
  });

  // Обработчики для безопасности
  void (














































  async (format = 'json') => {
    try {
      await exportSecurityLogs(format);
    } catch (error) {
      logger.error('Ошибка экспорта логов:', error);
      alert('Ошибка при экспорте логов безопасности');
    }
  });













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
  void (() => {
    userModal.openModal(null);
  });void (

  (user) => {
    userModal.openModal(user);
  });void (

  async (user) => {
    if (window.confirm(`Вы уверены, что хотите удалить пользователя "${user.name}"?`)) {
      try {
        await deleteUser(user.id);
      } catch (error) {
        logger.error('Ошибка удаления пользователя:', error);
        alert('Ошибка при удалении пользователя');
      }
    }
  });void (

  async (userData) => {
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
  });void (

  () => {
    userModal.closeModal();
  });void (

  (role) => {
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
  });void (

  (status) => {
    return status ? 'Активен' : 'Неактивен';
  });






  // ✅ УЛУЧШЕНИЕ: Обработчики для врачей с универсальным хуком
  const handleCreateDoctor = () => {
    doctorModal.openModal(null);
  };

  const handleEditDoctor = (doctor) => {
    doctorModal.openModal(doctor);
  };

  const handleDeleteDoctor = async (doctor) => {
    const doctorName = doctor.user?.full_name || doctor.name || doctor.user?.username || 'этого врача';
    if (window.confirm(`Вы уверены, что хотите деактивировать врача "${doctorName}"?\n\nВрач будет отмечен как неактивный, но останется в базе данных.`)) {
      try {
        await deleteDoctor(doctor.id);
        alert(`Врач "${doctorName}" успешно деактивирован`);
      } catch (error) {
        logger.error('Ошибка деактивации врача:', error);
        const errorMessage = error.message || 'Неизвестная ошибка';
        alert(`Ошибка при деактивации врача: ${errorMessage}`);
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
    { to: '/admin/graphql-explorer', label: 'GraphQL API', icon: Database }]

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
    { to: '/admin/all-free', label: 'Заявки All Free', icon: AlertTriangle }]

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
    { to: '/admin/settings', label: 'Настройки', icon: Settings }]

  }];


  // Получаем все табы для совместимости
  const tabs = navigationSections.flatMap((section) =>
  section.items.map((item) => ({
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

  const renderDashboard = () =>
  <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Красивые KPI карточки */}
        {statsLoading ?
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '24px'
      }}>
            <MacOSLoadingSkeleton type="card" count={6} />
          </div> :
      statsError ?
      <MacOSEmptyState
        icon={AlertCircle}
        title="Ошибка загрузки статистики"
        description="Не удалось загрузить данные. Проверьте подключение к серверу."
        action={
        <MacOSButton onClick={refreshStats} variant="primary">
                <RefreshCw size={16} />
                Повторить попытку
              </MacOSButton>
        } /> :


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
          loading={statsLoading} />


            <MacOSStatCard
          title="Врачи"
          value={stats.totalDoctors || 0}
          icon={Stethoscope}
          color="green"
          loading={statsLoading} />


            <MacOSStatCard
          title="Пациенты"
          value={stats.totalPatients || 0}
          icon={Users}
          color="purple"
          loading={statsLoading} />


            <MacOSStatCard
          title="Доход"
          value={formatCurrency(stats.totalRevenue || 0)}
          icon={TrendingUp}
          color="green"
          loading={statsLoading} />


            <MacOSStatCard
          title="Записи сегодня"
          value={stats.appointmentsToday || 0}
          icon={Calendar}
          color="orange"
          loading={statsLoading} />


            <MacOSStatCard
          title="Ожидают подтверждения"
          value={stats.pendingApprovals || 0}
          icon={Clock}
          color="red"
          loading={statsLoading} />

          </div>
      }

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
            {activityChartLoading ?
          <div style={{
            height: '256px',
            borderRadius: 'var(--mac-radius-md)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--mac-bg-secondary)'
          }}>
                <MacOSLoadingSkeleton type="text" count={3} />
              </div> :
          activityChartError ?
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
              description="Не удалось загрузить данные активности" />

              </div> :
          activityChartData?.data && activityChartData.data.length > 0 ?
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
                const maxValue = Math.max(...activityChartData.data.map((d) => d.total || 0));
                const height = maxValue > 0 ? item.total / maxValue * 180 : 0;
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
                      </div>);

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
              </div> :

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
          }
          </MacOSCard>

          <MacOSCard
          style={{ padding: 0 }}>

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
            {recentActivitiesLoading ?
          <div style={{ padding: '16px' }}>
                <MacOSLoadingSkeleton type="text" count={4} />
              </div> :
          recentActivitiesError ?
          <div style={{ padding: '16px' }}>
                <MacOSEmptyState
              icon={AlertTriangle}
              title="Ошибка загрузки"
              description="Не удалось загрузить последние действия" />

              </div> :
          recentActivities.length === 0 ?
          <div style={{ padding: '16px', textAlign: 'center' }}>
                <p style={{ color: 'var(--mac-text-secondary)' }}>Нет последних действий</p>
              </div> :

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {recentActivities.map((activity) =>
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
            )}
              </div>
          }
          </MacOSCard>
        </div>

        {/* Системные уведомления */}
        <MacOSCard
        style={{ padding: 0, marginTop: '24px' }}>

          <div style={{ padding: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>Системные уведомления</h3>
            <MacOSBadge variant="warning">{systemAlerts.length}</MacOSBadge>
          </div>
          {systemAlertsLoading ?
        <div style={{ padding: '16px' }}>
              <MacOSLoadingSkeleton type="text" count={3} />
            </div> :
        systemAlertsError ?
        <div style={{ padding: '16px' }}>
              <MacOSEmptyState
            icon={AlertTriangle}
            title="Ошибка загрузки"
            description="Не удалось загрузить системные уведомления" />

            </div> :
        systemAlerts.length === 0 ?
        <div style={{ padding: '16px', textAlign: 'center' }}>
              <p style={{ color: 'var(--mac-text-secondary)' }}>Нет системных уведомлений</p>
            </div> :

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {systemAlerts.map((alert) =>
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
          )}
            </div>
        }
        </MacOSCard>
      </div>
    </ErrorBoundary>;












































































































































































































































































































































































































































































































































































































































































































































































































































































































































































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
        return <UnifiedUserManagement />;
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
      case 'services':{
          // Вкладки для секции Services
          // ⭐ SSOT: DepartmentManagement удалён - QueueProfilesManager теперь единственный источник для вкладок регистратуры
          const serviceTabs = [
          { key: 'catalog', label: 'Справочник услуг', icon: Package },
          { key: 'queue-profiles', label: 'Вкладки регистратуры', icon: FolderTree } // ⭐ SSOT: Dynamic queue tabs
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
              {serviceTabs.map((tab) => {
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
                      }}>

                    <TabIcon size={18} />
                    {tab.label}
                  </button>);

                })}
            </div>

            {/* Содержимое вкладок */}
            {servicesTab === 'catalog' && <ServiceCatalog />}
            {servicesTab === 'queue-profiles' && <QueueProfilesManager theme={isDark ? 'dark' : 'light'} />}
          </div>);

        }
      case 'departments':
        // ⭐ DEPRECATED: Redirect to SSOT queue-profiles
        return <QueueProfilesManager theme={isDark ? 'dark' : 'light'} />;
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
                {tabs.find((tab) => tab.id === current)?.label || 'Неизвестный раздел'}
              </h2>
              <p style={{ color: 'var(--mac-text-secondary)' }}>Этот раздел находится в разработке</p>
            </div>
          </MacOSCard>);

    }
  };

  // Заглушки для остальных разделов
  const renderDoctors = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard
      variant="default"
      style={{ padding: '24px' }}>

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
            iconPosition="left" />

          </div>
          <MacOSInput
          type="text"
          placeholder="Специализация..."
          value={filterSpecialization}
          onChange={(e) => setFilterSpecialization(e.target.value)} />

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
          { value: 'general', label: 'Общее' }]
          }
          style={{
            padding: '8px 12px',
            borderRadius: 'var(--mac-radius-sm)',
            border: '1px solid var(--mac-border)',
            background: 'var(--mac-bg-primary)',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-sm)',
            outline: 'none'
          }} />

          <MacOSSelect
          value={doctorsFilterStatus}
          onChange={(e) => setDoctorsFilterStatus(e.target.value)}
          options={[
          { value: '', label: 'Все статусы' },
          { value: 'active', label: 'Активен' },
          { value: 'inactive', label: 'Неактивен' },
          { value: 'on_leave', label: 'В отпуске' }]
          }
          style={{
            padding: '8px 12px',
            borderRadius: 'var(--mac-radius-sm)',
            border: '1px solid var(--mac-border)',
            background: 'var(--mac-bg-primary)',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-sm)',
            outline: 'none'
          }} />

        </div>

        {/* Таблица врачей */}
        <div style={{ overflowX: 'auto' }}>
          {doctorsLoading ?
        <MacOSLoadingSkeleton type="table" count={5} /> :
        doctorsError ?
        <EmptyState
          type="error"
          title="Ошибка загрузки врачей"
          description="Не удалось загрузить список врачей"
          action={
          <MacOSButton onClick={() => window.location.reload()}>
                  <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                  Обновить
                </MacOSButton>
          } /> :

        doctors.length === 0 ?
        <EmptyState
          type="users"
          title="Врачи не найдены"
          description={doctorsSearchTerm || filterSpecialization || filterDepartment || doctorsFilterStatus ?
          'Попробуйте изменить параметры поиска' :
          'В системе пока нет врачей'
          }
          action={
          <MacOSButton onClick={handleCreateDoctor}>
                  <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                  Добавить первого врача
                </MacOSButton>
          } /> :


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
                {doctors.map((doctor) =>
            <tr key={doctor.id} style={{
              borderBottom: '1px solid var(--mac-border)',
              transition: 'background-color var(--mac-duration-normal) var(--mac-ease)'
            }}
            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)'}
            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>

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
                        return name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);
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
                          {doctor.user?.phone &&
                    <p style={{
                      fontSize: '11px',
                      color: 'var(--mac-text-tertiary)',
                      margin: '2px 0 0 0'
                    }}>{doctor.user.phone}</p>
                    }
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
                        {doctor.specialty ? getDepartmentLabel(doctor.specialty) : doctor.department ? getDepartmentLabel(doctor.department) : 'Не указано'}
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
                  variant={doctor.active ? 'success' : 'warning'}>

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
                    title="Редактировать">

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
                    title="Деактивировать">

                          <Trash2 style={{ width: '16px', height: '16px' }} />
                        </button>
                      </div>
                    </td>
                  </tr>
            )}
              </tbody>
            </table>
        }
        </div>
      </MacOSCard>

      {/* ✅ УЛУЧШЕНИЕ: Модальное окно врача с универсальным хуком */}
      <DoctorModal
      isOpen={doctorModal.isOpen}
      onClose={handleCloseDoctorModal}
      doctor={doctorModal.selectedItem}
      onSave={handleSaveDoctor}
      loading={doctorModal.loading} />

    </div>;


  const renderPatients = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard
      variant="default"
      style={{ padding: '24px' }}>

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
            }} />

          </div>
          <MacOSSelect
          value={filterGender}
          onChange={(e) => setFilterGender(e.target.value)}
          options={[
          { value: '', label: 'Все полы' },
          { value: 'male', label: 'Мужской' },
          { value: 'female', label: 'Женский' }]
          }
          style={{
            padding: '8px 12px',
            borderRadius: 'var(--mac-radius-sm)',
            border: '1px solid var(--mac-border)',
            background: 'var(--mac-bg-primary)',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-sm)',
            outline: 'none'
          }} />

          <MacOSSelect
          value={filterAgeRange}
          onChange={(e) => setFilterAgeRange(e.target.value)}
          options={[
          { value: '', label: 'Все возрасты' },
          { value: '0-18', label: '0-18 лет' },
          { value: '19-35', label: '19-35 лет' },
          { value: '36-50', label: '36-50 лет' },
          { value: '51-65', label: '51-65 лет' },
          { value: '65+', label: '65+ лет' }]
          }
          style={{
            padding: '8px 12px',
            borderRadius: 'var(--mac-radius-sm)',
            border: '1px solid var(--mac-border)',
            background: 'var(--mac-bg-primary)',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-sm)',
            outline: 'none'
          }} />

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
          { value: 'O-', label: 'O-' }]
          }
          style={{
            padding: '8px 12px',
            borderRadius: 'var(--mac-radius-sm)',
            border: '1px solid var(--mac-border)',
            background: 'var(--mac-bg-primary)',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-sm)',
            outline: 'none'
          }} />

        </div>

        {/* Таблица пациентов */}
        <div style={{ overflowX: 'auto' }}>
          {patientsLoading ?
        <MacOSLoadingSkeleton type="table" count={5} /> :
        patientsError ?
        <MacOSEmptyState
          type="error"
          title="Ошибка загрузки пациентов"
          description="Не удалось загрузить список пациентов"
          action={
          <MacOSButton onClick={() => window.location.reload()}>
                  <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                  Обновить
                </MacOSButton>
          } /> :

        patients.length === 0 ?
        <MacOSEmptyState
          type="users"
          title="Пациенты не найдены"
          description={patientsSearchTerm || filterGender || filterAgeRange || filterBloodType ?
          'Попробуйте изменить параметры поиска' :
          'В системе пока нет пациентов'
          }
          action={
          <MacOSButton onClick={handleCreatePatient}>
                  <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                  Добавить первого пациента
                </MacOSButton>
          } /> :


        <MacOSTable
          columns={[
          { key: 'patient', title: 'Пациент', width: '30%' },
          { key: 'age', title: 'Возраст', width: '8%' },
          { key: 'gender', title: 'Пол', width: '8%' },
          { key: 'phone', title: 'Телефон', width: '12%' },
          { key: 'bloodType', title: 'Группа крови', width: '10%' },
          { key: 'lastVisit', title: 'Последний визит', width: '12%' },
          { key: 'visits', title: 'Визиты', width: '10%' },
          { key: 'actions', title: 'Действия', width: '10%' }]
          }
          data={patients.map((patient) => ({
            id: patient.id,
            patient:
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
                      {patient.address &&
                <p style={{
                  fontSize: '11px',
                  color: 'var(--mac-text-tertiary)',
                  margin: '2px 0 0 0'
                }}>
                          {patient.address}
                        </p>
                }
                    </div>
                  </div>,

            age:
            <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
                    {calculateAge(patient.birthDate)} лет
                  </div>,

            gender:
            <MacOSBadge variant={patient.gender === 'male' ? 'info' : 'success'}>
                    {getGenderLabel(patient.gender)}
                  </MacOSBadge>,

            phone:
            <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
                    {patient.phone}
                  </div>,

            bloodType:
            patient.bloodType ?
            <MacOSBadge variant="warning">
                      {patient.bloodType}
                    </MacOSBadge> :

            <span style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-tertiary)'
            }}>Не указано</span>,


            lastVisit:
            <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
                    {patient.lastVisit ? new Date(patient.lastVisit).toLocaleDateString('ru-RU') : 'Нет визитов'}
                  </div>,

            visits:
            <div style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-secondary)'
            }}>
                    {patient.visitsCount} визитов
                  </div>,

            actions:
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
                title="Редактировать">

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
                title="Удалить">

                      <Trash2 style={{ width: '16px', height: '16px' }} />
                    </MacOSButton>
                  </div>

          }))} />

        }
        </div>
      </MacOSCard>

      {/* Модальное окно пациента */}
      {/* ✅ УЛУЧШЕНИЕ: Модальное окно пациента с универсальным хуком */}
      <PatientModal
      isOpen={patientModal.isOpen}
      onClose={handleClosePatientModal}
      patient={patientModal.selectedItem}
      onSave={handleSavePatient}
      loading={patientModal.loading} />

    </div>;


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
            style={{ padding: '24px' }}>

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
            style={{ padding: '24px' }}>

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
            style={{ padding: '24px' }}>

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
            style={{ padding: '24px' }}>

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
          style={{ padding: '24px' }}>

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
                }} />

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
              { value: 'no_show', label: 'Не явился' }]
              }
              style={{ minWidth: '140px' }} />

            <MacOSInput
              type="date"
              value={appointmentFilterDate}
              onChange={(e) => setAppointmentFilterDate(e.target.value)}
              style={{ minWidth: '140px' }} />

            <MacOSSelect
              value={appointmentFilterDoctor}
              onChange={(e) => setAppointmentFilterDoctor(e.target.value)}
              options={[
              { value: '', label: 'Все врачи' },
              ...doctors.map((doctor) => ({
                value: doctor.id,
                label: doctor.user?.full_name || doctor.name || doctor.user?.username || `Врач #${doctor.id}`
              }))]
              }
              style={{ minWidth: '140px' }} />

          </div>

          {/* Таблица записей */}
          <div style={{ overflowX: 'auto' }}>
            {appointmentsLoading ?
            <MacOSLoadingSkeleton type="table" count={5} /> :
            appointmentsError ?
            <EmptyState
              type="error"
              title="Ошибка загрузки записей"
              description="Не удалось загрузить список записей"
              action={
              <MacOSButton onClick={() => window.location.reload()}>
                    <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                    Обновить
                  </MacOSButton>
              } /> :

            appointments.length === 0 ?
            <MacOSEmptyState
              type="calendar"
              title="Записи не найдены"
              description={appointmentsSearchTerm || appointmentFilterStatus || appointmentFilterDate || appointmentFilterDoctor ?
              'Попробуйте изменить параметры поиска' :
              'В системе пока нет записей'
              }
              action={
              <MacOSButton onClick={handleCreateAppointment}>
                    <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                    Создать первую запись
                  </MacOSButton>
              } /> :


            <MacOSTable
              columns={[
              { key: 'patient', title: 'Пациент', width: '25%' },
              { key: 'doctor', title: 'Врач', width: '20%' },
              { key: 'datetime', title: 'Дата и время', width: '20%' },
              { key: 'status', title: 'Статус', width: '15%' },
              { key: 'reason', title: 'Причина', width: '15%' },
              { key: 'actions', title: 'Действия', width: '5%' }]
              }
              data={appointments.map((appointment) => ({
                id: appointment.id,
                patient:
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
                          {appointment.patientName.split(' ').map((n) => n[0]).join('').toUpperCase()}
                        </span>
                      </div>
                      <div>
                        <p style={{
                      fontWeight: 'var(--mac-font-weight-medium)',
                      color: 'var(--mac-text-primary)',
                      margin: 0
                    }}>{appointment.patientName}</p>
                        {appointment.phone &&
                    <p style={{
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-secondary)',
                      margin: '4px 0 0 0'
                    }}>{appointment.phone}</p>
                    }
                      </div>
                    </div>,

                doctor:
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
                    </div>,

                datetime:
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
                    </div>,

                status:
                <MacOSBadge variant={getAppointmentStatusVariant(appointment.status)}>
                      {getAppointmentStatusLabel(appointment.status)}
                    </MacOSBadge>,

                reason:
                <p style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>
                      {appointment.reason.length > 50 ?
                  `${appointment.reason.substring(0, 50)}...` :
                  appointment.reason
                  }
                    </p>,

                actions:
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
                    title="Редактировать">

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
                    title="Удалить">

                        <Trash2 style={{ width: '16px', height: '16px' }} />
                      </MacOSButton>
                    </div>

              }))} />

            }
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
          patients={patients} />

      </div>);

  };

  const renderFinance = () => {
    const financialStats = getFinancialStats();void
    getCategoryStats();void
    getDailyStats(7);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Финансовая статистика */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px'
        }}>
          <MacOSCard
            style={{ padding: '24px' }}>

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
            style={{ padding: '24px' }}>

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
            style={{ padding: '24px' }}>

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
            style={{ padding: '24px' }}>

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
          style={{ padding: 0 }}>

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
                }} />

            </div>
            <MacOSSelect
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              options={[
              { value: '', label: 'Все типы' },
              { value: 'income', label: 'Доходы' },
              { value: 'expense', label: 'Расходы' }]
              }
              style={{
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-sm)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                outline: 'none'
              }} />

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
              { value: 'Медикаменты', label: 'Медикаменты' }]
              }
              style={{
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-sm)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                outline: 'none'
              }} />

            <MacOSSelect
              value={filterDateRange}
              onChange={(e) => setFilterDateRange(e.target.value)}
              options={[
              { value: '', label: 'Все время' },
              { value: 'today', label: 'Сегодня' },
              { value: 'week', label: 'Неделя' },
              { value: 'month', label: 'Месяц' },
              { value: 'year', label: 'Год' }]
              }
              style={{
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-sm)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                outline: 'none'
              }} />

            <MacOSSelect
              value={financeFilterStatus}
              onChange={(e) => setFinanceFilterStatus(e.target.value)}
              options={[
              { value: '', label: 'Все статусы' },
              { value: 'pending', label: 'Ожидает' },
              { value: 'completed', label: 'Завершена' },
              { value: 'cancelled', label: 'Отменена' },
              { value: 'refunded', label: 'Возврат' }]
              }
              style={{
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-sm)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                outline: 'none'
              }} />

          </div>

          {/* Таблица транзакций */}
          <div style={{ overflowX: 'auto' }}>
            {financeLoading ?
            <MacOSLoadingSkeleton type="table" count={5} /> :
            financeError ?
            <EmptyState
              type="error"
              title="Ошибка загрузки транзакций"
              description="Не удалось загрузить список транзакций"
              action={
              <MacOSButton onClick={() => window.location.reload()}>
                    <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                    Обновить
                  </MacOSButton>
              } /> :

            transactions.length === 0 ?
            <EmptyState
              type="creditcard"
              title="Транзакции не найдены"
              description={financeSearchTerm || filterType || filterCategory || filterDateRange || financeFilterStatus ?
              'Попробуйте изменить параметры поиска' :
              'В системе пока нет транзакций'
              }
              action={
              <MacOSButton onClick={handleCreateTransaction}>
                    <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                    Добавить первую транзакцию
                  </MacOSButton>
              } /> :


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
                  {transactions.map((transaction) =>
                <tr
                  key={transaction.id}
                  style={{ borderBottom: '1px solid var(--mac-separator)', transition: 'all var(--mac-duration-normal) var(--mac-ease)' }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>

                      <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                        <MacOSBadge variant={transaction.type === 'income' ? 'success' : 'error'}>
                          {getTransactionTypeLabel(transaction.type)}
                        </MacOSBadge>
                      </td>
                      <td style={{ padding: 'var(--mac-spacing-3) var(--mac-spacing-4)' }}>
                        <div>
                          <p style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)', margin: 0 }}>{transaction.category}</p>
                          {transaction.patientName &&
                      <p style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', margin: '4px 0 0 0' }}>{transaction.patientName}</p>
                      }
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
                          {transaction.description.length > 50 ?
                      `${transaction.description.substring(0, 50)}...` :
                      transaction.description
                      }
                        </p>
                        {transaction.reference &&
                    <p style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)', margin: '4px 0 0 0' }}>
                            {transaction.reference}
                          </p>
                    }
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
                        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)'}
                        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                        title="Редактировать">

                            <Edit style={{ width: '16px', height: '16px' }} />
                          </button>
                          <button
                        onClick={() => handleDeleteTransaction(transaction)}
                        style={{ padding: 'var(--mac-spacing-2)', borderRadius: 'var(--mac-radius-sm)', backgroundColor: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--mac-danger)', transition: 'all var(--mac-duration-normal) var(--mac-ease)' }}
                        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)'}
                        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                        title="Удалить">

                            <Trash2 style={{ width: '16px', height: '16px' }} />
                          </button>
                        </div>
                      </td>
                    </tr>
                )}
                </tbody>
              </table>
            }
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
          doctors={doctors} />

      </div>);

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
            {[...Array(6)].map((_, i) =>
            <MacOSLoadingSkeleton key={i} style={{ height: '96px' }} />
            )}
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
      </div>);

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
          onNavigate={(path) => navigate(path)} />


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
          onClose={() => setShowHotkeysModal(false)} />

      </div>
    </div>);

};

export default AdminPanel;
