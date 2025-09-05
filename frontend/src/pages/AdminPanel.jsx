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
    refreshInterval: 300000, // Обновляем каждые 5 минут
    onError: (error) => {
      console.error('Ошибка загрузки статистики:', error);
    }
  });

  // Статистика по умолчанию (fallback)
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
  const [recentActivities, setRecentActivities] = useState([]);
  const [systemAlerts, setSystemAlerts] = useState([]);
  
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
  if (path === '/admin' || path === '/admin/') current = 'dashboard';
  else if (path.startsWith('/admin/')) {
    const seg = path.split('/')[2] || '';
    current = seg || 'dashboard';
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
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            Добавить пользователя
          </Button>
        </div>
        
        <div className="flex items-center space-x-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-tertiary)' }} />
            <input
              type="text"
              placeholder="Поиск пользователей..."
              className="w-full pl-10 pr-4 py-2 rounded-lg focus:ring-2"
              style={{ border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
            />
          </div>
          <Button variant="outline">
            <Filter className="w-4 h-4 mr-2" />
            Фильтры
          </Button>
        </div>

        <div className="overflow-x-auto">
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
              <tr className="border-b" style={{ borderColor: 'var(--border-color)' }}>
                <td className="py-3 px-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'var(--accent-color)' }}>
                      <span className="text-white text-sm font-medium">АА</span>
                    </div>
                    <div>
                      <p className="font-medium" style={{ color: 'var(--text-primary)' }}>Ахмедов Алишер</p>
                      <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>ahmedov@clinic.uz</p>
                    </div>
                  </div>
                </td>
                <td className="py-3 px-4">
                  <Badge variant="success">Администратор</Badge>
                </td>
                <td className="py-3 px-4">
                  <Badge variant="success">Активен</Badge>
                </td>
                <td className="py-3 px-4 text-sm" style={{ color: 'var(--text-secondary)' }}>2 минуты назад</td>
                <td className="py-3 px-4">
                  <div className="flex items-center space-x-2">
                    <Button variant="ghost" size="sm">
                      <Eye className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="sm">
                      <Edit className="w-4 h-4" />
                    </Button>
                    <Button variant="ghost" size="sm">
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
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
      default:
        return (
          <Card className="p-12">
            <div className="text-center">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">
                {tabs.find(tab => tab.id === current)?.label}
              </h2>
              <p className="text-gray-500">Этот раздел находится в разработке</p>
            </div>
          </Card>
        );
    }
  };

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
