import React, { useState, useEffect } from 'react';
import { 
  BarChart3, 
  PieChart, 
  TrendingUp, 
  TrendingDown,
  Users, 
  Calendar, 
  DollarSign, 
  FileText, 
  Download, 
  Filter,
  Search,
  RefreshCw,
  Eye,
  Printer,
  Share2,
  Clock,
  CheckCircle,
  AlertCircle,
  XCircle,
  Activity,
  Target,
  Award,
  Star,
  Zap,
  Heart,
  Smile,
  Scissors,
  Pill,
  Camera,
  Stethoscope,
  User,
  Building,
  MapPin,
  Phone,
  Mail,
  Plus,
  Minus,
  ChevronDown,
  ChevronUp,
  Settings,
  MoreHorizontal,
  X
} from 'lucide-react';

/**
 * Отчеты и аналитика для стоматологической ЭМК
 * Включает статистику по пациентам, врачам, клинике, процедурам
 */
const ReportsAndAnalytics = ({ 
  onClose 
}) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [dateRange, setDateRange] = useState('30d');
  const [selectedDoctor, setSelectedDoctor] = useState('all');
  const [selectedProcedure, setSelectedProcedure] = useState('all');
  const [loading, setLoading] = useState(false);

  // Моковые данные для демонстрации
  const [analyticsData, setAnalyticsData] = useState({
      overview: {
        totalPatients: 1247,
        totalAppointments: 3421,
      totalRevenue: 2847500,
      averageRating: 4.8,
      growthRate: 12.5
      },
      patients: {
      newPatients: 89,
      returningPatients: 1158,
      ageGroups: [
          { age: '0-18', count: 234, percentage: 18.8 },
          { age: '19-35', count: 456, percentage: 36.6 },
          { age: '36-50', count: 312, percentage: 25.0 },
          { age: '51-65', count: 189, percentage: 15.2 },
          { age: '65+', count: 56, percentage: 4.5 }
        ],
      genderDistribution: [
          { gender: 'Мужчины', count: 623, percentage: 50.0 },
          { gender: 'Женщины', count: 624, percentage: 50.0 }
      ]
    },
    doctors: [
      {
        id: 1,
        name: 'Иванов И.И.',
        specialty: 'Терапевт',
        patients: 456,
        appointments: 1234,
        revenue: 987500,
        rating: 4.9,
        efficiency: 95
      },
      {
        id: 2,
        name: 'Петрова А.С.',
        specialty: 'Хирург',
        patients: 234,
        appointments: 567,
        revenue: 756300,
        rating: 4.7,
        efficiency: 88
      },
      {
        id: 3,
        name: 'Сидоров В.В.',
        specialty: 'Ортодонт',
        patients: 189,
        appointments: 445,
        revenue: 654200,
        rating: 4.8,
        efficiency: 92
      }
    ],
    procedures: [
      { name: 'Лечение кариеса', count: 1234, revenue: 987500, growth: 15.2 },
      { name: 'Профессиональная гигиена', count: 567, revenue: 234500, growth: 8.7 },
      { name: 'Удаление зуба', count: 234, revenue: 456700, growth: -5.3 },
      { name: 'Протезирование', count: 123, revenue: 567800, growth: 22.1 },
      { name: 'Имплантация', count: 89, revenue: 445600, growth: 18.9 }
    ],
    revenue: {
      monthly: [
        { month: 'Янв', revenue: 234500 },
        { month: 'Фев', revenue: 267800 },
        { month: 'Мар', revenue: 289400 },
        { month: 'Апр', revenue: 312600 },
        { month: 'Май', revenue: 298700 },
        { month: 'Июн', revenue: 325400 }
      ],
      byCategory: [
        { category: 'Терапия', revenue: 987500, percentage: 34.7 },
        { category: 'Хирургия', revenue: 756300, percentage: 26.6 },
        { category: 'Протезирование', revenue: 654200, percentage: 23.0 },
        { category: 'Ортодонтия', revenue: 445600, percentage: 15.7 }
      ]
    },
    appointments: {
      total: 3421,
      completed: 3201,
      cancelled: 156,
      noShow: 64,
      byStatus: [
        { status: 'Завершено', count: 3201, percentage: 93.6 },
        { status: 'Отменено', count: 156, percentage: 4.6 },
        { status: 'Не явился', count: 64, percentage: 1.9 }
      ],
      byDay: [
        { day: 'Пн', count: 456 },
        { day: 'Вт', count: 523 },
        { day: 'Ср', count: 489 },
        { day: 'Чт', count: 567 },
        { day: 'Пт', count: 612 },
        { day: 'Сб', count: 234 },
        { day: 'Вс', count: 140 }
      ]
    }
  });

  // Обработчики
  const handleDateRangeChange = (range) => {
    setDateRange(range);
    // Здесь можно добавить логику загрузки данных для выбранного периода
  };

  const handleExportReport = (type) => {
    setLoading(true);
    // Симуляция экспорта
    setTimeout(() => {
      setLoading(false);
      alert(`Отчет ${type} экспортирован успешно!`);
    }, 2000);
  };

  // Рендер карточки метрики
  const renderMetricCard = (title, value, change, icon, color = 'blue') => (
    <div className="bg-white rounded-lg p-6 shadow-sm border">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          {change && (
            <div className={`flex items-center mt-1 ${
              change > 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {change > 0 ? (
                <TrendingUp className="h-4 w-4 mr-1" />
              ) : (
                <TrendingDown className="h-4 w-4 mr-1" />
              )}
              <span className="text-sm font-medium">{Math.abs(change)}%</span>
            </div>
          )}
        </div>
        <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
          color === 'blue' ? 'bg-blue-100 text-blue-600' :
          color === 'green' ? 'bg-green-100 text-green-600' :
          color === 'purple' ? 'bg-purple-100 text-purple-600' :
          color === 'orange' ? 'bg-orange-100 text-orange-600' :
          'bg-gray-100 text-gray-600'
        }`}>
          {icon}
        </div>
      </div>
    </div>
  );

  // Рендер обзорной вкладки
  const renderOverviewTab = () => (
      <div className="space-y-6">
      {/* Основные метрики */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {renderMetricCard(
            'Всего пациентов',
          analyticsData.overview.totalPatients.toLocaleString(),
          analyticsData.overview.growthRate,
            <Users className="h-6 w-6" />,
            'blue'
          )}
        {renderMetricCard(
            'Записей на прием',
          analyticsData.overview.totalAppointments.toLocaleString(),
          8.2,
            <Calendar className="h-6 w-6" />,
            'green'
          )}
        {renderMetricCard(
            'Выручка',
          `${(analyticsData.overview.totalRevenue / 1000000).toFixed(1)}М ₽`,
          15.7,
            <DollarSign className="h-6 w-6" />,
          'purple'
        )}
        {renderMetricCard(
          'Средняя оценка',
          analyticsData.overview.averageRating,
          0.3,
          <Star className="h-6 w-6" />,
            'orange'
          )}
        </div>

        {/* Графики */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* График выручки */}
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h3 className="text-lg font-semibold mb-4">Выручка по месяцам</h3>
          <div className="h-64 flex items-end justify-between space-x-2">
            {analyticsData.revenue.monthly.map((item, index) => (
              <div key={index} className="flex flex-col items-center">
                <div 
                  className="bg-blue-500 rounded-t w-8 mb-2"
                  style={{ height: `${(item.revenue / 350000) * 200}px` }}
                ></div>
                <span className="text-xs text-gray-600">{item.month}</span>
        </div>
            ))}
          </div>
      </div>

        {/* Распределение по категориям */}
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h3 className="text-lg font-semibold mb-4">Выручка по категориям</h3>
          <div className="space-y-3">
            {analyticsData.revenue.byCategory.map((item, index) => (
              <div key={index} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${
                    index === 0 ? 'bg-blue-500' :
                    index === 1 ? 'bg-green-500' :
                    index === 2 ? 'bg-purple-500' :
                    'bg-orange-500'
                  }`}></div>
                  <span className="text-sm font-medium">{item.category}</span>
        </div>
                <div className="text-right">
                  <div className="text-sm font-semibold">{item.percentage}%</div>
                  <div className="text-xs text-gray-600">{item.revenue.toLocaleString()} ₽</div>
            </div>
            </div>
            ))}
        </div>
      </div>
          </div>

      {/* Статистика записей */}
      <div className="bg-white rounded-lg p-6 shadow-sm border">
        <h3 className="text-lg font-semibold mb-4">Статистика записей</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {analyticsData.appointments.byStatus.map((item, index) => (
            <div key={index} className="text-center">
              <div className="text-2xl font-bold text-gray-900">{item.count}</div>
              <div className="text-sm text-gray-600">{item.status}</div>
              <div className="text-xs text-gray-500">{item.percentage}%</div>
          </div>
          ))}
      </div>
          </div>
      </div>
    );

  // Рендер вкладки пациентов
  const renderPatientsTab = () => (
    <div className="space-y-6">
      {/* Статистика пациентов */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h3 className="text-lg font-semibold mb-4">Возрастные группы</h3>
          <div className="space-y-3">
            {analyticsData.patients.ageGroups.map((group, index) => (
              <div key={index} className="flex items-center justify-between">
                <span className="text-sm font-medium">{group.age} лет</span>
          <div className="flex items-center gap-2">
                  <div className="w-32 bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-blue-500 h-2 rounded-full"
                      style={{ width: `${group.percentage}%` }}
                    ></div>
          </div>
                  <span className="text-sm text-gray-600 w-12 text-right">{group.count}</span>
        </div>
            </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg p-6 shadow-sm border">
          <h3 className="text-lg font-semibold mb-4">Распределение по полу</h3>
          <div className="space-y-4">
            {analyticsData.patients.genderDistribution.map((item, index) => (
              <div key={index} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${
                    index === 0 ? 'bg-blue-500' : 'bg-pink-500'
                  }`}></div>
                  <span className="text-sm font-medium">{item.gender}</span>
              </div>
                <div className="text-right">
                  <div className="text-sm font-semibold">{item.count}</div>
                  <div className="text-xs text-gray-600">{item.percentage}%</div>
            </div>
        </div>
            ))}
      </div>
    </div>
      </div>

      {/* Новые и возвращающиеся пациенты */}
    <div className="bg-white rounded-lg p-6 shadow-sm border">
        <h3 className="text-lg font-semibold mb-4">Типы пациентов</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="text-center">
            <div className="text-3xl font-bold text-green-600 mb-2">
              {analyticsData.patients.newPatients}
            </div>
            <div className="text-sm text-gray-600">Новые пациенты</div>
        </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-blue-600 mb-2">
              {analyticsData.patients.returningPatients}
        </div>
            <div className="text-sm text-gray-600">Возвращающиеся пациенты</div>
      </div>
        </div>
      </div>
    </div>
  );

  // Рендер вкладки врачей
  const renderDoctorsTab = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
        <div className="px-6 py-4 border-b">
          <h3 className="text-lg font-semibold">Статистика врачей</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Врач
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Специальность
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Пациенты
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Записи
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Выручка
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Рейтинг
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Эффективность
                </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
              {analyticsData.doctors.map((doctor) => (
                <tr key={doctor.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                        <User className="h-4 w-4 text-blue-600" />
      </div>
                      <div className="ml-3">
                        <div className="text-sm font-medium text-gray-900">{doctor.name}</div>
    </div>
        </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{doctor.specialty}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{doctor.patients}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{doctor.appointments}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{doctor.revenue.toLocaleString()} ₽</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <Star className="h-4 w-4 text-yellow-400 mr-1" />
                      <span className="text-sm text-gray-900">{doctor.rating}</span>
        </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                        <div 
                          className="bg-green-500 h-2 rounded-full"
                          style={{ width: `${doctor.efficiency}%` }}
                        ></div>
          </div>
                      <span className="text-sm text-gray-900">{doctor.efficiency}%</span>
      </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </div>
      </div>
    );

  // Рендер вкладки процедур
  const renderProceduresTab = () => (
      <div className="space-y-6">
      <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
        <div className="px-6 py-4 border-b">
          <h3 className="text-lg font-semibold">Статистика процедур</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Процедура
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Количество
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Выручка
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Рост
                </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
              {analyticsData.procedures.map((procedure, index) => (
              <tr key={index} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                        index === 0 ? 'bg-blue-100' :
                        index === 1 ? 'bg-green-100' :
                        index === 2 ? 'bg-red-100' :
                        index === 3 ? 'bg-purple-100' :
                        'bg-orange-100'
                      }`}>
                        <Scissors className={`h-4 w-4 ${
                          index === 0 ? 'text-blue-600' :
                          index === 1 ? 'text-green-600' :
                          index === 2 ? 'text-red-600' :
                          index === 3 ? 'text-purple-600' :
                          'text-orange-600'
                        }`} />
      </div>
                      <div className="ml-3">
                        <div className="text-sm font-medium text-gray-900">{procedure.name}</div>
    </div>
        </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{procedure.count}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{procedure.revenue.toLocaleString()} ₽</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className={`flex items-center ${
                      procedure.growth > 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {procedure.growth > 0 ? (
                        <TrendingUp className="h-4 w-4 mr-1" />
                      ) : (
                        <TrendingDown className="h-4 w-4 mr-1" />
                      )}
                      <span className="text-sm font-medium">{Math.abs(procedure.growth)}%</span>
        </div>
                  </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
      </div>
    );

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg w-full max-w-7xl h-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Заголовок */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-xl font-semibold">Отчеты и аналитика</h2>
            <p className="text-gray-600 text-sm">
              Статистика и аналитика работы клиники
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            <select
              value={dateRange}
              onChange={(e) => handleDateRangeChange(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="7d">Последние 7 дней</option>
              <option value="30d">Последние 30 дней</option>
              <option value="90d">Последние 90 дней</option>
              <option value="1y">Последний год</option>
            </select>
            
            <button
              onClick={() => handleExportReport('PDF')}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              <Download className="h-4 w-4" />
              {loading ? 'Экспорт...' : 'Экспорт PDF'}
            </button>
            
            <button
              onClick={onClose}
              className="p-2 text-gray-500 hover:text-gray-700"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Навигация по вкладкам */}
        <div className="border-b">
          <nav className="flex space-x-8 px-6">
            {[
              { id: 'overview', label: 'Обзор', icon: BarChart3 },
              { id: 'patients', label: 'Пациенты', icon: Users },
              { id: 'doctors', label: 'Врачи', icon: User },
              { id: 'procedures', label: 'Процедуры', icon: Scissors }
            ].map((tab) => (
            <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
            </button>
            ))}
          </nav>
        </div>

        {/* Контент */}
        <div className="flex-1 overflow-auto p-6">
          {activeTab === 'overview' && renderOverviewTab()}
          {activeTab === 'patients' && renderPatientsTab()}
          {activeTab === 'doctors' && renderDoctorsTab()}
          {activeTab === 'procedures' && renderProceduresTab()}
        </div>
      </div>
    </div>
  );
};

export default ReportsAndAnalytics;

