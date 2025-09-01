import React, { useState, useEffect } from 'react';
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
  ChevronUp
} from 'lucide-react';
import { Card, Badge, Button, Skeleton } from '../design-system/components';
import { useBreakpoint, useTouchDevice, useTheme } from '../design-system/hooks';
import { useFade, useSlide, useScale } from '../design-system/hooks/useAnimation';

const AdminPanel = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState({
    totalUsers: 0,
    totalDoctors: 0,
    totalPatients: 0,
    totalRevenue: 0,
    appointmentsToday: 0,
    pendingApprovals: 0
  });
  const [recentActivities, setRecentActivities] = useState([]);
  const [systemAlerts, setSystemAlerts] = useState([]);
  
  const breakpoint = useBreakpoint();
  const isTouchDevice = useTouchDevice();
  const { theme, toggleTheme } = useTheme();
  
  // Анимации
  const { isVisible: fadeIn, fadeIn: startFadeIn } = useFade(false);
  const { isVisible: slideIn, slideIn: startSlideIn } = useSlide(false, 'up');
  const { isVisible: scaleIn, scaleIn: startScaleIn } = useScale(false);

  useEffect(() => {
    // Симуляция загрузки данных
    const loadData = async () => {
      setIsLoading(true);
      
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      setStats({
        totalUsers: 1247,
        totalDoctors: 23,
        totalPatients: 8921,
        totalRevenue: 1250000,
        appointmentsToday: 156,
        pendingApprovals: 8
      });
      
      setRecentActivities([
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
      
      setSystemAlerts([
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
      
      setIsLoading(false);
      
      // Запуск анимаций
      startFadeIn(500);
      startSlideIn(600);
      startScaleIn(700);
    };
    
    loadData();
  }, [startFadeIn, startSlideIn, startScaleIn]);

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'UZS',
      minimumFractionDigits: 0
    }).format(amount);
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-yellow-500" />;
      case 'error':
        return <AlertTriangle className="w-4 h-4 text-red-500" />;
      case 'info':
        return <Clock className="w-4 h-4 text-blue-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const tabs = [
    { id: 'dashboard', label: 'Панель управления', icon: BarChart3 },
    { id: 'users', label: 'Пользователи', icon: Users },
    { id: 'doctors', label: 'Врачи', icon: UserPlus },
    { id: 'patients', label: 'Пациенты', icon: Users },
    { id: 'appointments', label: 'Записи', icon: Calendar },
    { id: 'finance', label: 'Финансы', icon: CreditCard },
    { id: 'reports', label: 'Отчеты', icon: FileText },
    { id: 'settings', label: 'Настройки', icon: Settings },
    { id: 'security', label: 'Безопасность', icon: Shield }
  ];

  const renderDashboard = () => (
    <div className="space-y-6">
      {/* Статистика */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Всего пользователей</p>
              <p className="text-2xl font-bold text-gray-900">{stats.totalUsers}</p>
            </div>
            <Users className="w-8 h-8 text-blue-500" />
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Врачи</p>
              <p className="text-2xl font-bold text-gray-900">{stats.totalDoctors}</p>
            </div>
            <UserPlus className="w-8 h-8 text-green-500" />
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Пациенты</p>
              <p className="text-2xl font-bold text-gray-900">{stats.totalPatients}</p>
            </div>
            <Users className="w-8 h-8 text-purple-500" />
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Доход</p>
              <p className="text-2xl font-bold text-gray-900">{formatCurrency(stats.totalRevenue)}</p>
            </div>
            <TrendingUp className="w-8 h-8 text-green-500" />
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Записи сегодня</p>
              <p className="text-2xl font-bold text-gray-900">{stats.appointmentsToday}</p>
            </div>
            <Calendar className="w-8 h-8 text-orange-500" />
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Ожидают одобрения</p>
              <p className="text-2xl font-bold text-gray-900">{stats.pendingApprovals}</p>
            </div>
            <Clock className="w-8 h-8 text-yellow-500" />
          </div>
        </Card>
      </div>

      {/* Графики и аналитика */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Активность системы</h3>
            <Button variant="outline" size="sm">
              <Download className="w-4 h-4 mr-2" />
              Экспорт
            </Button>
          </div>
          <div className="h-64 bg-gray-50 rounded-lg flex items-center justify-center">
            <div className="text-center">
              <Activity className="w-12 h-12 text-gray-400 mx-auto mb-2" />
              <p className="text-gray-500">График активности</p>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Последние действия</h3>
            <Button variant="outline" size="sm">
              <Eye className="w-4 h-4 mr-2" />
              Все
            </Button>
          </div>
          <div className="space-y-3">
            {recentActivities.map((activity) => (
              <div key={activity.id} className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                {getStatusIcon(activity.status)}
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900">{activity.message}</p>
                  <p className="text-xs text-gray-500">{activity.user} • {activity.time}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Системные уведомления */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Системные уведомления</h3>
          <Badge variant="warning">{systemAlerts.length}</Badge>
        </div>
        <div className="space-y-3">
          {systemAlerts.map((alert) => (
            <div key={alert.id} className="flex items-center space-x-3 p-3 border border-gray-200 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-yellow-500" />
              <div className="flex-1">
                <p className="text-sm font-medium text-gray-900">{alert.message}</p>
                <p className="text-xs text-gray-500">{alert.time}</p>
              </div>
              <Badge variant={alert.priority === 'high' ? 'error' : alert.priority === 'medium' ? 'warning' : 'info'}>
                {alert.priority}
              </Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );

  const renderUsers = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">Управление пользователями</h2>
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            Добавить пользователя
          </Button>
        </div>
        
        <div className="flex items-center space-x-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Поиск пользователей..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <Button variant="outline">
            <Filter className="w-4 h-4 mr-2" />
            Фильтры
          </Button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-medium text-gray-900">Пользователь</th>
                <th className="text-left py-3 px-4 font-medium text-gray-900">Роль</th>
                <th className="text-left py-3 px-4 font-medium text-gray-900">Статус</th>
                <th className="text-left py-3 px-4 font-medium text-gray-900">Последний вход</th>
                <th className="text-left py-3 px-4 font-medium text-gray-900">Действия</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-gray-100">
                <td className="py-3 px-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                      <span className="text-white text-sm font-medium">АА</span>
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">Ахмедов Алишер</p>
                      <p className="text-sm text-gray-500">ahmedov@clinic.uz</p>
                    </div>
                  </div>
                </td>
                <td className="py-3 px-4">
                  <Badge variant="success">Администратор</Badge>
                </td>
                <td className="py-3 px-4">
                  <Badge variant="success">Активен</Badge>
                </td>
                <td className="py-3 px-4 text-sm text-gray-500">2 минуты назад</td>
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

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return renderDashboard();
      case 'users':
        return renderUsers();
      default:
        return (
          <Card className="p-12">
            <div className="text-center">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">
                {tabs.find(tab => tab.id === activeTab)?.label}
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

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Заголовок */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center space-x-4">
              <Building2 className="w-8 h-8 text-blue-600" />
              <div>
                <h1 className="text-xl font-semibold text-gray-900">Панель администратора</h1>
                <p className="text-sm text-gray-500">Управление системой клиники</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              <Button variant="outline" size="sm" onClick={toggleTheme}>
                {theme === 'dark' ? '☀️' : '🌙'}
              </Button>
              <Button variant="outline" size="sm">
                <Bell className="w-4 h-4" />
              </Button>
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-medium">АА</span>
                </div>
                <span className="text-sm font-medium text-gray-900">Администратор</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Навигация */}
        <div className="mb-6">
          <div className="flex flex-wrap gap-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <Button
                  key={tab.id}
                  variant={activeTab === tab.id ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setActiveTab(tab.id)}
                  className="flex items-center space-x-2"
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                </Button>
              );
            })}
          </div>
        </div>

        {/* Основной контент */}
        <div style={{ opacity: fadeIn ? 1 : 0, transform: slideIn ? 'translateY(0)' : 'translateY(20px)' }}>
          {renderContent()}
        </div>
      </div>
    </div>
  );
};

export default AdminPanel;
