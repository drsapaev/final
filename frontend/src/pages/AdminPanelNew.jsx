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
  RefreshCw,
  Package,
  Brain,
  MessageSquare,
  Monitor,
  Key,
  DollarSign,
  Receipt,
  X,
  TrendingDown,
  XCircle,
  Globe,
  AlertCircle
} from 'lucide-react';

// Новые унифицированные компоненты
import UnifiedLayout from '../components/layout/UnifiedLayout';
import { MedicalCard, MetricCard, MedicalTable } from '../components/medical';
import { useTheme } from '../contexts/ThemeContext';

/**
 * Обновленная админ панель с унифицированным дизайном
 */
const AdminPanelNew = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { isDark } = useTheme();
  
  const [current, setCurrent] = useState('dashboard');
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Моковые данные для демонстрации
  const [dashboardData, setDashboardData] = useState({
    totalUsers: 1247,
    totalPatients: 3421,
    totalRevenue: 2847500,
    totalAppointments: 156,
    growthRate: 12.5,
    activeUsers: 89,
    newPatients: 234,
    completedAppointments: 120,
    pendingAppointments: 36
  });

  const [recentUsers] = useState([
    {
      id: 1,
      name: 'Dr. John Smith',
      email: 'john.smith@clinic.com',
      role: 'Doctor',
      status: 'active',
      lastLogin: '2 hours ago',
      department: 'Cardiology'
    },
    {
      id: 2,
      name: 'Sarah Johnson',
      email: 'sarah.johnson@clinic.com',
      role: 'Nurse',
      status: 'active',
      lastLogin: '1 hour ago',
      department: 'Emergency'
    },
    {
      id: 3,
      name: 'Mike Wilson',
      email: 'mike.wilson@clinic.com',
      role: 'Admin',
      status: 'inactive',
      lastLogin: '1 day ago',
      department: 'Administration'
    }
  ]);

  const [recentPatients] = useState([
    {
      id: 1,
      name: 'Alice Brown',
      patientId: 'P001234',
      age: 45,
      gender: 'F',
      lastVisit: '2024-01-15',
      department: 'Cardiology',
      status: 'active'
    },
    {
      id: 2,
      name: 'Bob Davis',
      patientId: 'P001235',
      age: 32,
      gender: 'M',
      lastVisit: '2024-01-14',
      department: 'Dermatology',
      status: 'active'
    },
    {
      id: 3,
      name: 'Carol White',
      patientId: 'P001236',
      age: 28,
      gender: 'F',
      lastVisit: '2024-01-13',
      department: 'Pediatrics',
      status: 'pending'
    }
  ]);

  // Определяем текущую вкладку из URL
  useEffect(() => {
    const path = location.pathname;
    if (path.includes('/admin/users')) setCurrent('users');
    else if (path.includes('/admin/analytics')) setCurrent('analytics');
    else if (path.includes('/admin/settings')) setCurrent('settings');
    else setCurrent('dashboard');
  }, [location.pathname]);

  // Рендер дашборда
  const renderDashboard = () => (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
            Dashboard
          </h1>
          <p className="text-gray-600" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>
            Overview of your medical clinic
          </p>
        </div>
        <div className="flex gap-3">
          <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
            <Plus className="h-4 w-4 mr-2" />
            Add New
          </button>
        </div>
      </div>

      {/* Основные метрики */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Total Users"
          value={dashboardData.totalUsers.toLocaleString()}
          change={dashboardData.growthRate}
          icon={Users}
          color="blue"
        />
        <MetricCard
          title="Total Patients"
          value={dashboardData.totalPatients.toLocaleString()}
          change={8.2}
          icon={Users}
          color="green"
        />
        <MetricCard
          title="Revenue"
          value={`$${(dashboardData.totalRevenue / 1000000).toFixed(1)}M`}
          change={15.7}
          icon={DollarSign}
          color="purple"
        />
        <MetricCard
          title="Appointments"
          value={dashboardData.totalAppointments}
          change={-2.1}
          icon={Calendar}
          color="orange"
        />
      </div>

      {/* Дополнительные метрики */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <MetricCard
          title="Active Users"
          value={dashboardData.activeUsers}
          icon={Activity}
          color="green"
        />
        <MetricCard
          title="New Patients"
          value={dashboardData.newPatients}
          icon={UserPlus}
          color="blue"
        />
        <MetricCard
          title="Completed Appointments"
          value={dashboardData.completedAppointments}
          icon={CheckCircle}
          color="green"
        />
      </div>

      {/* Таблицы */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Последние пользователи */}
        <MedicalCard>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
              Recent Users
            </h3>
            <button 
              className="text-blue-600 hover:text-blue-800 text-sm"
              onClick={() => setCurrent('users')}
            >
              View All
            </button>
          </div>
          <MedicalTable
            columns={[
              { key: 'name', label: 'Name' },
              { key: 'role', label: 'Role' },
              { key: 'department', label: 'Department' },
              { 
                key: 'status', 
                label: 'Status',
                render: (value) => (
                  <span 
                    className={`px-2 py-1 rounded-full text-xs ${
                      value === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {value}
                  </span>
                )
              }
            ]}
            data={recentUsers.slice(0, 5)}
            onView={(user) => console.log('View user:', user)}
            onEdit={(user) => console.log('Edit user:', user)}
            onDelete={(user) => console.log('Delete user:', user)}
            pagination={false}
          />
        </MedicalCard>

        {/* Последние пациенты */}
        <MedicalCard>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
              Recent Patients
            </h3>
            <button 
              className="text-blue-600 hover:text-blue-800 text-sm"
              onClick={() => setCurrent('patients')}
            >
              View All
            </button>
          </div>
          <MedicalTable
            columns={[
              { key: 'name', label: 'Name' },
              { key: 'patientId', label: 'ID' },
              { key: 'department', label: 'Department' },
              { 
                key: 'status', 
                label: 'Status',
                render: (value) => (
                  <span 
                    className={`px-2 py-1 rounded-full text-xs ${
                      value === 'active' ? 'bg-green-100 text-green-800' : 
                      value === 'pending' ? 'bg-yellow-100 text-yellow-800' : 
                      'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {value}
                  </span>
                )
              }
            ]}
            data={recentPatients.slice(0, 5)}
            onView={(patient) => console.log('View patient:', patient)}
            onEdit={(patient) => console.log('Edit patient:', patient)}
            onDelete={(patient) => console.log('Delete patient:', patient)}
            pagination={false}
          />
        </MedicalCard>
      </div>
    </div>
  );

  // Рендер пользователей
  const renderUsers = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
            Users Management
          </h1>
          <p className="text-gray-600" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>
            Manage clinic staff and users
          </p>
        </div>
        <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
          <Plus className="h-4 w-4 mr-2" />
          Add User
        </button>
      </div>

      <MedicalCard>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search users..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                style={{
                  backgroundColor: isDark ? '#1e293b' : '#ffffff',
                  borderColor: isDark ? '#334155' : '#d1d5db',
                  color: isDark ? '#f8fafc' : '#374151'
                }}
              />
            </div>
            <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
              <Filter className="h-4 w-4 mr-2" />
              Filter
            </button>
          </div>
        </div>

        <MedicalTable
          columns={[
            { key: 'name', label: 'Name' },
            { key: 'email', label: 'Email' },
            { key: 'role', label: 'Role' },
            { key: 'department', label: 'Department' },
            { key: 'lastLogin', label: 'Last Login' },
            { 
              key: 'status', 
              label: 'Status',
              render: (value) => (
                <span 
                  className={`px-2 py-1 rounded-full text-xs ${
                    value === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {value}
                </span>
              )
            }
          ]}
          data={recentUsers}
          onView={(user) => console.log('View user:', user)}
          onEdit={(user) => console.log('Edit user:', user)}
          onDelete={(user) => console.log('Delete user:', user)}
        />
      </MedicalCard>
    </div>
  );

  // Рендер аналитики
  const renderAnalytics = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
            Analytics
          </h1>
          <p className="text-gray-600" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>
            Clinic performance and insights
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <MedicalCard>
          <h3 className="text-lg font-semibold mb-4" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
            Revenue Overview
          </h3>
          <div className="h-64 flex items-center justify-center text-gray-500">
            <BarChart3 className="h-16 w-16" />
            <span className="ml-2">Chart placeholder</span>
          </div>
        </MedicalCard>

        <MedicalCard>
          <h3 className="text-lg font-semibold mb-4" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
            Patient Demographics
          </h3>
          <div className="h-64 flex items-center justify-center text-gray-500">
            <Users className="h-16 w-16" />
            <span className="ml-2">Chart placeholder</span>
          </div>
        </MedicalCard>
      </div>
    </div>
  );

  // Рендер настроек
  const renderSettings = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
            Settings
          </h1>
          <p className="text-gray-600" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>
            Configure clinic settings
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <MedicalCard>
          <h3 className="text-lg font-semibold mb-4" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
            General Settings
          </h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: isDark ? '#f8fafc' : '#374151' }}>
                Clinic Name
              </label>
              <input
                type="text"
                defaultValue="MediLab Clinic"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                style={{
                  backgroundColor: isDark ? '#1e293b' : '#ffffff',
                  borderColor: isDark ? '#334155' : '#d1d5db',
                  color: isDark ? '#f8fafc' : '#374151'
                }}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-2" style={{ color: isDark ? '#f8fafc' : '#374151' }}>
                Time Zone
              </label>
              <select
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                style={{
                  backgroundColor: isDark ? '#1e293b' : '#ffffff',
                  borderColor: isDark ? '#334155' : '#d1d5db',
                  color: isDark ? '#f8fafc' : '#374151'
                }}
              >
                <option>UTC+3 (Moscow)</option>
                <option>UTC+0 (London)</option>
                <option>UTC-5 (New York)</option>
              </select>
            </div>
          </div>
        </MedicalCard>

        <MedicalCard>
          <h3 className="text-lg font-semibold mb-4" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
            Security Settings
          </h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span style={{ color: isDark ? '#f8fafc' : '#374151' }}>Two-Factor Authentication</span>
              <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                Enable
              </button>
            </div>
            <div className="flex items-center justify-between">
              <span style={{ color: isDark ? '#f8fafc' : '#374151' }}>Session Timeout</span>
              <select
                className="px-3 py-2 border border-gray-300 rounded-lg"
                style={{
                  backgroundColor: isDark ? '#1e293b' : '#ffffff',
                  borderColor: isDark ? '#334155' : '#d1d5db',
                  color: isDark ? '#f8fafc' : '#374151'
                }}
              >
                <option>30 minutes</option>
                <option>1 hour</option>
                <option>2 hours</option>
              </select>
            </div>
          </div>
        </MedicalCard>
      </div>
    </div>
  );

  // Основной рендер контента
  const renderContent = () => {
    switch (current) {
      case 'dashboard':
        return renderDashboard();
      case 'users':
        return renderUsers();
      case 'analytics':
        return renderAnalytics();
      case 'settings':
        return renderSettings();
      default:
        return renderDashboard();
    }
  };

  return (
    <UnifiedLayout showSidebar={true}>
      {renderContent()}
    </UnifiedLayout>
  );
};

export default AdminPanelNew;
