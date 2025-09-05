import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { 
  Users, 
  Building2, 
  Calendar, 
  BarChart3, 
  Settings, 
  Shield, 
  FileText, 
  CreditCard,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Clock,
  UserPlus,
  Database,
  Activity,
  Bell,
  Search,
  Filter,
  Download,
  Upload,
  Eye,
  Edit,
  Trash2,
  Plus,
  MoreHorizontal,
  ChevronDown,
  ChevronUp,
  RefreshCw
} from 'lucide-react';
import { Card, Badge, Button, Skeleton } from '../design-system/components';
import { useBreakpoint, useTouchDevice } from '../design-system/hooks';
import { useFade, useSlide, useScale } from '../design-system/hooks/useAnimation';
import { useTheme } from '../contexts/ThemeContext';
import KPICard from '../components/admin/KPICard';
import AdminNavigation from '../components/admin/AdminNavigation';
import ErrorBoundary from '../components/admin/ErrorBoundary';
import LoadingSkeleton from '../components/admin/LoadingSkeleton';
import EmptyState from '../components/admin/EmptyState';
import useAdminData from '../hooks/useAdminData';
import useUsers from '../hooks/useUsers';
import useDoctors from '../hooks/useDoctors';
import usePatients from '../hooks/usePatients';
import useAppointments from '../hooks/useAppointments';
import UserModal from '../components/admin/UserModal';
import DoctorModal from '../components/admin/DoctorModal';
import PatientModal from '../components/admin/PatientModal';
import AppointmentModal from '../components/admin/AppointmentModal';
import '../styles/admin.css';

const AdminPanel = () => {
  const location = useLocation();
  const navigate = useNavigate();
  
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
    createUser,
    updateUser,
    deleteUser
  } = useUsers();
  
  // Состояние модального окна пользователей
  const [showUserModal, setShowUserModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userModalLoading, setUserModalLoading] = useState(false);
  
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
  
  // Состояние модального окна врачей
  const [showDoctorModal, setShowDoctorModal] = useState(false);
  const [selectedDoctor, setSelectedDoctor] = useState(null);
  const [doctorModalLoading, setDoctorModalLoading] = useState(false);
  
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
  
  // Состояние модального окна пациентов
  const [showPatientModal, setShowPatientModal] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [patientModalLoading, setPatientModalLoading] = useState(false);
  
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
  
  // Состояние модального окна записей
  const [showAppointmentModal, setShowAppointmentModal] = useState(false);
  const [selectedAppointment, setSelectedAppointment] = useState(null);
  const [appointmentModalLoading, setAppointmentModalLoading] = useState(false);
  
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
  
  const { isMobile, isTablet } = useBreakpoint();
  const isTouchDevice = useTouchDevice();
  const { 
    theme, 
    isDark, 
    isLight, 
    toggleTheme, 
    getColor, 
    getSpacing, 
    getFontSize 
  } = useTheme();
  
  // Анимации
  const { isVisible: fadeIn, fadeIn: startFadeIn } = useFade(false);
  const { isVisible: slideIn, slideIn: startSlideIn } = useSlide(false, 'up');
  const { isVisible: scaleIn, scaleIn: startScaleIn } = useScale(false);
  const [animationsStarted, setAnimationsStarted] = useState(false);

  useEffect(() => {
    // Запуск анимаций только один раз после первой загрузки статистики
    if (!statsLoading && !animationsStarted && statsData) {
      const timer = setTimeout(() => {
        startFadeIn(300);
        startSlideIn(400);
        startScaleIn(500);
        setAnimationsStarted(true);
      }, 100);
      
      return () => clearTimeout(timer);
    }
  }, [statsLoading, animationsStarted, statsData, startFadeIn, startSlideIn, startScaleIn]);

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'UZS',
      minimumFractionDigits: 0
    }).format(amount);
  };

  const getStatusIcon = (status) => {
    const colorMap = {
      success: 'var(--success-color)',
      warning: 'var(--warning-color)',
      error: 'var(--danger-color)',
      info: 'var(--info-color)',
      default: 'var(--text-tertiary)'
    };
    if (status === 'success') return <CheckCircle className="w-4 h-4" style={{ color: colorMap.success }} />;
    if (status === 'warning') return <AlertTriangle className="w-4 h-4" style={{ color: colorMap.warning }} />;
    if (status === 'error') return <AlertTriangle className="w-4 h-4" style={{ color: colorMap.error }} />;
    if (status === 'info') return <Clock className="w-4 h-4" style={{ color: colorMap.info }} />;
    return <Clock className="w-4 h-4" style={{ color: colorMap.default }} />;
  };

  // Обработчики для пользователей
  const handleCreateUser = () => {
    setSelectedUser(null);
    setShowUserModal(true);
  };

  const handleEditUser = (user) => {
    setSelectedUser(user);
    setShowUserModal(true);
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
    setUserModalLoading(true);
    try {
      if (selectedUser) {
        await updateUser(selectedUser.id, userData);
      } else {
        await createUser(userData);
      }
    } catch (error) {
      console.error('Ошибка сохранения пользователя:', error);
      throw error;
    } finally {
      setUserModalLoading(false);
    }
  };

  const handleCloseUserModal = () => {
    setShowUserModal(false);
    setSelectedUser(null);
  };

  const getRoleLabel = (role) => {
    const roleMap = {
      admin: 'Администратор',
      doctor: 'Врач',
      registrar: 'Регистратор',
      cashier: 'Кассир',
      lab: 'Лаборант',
      user: 'Пользователь'
    };
    return roleMap[role] || role;
  };

  const getStatusLabel = (status) => {
    const statusMap = {
      active: 'Активен',
      inactive: 'Неактивен',
      blocked: 'Заблокирован'
    };
    return statusMap[status] || status;
  };

  const getStatusColor = (status) => {
    const colorMap = {
      active: 'var(--success-color)',
      inactive: 'var(--warning-color)',
      blocked: 'var(--danger-color)'
    };
    return colorMap[status] || 'var(--text-tertiary)';
  };

  // Обработчики для врачей
  const handleCreateDoctor = () => {
    setSelectedDoctor(null);
    setShowDoctorModal(true);
  };

  const handleEditDoctor = (doctor) => {
    setSelectedDoctor(doctor);
    setShowDoctorModal(true);
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
    setDoctorModalLoading(true);
    try {
      if (selectedDoctor) {
        await updateDoctor(selectedDoctor.id, doctorData);
      } else {
        await createDoctor(doctorData);
      }
    } catch (error) {
      console.error('Ошибка сохранения врача:', error);
      throw error;
    } finally {
      setDoctorModalLoading(false);
    }
  };

  const handleCloseDoctorModal = () => {
    setShowDoctorModal(false);
    setSelectedDoctor(null);
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
      active: 'var(--success-color)',
      inactive: 'var(--warning-color)',
      on_leave: 'var(--info-color)'
    };
    return colorMap[status] || 'var(--text-tertiary)';
  };

  // Обработчики для пациентов
  const handleCreatePatient = () => {
    setSelectedPatient(null);
    setShowPatientModal(true);
  };

  const handleEditPatient = (patient) => {
    setSelectedPatient(patient);
    setShowPatientModal(true);
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
    setPatientModalLoading(true);
    try {
      if (selectedPatient) {
        await updatePatient(selectedPatient.id, patientData);
      } else {
        await createPatient(patientData);
      }
    } catch (error) {
      console.error('Ошибка сохранения пациента:', error);
      throw error;
    } finally {
      setPatientModalLoading(false);
    }
  };

  const handleClosePatientModal = () => {
    setShowPatientModal(false);
    setSelectedPatient(null);
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
  const handleCreateAppointment = () => {
    setSelectedAppointment(null);
    setShowAppointmentModal(true);
  };

  const handleEditAppointment = (appointment) => {
    setSelectedAppointment(appointment);
    setShowAppointmentModal(true);
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
    setAppointmentModalLoading(true);
    try {
      if (selectedAppointment) {
        await updateAppointment(selectedAppointment.id, appointmentData);
      } else {
        await createAppointment(appointmentData);
      }
    } catch (error) {
      console.error('Ошибка сохранения записи:', error);
      throw error;
    } finally {
      setAppointmentModalLoading(false);
    }
  };

  const handleCloseAppointmentModal = () => {
    setShowAppointmentModal(false);
    setSelectedAppointment(null);
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
      pending: 'var(--warning-color)',
      confirmed: 'var(--info-color)',
      paid: 'var(--success-color)',
      in_visit: 'var(--accent-color)',
      completed: 'var(--success-color)',
      cancelled: 'var(--danger-color)',
      no_show: 'var(--text-tertiary)'
    };
    return colorMap[status] || 'var(--text-tertiary)';
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

  // Новая структура навигации
  const navigationSections = [
    {
      title: 'Обзор',
      items: [
        { to: '/admin', label: 'Дашборд', icon: BarChart3 },
        { to: '/admin/analytics', label: 'Аналитика', icon: TrendingUp }
      ]
    },
    {
      title: 'Управление',
      items: [
        { to: '/admin/users', label: 'Пользователи', icon: Users },
        { to: '/admin/doctors', label: 'Врачи', icon: UserPlus },
        { to: '/admin/patients', label: 'Пациенты', icon: Users },
        { to: '/admin/appointments', label: 'Записи', icon: Calendar }
      ]
    },
    {
      title: 'Система',
      items: [
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

  // Вычисляем текущую вкладку из URL
  const path = location.pathname || '/admin';
  let current = 'dashboard';
  
  if (path === '/admin' || path === '/admin/') {
    current = 'dashboard';
  } else if (path.startsWith('/admin/')) {
    const segments = path.split('/').filter(Boolean);
    const adminIndex = segments.indexOf('admin');
    if (adminIndex !== -1 && segments[adminIndex + 1]) {
      current = segments[adminIndex + 1];
    } else {
      current = 'dashboard';
    }
  }

  const renderDashboard = () => (
    <ErrorBoundary>
      <div className="space-y-6">
        {/* Красивые KPI карточки */}
        {statsLoading ? (
          <div className="admin-kpi-grid grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6">
            <LoadingSkeleton type="card" count={6} />
          </div>
        ) : statsError ? (
          <EmptyState
            type="default"
            title="Ошибка загрузки статистики"
            description="Не удалось загрузить данные. Проверьте подключение к серверу."
            action={
              <Button onClick={refreshStats} variant="primary">
                <RefreshCw size={16} />
                Повторить попытку
              </Button>
            }
          />
        ) : (
          <div className="admin-kpi-grid grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-6">
            <KPICard
              title="Всего пользователей"
              value={stats.totalUsers}
              icon={Users}
              color="blue"
              trend="+5.2%"
              trendType="positive"
              loading={isLoading}
            />
        
            <KPICard
              title="Врачи"
              value={stats.totalDoctors}
              icon={UserPlus}
              color="green"
              trend="+2"
              trendType="positive"
              loading={isLoading}
            />
        
            <KPICard
              title="Пациенты"
              value={stats.totalPatients}
              icon={Users}
              color="purple"
              trend="+12.3%"
              trendType="positive"
              loading={isLoading}
            />
            
            <KPICard
              title="Доход"
              value={formatCurrency(stats.totalRevenue)}
              icon={TrendingUp}
              color="green"
              trend="+8.7%"
              trendType="positive"
              loading={isLoading}
            />
            
            <KPICard
              title="Записи сегодня"
              value={stats.appointmentsToday}
              icon={Calendar}
              color="orange"
              trend="+15"
              trendType="positive"
              loading={isLoading}
            />
            
            <KPICard
              title="Ожидают одобрения"
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
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Активность системы</h3>
              <Button variant="outline" size="sm">
                <Download className="w-4 h-4 mr-2" />
                Экспорт
              </Button>
            </div>
            <div className="h-64 rounded-lg flex items-center justify-center" style={{ background: 'var(--bg-secondary)' }}>
              <div className="text-center">
                <Activity className="w-12 h-12 mx-auto mb-2" style={{ color: 'var(--text-tertiary)' }} />
                <p style={{ color: 'var(--text-secondary)' }}>График активности</p>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Последние действия</h3>
              <Button variant="outline" size="sm">
                <Eye className="w-4 h-4 mr-2" />
                Все
              </Button>
            </div>
            <div className="space-y-3">
              {recentActivities.map((activity) => (
                <div key={activity.id} className="flex items-center space-x-3 p-3 rounded-lg" style={{ background: 'var(--bg-secondary)' }}>
                  {getStatusIcon(activity.status)}
                  <div className="flex-1">
                    <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{activity.message}</p>
                    <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{activity.user} • {activity.time}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Системные уведомления */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Системные уведомления</h3>
            <Badge variant="warning">{systemAlerts.length}</Badge>
          </div>
            <div className="space-y-3">
              {systemAlerts.map((alert) => (
                <div key={alert.id} className="flex items-center space-x-3 p-3 border rounded-lg" style={{ borderColor: 'var(--border-color)' }}>
                  <AlertTriangle className="w-5 h-5" style={{ color: 'var(--warning-color)' }} />
                  <div className="flex-1">
                    <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{alert.message}</p>
                    <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{alert.time}</p>
                  </div>
                  <Badge variant={alert.priority === 'high' ? 'error' : alert.priority === 'medium' ? 'warning' : 'info'}>
                    {alert.priority}
                  </Badge>
                </div>
              ))}
            </div>
          </Card>
        </div>
    </ErrorBoundary>
  );

  const renderUsers = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Управление пользователями</h2>
          <Button onClick={handleCreateUser}>
            <Plus className="w-4 h-4 mr-2" />
            Добавить пользователя
          </Button>
        </div>
        
        {/* Поиск и фильтры */}
        <div className="flex items-center space-x-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-tertiary)' }} />
            <input
              type="text"
              placeholder="Поиск пользователей..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg focus:ring-2"
              style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
            />
          </div>
          <select
            value={filterRole}
            onChange={(e) => setFilterRole(e.target.value)}
            className="px-3 py-2 rounded-lg border focus:ring-2"
            style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
          >
            <option value="">Все роли</option>
            <option value="admin">Администратор</option>
            <option value="doctor">Врач</option>
            <option value="registrar">Регистратор</option>
            <option value="cashier">Кассир</option>
            <option value="lab">Лаборант</option>
            <option value="user">Пользователь</option>
          </select>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-3 py-2 rounded-lg border focus:ring-2"
            style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
          >
            <option value="">Все статусы</option>
            <option value="active">Активен</option>
            <option value="inactive">Неактивен</option>
            <option value="blocked">Заблокирован</option>
          </select>
        </div>

        {/* Таблица пользователей */}
        <div className="overflow-x-auto">
          {usersLoading ? (
            <LoadingSkeleton type="table" count={5} />
          ) : usersError ? (
            <EmptyState
              type="error"
              title="Ошибка загрузки пользователей"
              description="Не удалось загрузить список пользователей"
              action={
                <Button onClick={() => window.location.reload()}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Обновить
                </Button>
              }
            />
          ) : users.length === 0 ? (
            <EmptyState
              type="users"
              title="Пользователи не найдены"
              description={searchTerm || filterRole || filterStatus 
                ? "Попробуйте изменить параметры поиска" 
                : "В системе пока нет пользователей"
              }
              action={
                <Button onClick={handleCreateUser}>
                  <Plus className="w-4 h-4 mr-2" />
                  Добавить первого пользователя
                </Button>
              }
            />
          ) : (
            <table className="w-full" role="table" aria-label="Таблица пользователей">
              <thead>
                <tr className="border-b" style={{ borderColor: 'var(--border-color)' }}>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Пользователь</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Роль</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Статус</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Последний вход</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Действия</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className="border-b hover:bg-gray-50" style={{ borderColor: 'var(--border-color)' }}>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'var(--accent-color)' }}>
                          <span className="text-white text-sm font-medium">
                            {user.name.split(' ').map(n => n[0]).join('').toUpperCase()}
                          </span>
                        </div>
                        <div>
                          <p className="font-medium" style={{ color: 'var(--text-primary)' }}>{user.name}</p>
                          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{user.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <Badge 
                        variant={user.role === 'admin' ? 'error' : user.role === 'doctor' ? 'success' : 'info'}
                      >
                        {getRoleLabel(user.role)}
                      </Badge>
                    </td>
                    <td className="py-3 px-4">
                      <Badge 
                        variant={user.status === 'active' ? 'success' : user.status === 'inactive' ? 'warning' : 'error'}
                      >
                        {getStatusLabel(user.status)}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
                      {user.lastLogin}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        <button 
                          onClick={() => handleEditUser(user)}
                          className="p-1 hover:bg-gray-100 rounded transition-colors" 
                          style={{ color: 'var(--text-secondary)' }}
                          title="Редактировать"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => handleDeleteUser(user)}
                          className="p-1 hover:bg-red-100 rounded transition-colors" 
                          style={{ color: 'var(--danger-color)' }}
                          title="Удалить"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </Card>

      {/* Модальное окно пользователя */}
      <UserModal
        isOpen={showUserModal}
        onClose={handleCloseUserModal}
        user={selectedUser}
        onSave={handleSaveUser}
        loading={userModalLoading}
      />
    </div>
  );

  const renderAnalytics = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">Аналитика и отчеты</h2>
          <div className="flex gap-2">
            <Button variant="outline">
              <Download className="w-4 h-4 mr-2" />
              Экспорт
            </Button>
            <Button>
              <BarChart3 className="w-4 h-4 mr-2" />
              Создать отчет
            </Button>
          </div>
        </div>

        {/* Фильтры */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6" role="group" aria-label="Фильтры аналитики">
          <div>
            <label htmlFor="period" className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Период</label>
            <select id="period" aria-label="Период" className="w-full px-3 py-2 rounded-lg focus:ring-2" style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
              <option>Сегодня</option>
              <option>Неделя</option>
              <option>Месяц</option>
              <option>Квартал</option>
              <option>Год</option>
            </select>
          </div>
          <div>
            <label htmlFor="department" className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Отделение</label>
            <select id="department" aria-label="Отделение" className="w-full px-3 py-2 rounded-lg focus:ring-2" style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
              <option>Все отделения</option>
              <option>Кардиология</option>
              <option>Дерматология</option>
              <option>Стоматология</option>
              <option>Общее</option>
            </select>
          </div>
          <div>
            <label htmlFor="doctor" className="block text-sm font-medium mb-1" style={{ color: 'var(--text-primary)' }}>Врач</label>
            <select id="doctor" aria-label="Врач" className="w-full px-3 py-2 rounded-lg focus:ring-2" style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
              <option>Все врачи</option>
              <option>Иванов И.И.</option>
              <option>Петров П.П.</option>
            </select>
          </div>
          <div className="flex items-end">
            <Button className="w-full" aria-label="Применить фильтры">
              <Filter className="w-4 h-4 mr-2" />
              Применить
            </Button>
          </div>
        </div>

        {/* Ключевые метрики */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-blue-50 p-4 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-blue-600">Всего записей</p>
                <p className="text-2xl font-bold text-blue-900">1,247</p>
              </div>
              <Calendar className="w-8 h-8 text-blue-500" />
            </div>
            <p className="text-xs text-blue-600 mt-1">+12% за месяц</p>
          </div>
          
          <div className="bg-green-50 p-4 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-green-600">Доходы</p>
                <p className="text-2xl font-bold text-green-900">₽2.4M</p>
              </div>
              <CreditCard className="w-8 h-8 text-green-500" />
            </div>
            <p className="text-xs text-green-600 mt-1">+8% за месяц</p>
          </div>
          
          <div className="bg-purple-50 p-4 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-purple-600">Пациенты</p>
                <p className="text-2xl font-bold text-purple-900">892</p>
              </div>
              <Users className="w-8 h-8 text-purple-500" />
            </div>
            <p className="text-xs text-purple-600 mt-1">+15% за месяц</p>
          </div>
          
          <div className="bg-orange-50 p-4 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-orange-600">Средний чек</p>
                <p className="text-2xl font-bold text-orange-900">₽1,925</p>
              </div>
              <TrendingUp className="w-8 h-8 text-orange-500" />
            </div>
            <p className="text-xs text-orange-600 mt-1">+5% за месяц</p>
          </div>
        </div>

        {/* Графики */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="p-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Динамика записей</h3>
            <div className="h-64 bg-gray-50 rounded-lg flex items-center justify-center">
              <p className="text-gray-500">График записей по дням</p>
            </div>
          </Card>
          
          <Card className="p-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Доходы по отделениям</h3>
            <div className="h-64 bg-gray-50 rounded-lg flex items-center justify-center">
              <p className="text-gray-500">Круговая диаграмма доходов</p>
            </div>
          </Card>
        </div>

        {/* Топ врачи */}
        <Card className="p-4 mt-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Топ врачи по количеству приемов</h3>
          <div className="space-y-3">
            {[
              { name: 'Иванов И.И.', department: 'Кардиология', patients: 156, revenue: '₽312,000' },
              { name: 'Петров П.П.', department: 'Дерматология', patients: 134, revenue: '₽268,000' },
              { name: 'Сидоров С.С.', department: 'Стоматология', patients: 98, revenue: '₽196,000' },
              { name: 'Козлов К.К.', department: 'Общее', patients: 87, revenue: '₽174,000' }
            ].map((doctor, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                    <span className="text-white text-sm font-medium">{index + 1}</span>
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">{doctor.name}</p>
                    <p className="text-sm text-gray-600">{doctor.department}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-medium text-gray-900">{doctor.patients} пациентов</p>
                  <p className="text-sm text-gray-600">{doctor.revenue}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </Card>
    </div>
  );

  const renderContent = () => {
    switch (current) {
      case 'dashboard':
        return renderDashboard();
      case 'analytics':
        return renderAnalytics();
      case 'users':
        return renderUsers();
      case 'doctors':
        return renderDoctors();
      case 'patients':
        return renderPatients();
      case 'appointments':
        return renderAppointments();
      case 'finance':
        return renderFinance();
      case 'reports':
        return renderReports();
      case 'settings':
        return renderSettings();
      case 'security':
        return renderSecurity();
      default:
        return (
          <Card className="p-12">
            <div className="text-center">
              <h2 className="text-2xl font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
                {tabs.find(tab => tab.id === current)?.label || 'Неизвестный раздел'}
              </h2>
              <p style={{ color: 'var(--text-secondary)' }}>Этот раздел находится в разработке</p>
            </div>
          </Card>
        );
    }
  };

  // Заглушки для остальных разделов
  const renderDoctors = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Управление врачами</h2>
          <Button onClick={handleCreateDoctor}>
            <Plus className="w-4 h-4 mr-2" />
            Добавить врача
          </Button>
        </div>
        
        {/* Поиск и фильтры */}
        <div className="flex items-center space-x-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-tertiary)' }} />
            <input
              type="text"
              placeholder="Поиск врачей..."
              value={doctorsSearchTerm}
              onChange={(e) => setDoctorsSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg focus:ring-2"
              style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
            />
          </div>
          <input
            type="text"
            placeholder="Специализация..."
            value={filterSpecialization}
            onChange={(e) => setFilterSpecialization(e.target.value)}
            className="px-3 py-2 rounded-lg border focus:ring-2"
            style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
          />
          <select
            value={filterDepartment}
            onChange={(e) => setFilterDepartment(e.target.value)}
            className="px-3 py-2 rounded-lg border focus:ring-2"
            style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
          >
            <option value="">Все отделения</option>
            <option value="cardiology">Кардиология</option>
            <option value="dermatology">Дерматология</option>
            <option value="dentistry">Стоматология</option>
            <option value="general">Общее</option>
            <option value="surgery">Хирургия</option>
            <option value="pediatrics">Педиатрия</option>
            <option value="neurology">Неврология</option>
          </select>
          <select
            value={doctorsFilterStatus}
            onChange={(e) => setDoctorsFilterStatus(e.target.value)}
            className="px-3 py-2 rounded-lg border focus:ring-2"
            style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
          >
            <option value="">Все статусы</option>
            <option value="active">Активен</option>
            <option value="inactive">Неактивен</option>
            <option value="on_leave">В отпуске</option>
          </select>
        </div>

        {/* Таблица врачей */}
        <div className="overflow-x-auto">
          {doctorsLoading ? (
            <LoadingSkeleton type="table" count={5} />
          ) : doctorsError ? (
            <EmptyState
              type="error"
              title="Ошибка загрузки врачей"
              description="Не удалось загрузить список врачей"
              action={
                <Button onClick={() => window.location.reload()}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Обновить
                </Button>
              }
            />
          ) : doctors.length === 0 ? (
            <EmptyState
              type="users"
              title="Врачи не найдены"
              description={doctorsSearchTerm || filterSpecialization || filterDepartment || doctorsFilterStatus 
                ? "Попробуйте изменить параметры поиска" 
                : "В системе пока нет врачей"
              }
              action={
                <Button onClick={handleCreateDoctor}>
                  <Plus className="w-4 h-4 mr-2" />
                  Добавить первого врача
                </Button>
              }
            />
          ) : (
            <table className="w-full" role="table" aria-label="Таблица врачей">
              <thead>
                <tr className="border-b" style={{ borderColor: 'var(--border-color)' }}>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Врач</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Специализация</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Отделение</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Опыт</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Статус</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Пациенты</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Действия</th>
                </tr>
              </thead>
              <tbody>
                {doctors.map((doctor) => (
                  <tr key={doctor.id} className="border-b hover:bg-gray-50" style={{ borderColor: 'var(--border-color)' }}>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ background: 'var(--accent-color)' }}>
                          <span className="text-white text-sm font-medium">
                            {doctor.name.split(' ').map(n => n[0]).join('').toUpperCase()}
                          </span>
                        </div>
                        <div>
                          <p className="font-medium" style={{ color: 'var(--text-primary)' }}>{doctor.name}</p>
                          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{doctor.email}</p>
                          {doctor.phone && (
                            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{doctor.phone}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant="info">
                        {doctor.specialization}
                      </Badge>
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant="success">
                        {getDepartmentLabel(doctor.department)}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
                      {doctor.experience} лет
                    </td>
                    <td className="py-3 px-4">
                      <Badge 
                        variant={doctor.status === 'active' ? 'success' : doctor.status === 'inactive' ? 'warning' : 'info'}
                      >
                        {getDoctorStatusLabel(doctor.status)}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
                      {doctor.patientsCount} пациентов
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        <button 
                          onClick={() => handleEditDoctor(doctor)}
                          className="p-1 hover:bg-gray-100 rounded transition-colors" 
                          style={{ color: 'var(--text-secondary)' }}
                          title="Редактировать"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => handleDeleteDoctor(doctor)}
                          className="p-1 hover:bg-red-100 rounded transition-colors" 
                          style={{ color: 'var(--danger-color)' }}
                          title="Удалить"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </Card>

      {/* Модальное окно врача */}
      <DoctorModal
        isOpen={showDoctorModal}
        onClose={handleCloseDoctorModal}
        doctor={selectedDoctor}
        onSave={handleSaveDoctor}
        loading={doctorModalLoading}
      />
    </div>
  );

  const renderPatients = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Управление пациентами</h2>
          <Button onClick={handleCreatePatient}>
            <Plus className="w-4 h-4 mr-2" />
            Добавить пациента
          </Button>
        </div>
        
        {/* Поиск и фильтры */}
        <div className="flex items-center space-x-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-tertiary)' }} />
            <input
              type="text"
              placeholder="Поиск пациентов..."
              value={patientsSearchTerm}
              onChange={(e) => setPatientsSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg focus:ring-2"
              style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
            />
          </div>
          <select
            value={filterGender}
            onChange={(e) => setFilterGender(e.target.value)}
            className="px-3 py-2 rounded-lg border focus:ring-2"
            style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
          >
            <option value="">Все полы</option>
            <option value="male">Мужской</option>
            <option value="female">Женский</option>
          </select>
          <select
            value={filterAgeRange}
            onChange={(e) => setFilterAgeRange(e.target.value)}
            className="px-3 py-2 rounded-lg border focus:ring-2"
            style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
          >
            <option value="">Все возрасты</option>
            <option value="0-18">0-18 лет</option>
            <option value="19-35">19-35 лет</option>
            <option value="36-50">36-50 лет</option>
            <option value="51-65">51-65 лет</option>
            <option value="65+">65+ лет</option>
          </select>
          <select
            value={filterBloodType}
            onChange={(e) => setFilterBloodType(e.target.value)}
            className="px-3 py-2 rounded-lg border focus:ring-2"
            style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
          >
            <option value="">Все группы крови</option>
            <option value="A+">A+</option>
            <option value="A-">A-</option>
            <option value="B+">B+</option>
            <option value="B-">B-</option>
            <option value="AB+">AB+</option>
            <option value="AB-">AB-</option>
            <option value="O+">O+</option>
            <option value="O-">O-</option>
          </select>
        </div>

        {/* Таблица пациентов */}
        <div className="overflow-x-auto">
          {patientsLoading ? (
            <LoadingSkeleton type="table" count={5} />
          ) : patientsError ? (
            <EmptyState
              type="error"
              title="Ошибка загрузки пациентов"
              description="Не удалось загрузить список пациентов"
              action={
                <Button onClick={() => window.location.reload()}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Обновить
                </Button>
              }
            />
          ) : patients.length === 0 ? (
            <EmptyState
              type="users"
              title="Пациенты не найдены"
              description={patientsSearchTerm || filterGender || filterAgeRange || filterBloodType 
                ? "Попробуйте изменить параметры поиска" 
                : "В системе пока нет пациентов"
              }
              action={
                <Button onClick={handleCreatePatient}>
                  <Plus className="w-4 h-4 mr-2" />
                  Добавить первого пациента
                </Button>
              }
            />
          ) : (
            <table className="w-full" role="table" aria-label="Таблица пациентов">
              <thead>
                <tr className="border-b" style={{ borderColor: 'var(--border-color)' }}>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Пациент</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Возраст</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Пол</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Телефон</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Группа крови</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Последний визит</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Визиты</th>
                  <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Действия</th>
                </tr>
              </thead>
              <tbody>
                {patients.map((patient) => (
                  <tr key={patient.id} className="border-b hover:bg-gray-50" style={{ borderColor: 'var(--border-color)' }}>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ background: 'var(--accent-color)' }}>
                          <span className="text-white text-sm font-medium">
                            {patient.firstName[0]}{patient.lastName[0]}
                          </span>
                        </div>
                        <div>
                          <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
                            {patient.lastName} {patient.firstName} {patient.middleName}
                          </p>
                          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                            {patient.email || 'Email не указан'}
                          </p>
                          {patient.address && (
                            <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                              {patient.address}
                            </p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
                      {calculateAge(patient.birthDate)} лет
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant={patient.gender === 'male' ? 'info' : 'success'}>
                        {getGenderLabel(patient.gender)}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
                      {patient.phone}
                    </td>
                    <td className="py-3 px-4">
                      {patient.bloodType ? (
                        <Badge variant="warning">
                          {patient.bloodType}
                        </Badge>
                      ) : (
                        <span className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Не указано</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
                      {patient.lastVisit ? new Date(patient.lastVisit).toLocaleDateString('ru-RU') : 'Нет визитов'}
                    </td>
                    <td className="py-3 px-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
                      {patient.visitsCount} визитов
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        <button 
                          onClick={() => handleEditPatient(patient)}
                          className="p-1 hover:bg-gray-100 rounded transition-colors" 
                          style={{ color: 'var(--text-secondary)' }}
                          title="Редактировать"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => handleDeletePatient(patient)}
                          className="p-1 hover:bg-red-100 rounded transition-colors" 
                          style={{ color: 'var(--danger-color)' }}
                          title="Удалить"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </Card>

      {/* Модальное окно пациента */}
      <PatientModal
        isOpen={showPatientModal}
        onClose={handleClosePatientModal}
        patient={selectedPatient}
        onSave={handleSavePatient}
        loading={patientModalLoading}
      />
    </div>
  );

  const renderAppointments = () => {
    const statusStats = getStatusStats();
    const todayAppointments = getTodayAppointments();
    const tomorrowAppointments = getTomorrowAppointments();

    return (
      <div className="space-y-6">
        {/* Статистика записей */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Всего записей</p>
                <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{appointments.length}</p>
              </div>
              <Calendar className="w-8 h-8" style={{ color: 'var(--accent-color)' }} />
            </div>
          </Card>
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>На сегодня</p>
                <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{todayAppointments.length}</p>
              </div>
              <Clock className="w-8 h-8" style={{ color: 'var(--success-color)' }} />
            </div>
          </Card>
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>На завтра</p>
                <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{tomorrowAppointments.length}</p>
              </div>
              <Calendar className="w-8 h-8" style={{ color: 'var(--info-color)' }} />
            </div>
          </Card>
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Ожидают</p>
                <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{statusStats.pending}</p>
              </div>
              <Clock className="w-8 h-8" style={{ color: 'var(--warning-color)' }} />
            </div>
          </Card>
        </div>

        <Card className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>Управление записями</h2>
            <Button onClick={handleCreateAppointment}>
              <Plus className="w-4 h-4 mr-2" />
              Создать запись
            </Button>
          </div>
          
          {/* Поиск и фильтры */}
          <div className="flex items-center space-x-4 mb-6">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-tertiary)' }} />
              <input
                type="text"
                placeholder="Поиск записей..."
                value={appointmentsSearchTerm}
                onChange={(e) => setAppointmentsSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-lg focus:ring-2"
                style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
              />
            </div>
            <select
              value={appointmentFilterStatus}
              onChange={(e) => setAppointmentFilterStatus(e.target.value)}
              className="px-3 py-2 rounded-lg border focus:ring-2"
              style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
            >
              <option value="">Все статусы</option>
              <option value="pending">Ожидает</option>
              <option value="confirmed">Подтверждена</option>
              <option value="paid">Оплачена</option>
              <option value="in_visit">На приеме</option>
              <option value="completed">Завершена</option>
              <option value="cancelled">Отменена</option>
              <option value="no_show">Не явился</option>
            </select>
            <input
              type="date"
              value={appointmentFilterDate}
              onChange={(e) => setAppointmentFilterDate(e.target.value)}
              className="px-3 py-2 rounded-lg border focus:ring-2"
              style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
            />
            <select
              value={appointmentFilterDoctor}
              onChange={(e) => setAppointmentFilterDoctor(e.target.value)}
              className="px-3 py-2 rounded-lg border focus:ring-2"
              style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
            >
              <option value="">Все врачи</option>
              {doctors.map(doctor => (
                <option key={doctor.id} value={doctor.id}>
                  {doctor.name}
                </option>
              ))}
            </select>
          </div>

          {/* Таблица записей */}
          <div className="overflow-x-auto">
            {appointmentsLoading ? (
              <LoadingSkeleton type="table" count={5} />
            ) : appointmentsError ? (
              <EmptyState
                type="error"
                title="Ошибка загрузки записей"
                description="Не удалось загрузить список записей"
                action={
                  <Button onClick={() => window.location.reload()}>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Обновить
                  </Button>
                }
              />
            ) : appointments.length === 0 ? (
              <EmptyState
                type="calendar"
                title="Записи не найдены"
                description={appointmentsSearchTerm || appointmentFilterStatus || appointmentFilterDate || appointmentFilterDoctor 
                  ? "Попробуйте изменить параметры поиска" 
                  : "В системе пока нет записей"
                }
                action={
                  <Button onClick={handleCreateAppointment}>
                    <Plus className="w-4 h-4 mr-2" />
                    Создать первую запись
                  </Button>
                }
              />
            ) : (
              <table className="w-full" role="table" aria-label="Таблица записей">
                <thead>
                  <tr className="border-b" style={{ borderColor: 'var(--border-color)' }}>
                    <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Пациент</th>
                    <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Врач</th>
                    <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Дата и время</th>
                    <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Статус</th>
                    <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Причина</th>
                    <th scope="col" className="text-left py-3 px-4 font-medium" style={{ color: 'var(--text-primary)' }}>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {appointments.map((appointment) => (
                    <tr key={appointment.id} className="border-b hover:bg-gray-50" style={{ borderColor: 'var(--border-color)' }}>
                      <td className="py-3 px-4">
                        <div className="flex items-center space-x-3">
                          <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'var(--accent-color)' }}>
                            <span className="text-white text-sm font-medium">
                              {appointment.patientName.split(' ').map(n => n[0]).join('').toUpperCase()}
                            </span>
                          </div>
                          <div>
                            <p className="font-medium" style={{ color: 'var(--text-primary)' }}>{appointment.patientName}</p>
                            {appointment.phone && (
                              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{appointment.phone}</p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div>
                          <p className="font-medium" style={{ color: 'var(--text-primary)' }}>{appointment.doctorName}</p>
                          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{appointment.doctorSpecialization}</p>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div>
                          <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
                            {new Date(appointment.appointmentDate).toLocaleDateString('ru-RU')}
                          </p>
                          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                            {appointment.appointmentTime} ({appointment.duration} мин)
                          </p>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={getAppointmentStatusVariant(appointment.status)}>
                          {getAppointmentStatusLabel(appointment.status)}
                        </Badge>
                      </td>
                      <td className="py-3 px-4">
                        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                          {appointment.reason.length > 50 
                            ? `${appointment.reason.substring(0, 50)}...` 
                            : appointment.reason
                          }
                        </p>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center space-x-2">
                          <button 
                            onClick={() => handleEditAppointment(appointment)}
                            className="p-1 hover:bg-gray-100 rounded transition-colors" 
                            style={{ color: 'var(--text-secondary)' }}
                            title="Редактировать"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button 
                            onClick={() => handleDeleteAppointment(appointment)}
                            className="p-1 hover:bg-red-100 rounded transition-colors" 
                            style={{ color: 'var(--danger-color)' }}
                            title="Удалить"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </Card>

        {/* Модальное окно записи */}
        <AppointmentModal
          isOpen={showAppointmentModal}
          onClose={handleCloseAppointmentModal}
          appointment={selectedAppointment}
          onSave={handleSaveAppointment}
          loading={appointmentModalLoading}
          doctors={doctors}
          patients={patients}
        />
      </div>
    );
  };

  const renderFinance = () => (
    <EmptyState
      type="creditcard"
      title="Финансовый учет"
      description="Здесь будет интерфейс для управления финансами клиники"
      action={
        <Button variant="primary">
          <CreditCard className="w-4 h-4 mr-2" />
          Создать транзакцию
        </Button>
      }
    />
  );

  const renderReports = () => (
    <EmptyState
      type="filetext"
      title="Отчеты и аналитика"
      description="Здесь будет интерфейс для создания и просмотра отчетов"
      action={
        <Button variant="primary">
          <FileText className="w-4 h-4 mr-2" />
          Создать отчет
        </Button>
      }
    />
  );

  const renderSettings = () => (
    <EmptyState
      type="settings"
      title="Настройки системы"
      description="Здесь будут настройки конфигурации системы"
      action={
        <Button variant="primary">
          <Settings className="w-4 h-4 mr-2" />
          Открыть настройки
        </Button>
      }
    />
  );

  const renderSecurity = () => (
    <EmptyState
      type="shield"
      title="Безопасность"
      description="Здесь будут настройки безопасности и доступа"
      action={
        <Button variant="primary">
          <Shield className="w-4 h-4 mr-2" />
          Настроить безопасность
        </Button>
      }
    />
  );

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-7xl mx-auto space-y-6">
          <Skeleton className="h-8 w-64" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            {[...Array(6)].map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Skeleton className="h-80" />
            <Skeleton className="h-80" />
          </div>
        </div>
      </div>
    );
  }

  const pageStyle = {
    minHeight: '100vh',
    background: theme === 'light' 
      ? 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)'
      : 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
    padding: 0,
    margin: 0,
    fontFamily: 'system-ui, -apple-system, sans-serif'
  };

  const containerStyle = {
    maxWidth: '1400px',
    margin: '0 auto',
    padding: `${getSpacing('xl')} ${getSpacing('lg')}`
  };

  return (
    <div style={pageStyle}>
      <div style={containerStyle}>
        {/* Заголовок страницы (внутри контента) */}
        <div style={{ marginBottom: getSpacing('xl') }}>
          <h1 style={{ 
            fontSize: getFontSize('3xl'),
            fontWeight: '700',
            color: 'var(--text-primary)',
            marginBottom: getSpacing('xs'),
            background: 'linear-gradient(135deg, var(--accent-color) 0%, #1d4ed8 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text'
          }}>
            🏥 Панель администратора
          </h1>
          <p style={{ 
            fontSize: getFontSize('lg'),
            color: 'var(--text-secondary)',
            fontWeight: '400'
          }}>
            Управление системой клиники
          </p>
        </div>
        
        {/* Навигация */}
        <AdminNavigation sections={navigationSections} />

        {/* Основной контент */}
        <div style={{ opacity: fadeIn ? 1 : 0, transform: slideIn ? 'translateY(0)' : 'translateY(20px)' }}>
          {renderContent()}
        </div>
      </div>
    </div>
  );
};

export default AdminPanel;
