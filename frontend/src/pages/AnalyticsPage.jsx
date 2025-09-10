import React, { useState, useEffect } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { api } from '../api/client';
import AnalyticsChart from '../components/AnalyticsChart';
import AnalyticsMetrics from '../components/AnalyticsMetrics';
import AnalyticsCharts from '../components/AnalyticsCharts';
import { 
  Calendar, 
  TrendingUp, 
  Users, 
  DollarSign, 
  Activity,
  Download,
  Filter,
  RefreshCw,
  BarChart3
} from 'lucide-react';

export default function AnalyticsPage() {
  const { isDark, isLight, getColor, getSpacing } = useTheme();
  const [loading, setLoading] = useState(false);
  const [dateRange, setDateRange] = useState({
    start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    end: new Date().toISOString().split('T')[0]
  });
  const [department, setDepartment] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const [data, setData] = useState({
    overview: null,
    appointments: null,
    revenue: null,
    providers: null,
    visualization: null
  });

  const loadAnalytics = async (tab = activeTab) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        start_date: dateRange.start,
        end_date: dateRange.end
      });
      
      if (department) {
        params.append('department', department);
      }

      let response;
      switch (tab) {
        case 'overview':
          response = await api.get(`/analytics/dashboard?${params}`);
          break;
        case 'appointments':
          response = await api.get(`/analytics/appointment-flow?${params}`);
          break;
        case 'revenue':
          response = await api.get(`/analytics/revenue-breakdown?${params}`);
          break;
        case 'providers':
          response = await api.get(`/analytics/payment-providers?${params}`);
          break;
        case 'visualization':
          response = await api.get(`/analytics/visualization/comprehensive?${params}`);
          break;
        default:
          response = await api.get(`/analytics/dashboard?${params}`);
      }
      
      setData(prev => ({ ...prev, [tab]: response }));
    } catch (error) {
      console.error('Ошибка загрузки аналитики:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAnalytics();
  }, [dateRange, department]);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    if (!data[tab]) {
      loadAnalytics(tab);
    }
  };

  const exportData = async (format = 'json') => {
    try {
      const params = new URLSearchParams({
        start_date: dateRange.start,
        end_date: dateRange.end,
        format: format
      });
      
      if (department) {
        params.append('department', department);
      }

      const response = await api.get(`/analytics/export/comprehensive/export/${format}?${params}`, {
        responseType: 'blob'
      });
      
      const blob = new Blob([response], { 
        type: format === 'json' ? 'application/json' : 
              format === 'csv' ? 'text/csv' :
              format === 'pdf' ? 'application/pdf' :
              'application/octet-stream'
      });
      
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `analytics_${dateRange.start}_${dateRange.end}.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Ошибка экспорта:', error);
    }
  };

  const renderOverviewTab = () => {
    if (!data.overview) return <div>Загрузка...</div>;
    
    const { today, week, month } = data.overview;
    
    const metrics = [
      {
        label: 'Визиты сегодня',
        value: today.visits?.total_visits || 0,
        type: 'visits',
        icon: <Calendar size={16} />
      },
      {
        label: 'Доходы сегодня',
        value: today.revenue?.total_revenue || 0,
        type: 'revenue',
        format: 'revenue',
        icon: <DollarSign size={16} />
      },
      {
        label: 'Пациенты за месяц',
        value: month.patients?.total_patients || 0,
        type: 'patients',
        icon: <Users size={16} />
      },
      {
        label: 'Конверсия',
        value: month.visits?.completion_rate || 0,
        type: 'conversion',
        format: 'percentage',
        icon: <TrendingUp size={16} />
      }
    ];

    return (
      <div>
        <AnalyticsMetrics metrics={metrics} />
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '24px'
        }}>
          <AnalyticsChart
            title="Визиты по дням недели"
            data={Object.entries(month.visits?.day_stats || {}).map(([day, count]) => ({
              label: day,
              value: count
            }))}
            type="bar"
            color="#3b82f6"
          />
          
          <AnalyticsChart
            title="Доходы по отделениям"
            data={Object.entries(month.revenue?.department_stats || {}).map(([dept, stats]) => ({
              label: dept,
              value: stats.total_revenue || 0
            }))}
            type="pie"
          />
        </div>
      </div>
    );
  };

  const renderAppointmentsTab = () => {
    if (!data.appointments) return <div>Загрузка...</div>;
    
    const { summary, status_distribution, conversion_rates } = data.appointments;
    
    const metrics = [
      {
        label: 'Всего записей',
        value: summary.total_appointments,
        type: 'visits',
        icon: <Calendar size={16} />
      },
      {
        label: 'Оплачено',
        value: summary.paid_appointments,
        type: 'visits',
        icon: <DollarSign size={16} />
      },
      {
        label: 'Завершено',
        value: summary.completed_appointments,
        type: 'visits',
        icon: <Activity size={16} />
      },
      {
        label: 'Конверсия',
        value: conversion_rates.overall_conversion,
        type: 'conversion',
        format: 'percentage',
        icon: <TrendingUp size={16} />
      }
    ];

    return (
      <div>
        <AnalyticsMetrics metrics={metrics} />
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '24px'
        }}>
          <AnalyticsChart
            title="Распределение по статусам"
            data={Object.entries(status_distribution).map(([status, count]) => ({
              label: status,
              value: count
            }))}
            type="pie"
          />
          
          <AnalyticsChart
            title="Конверсия по воронке"
            data={[
              { label: 'Запись → Оплата', value: conversion_rates.pending_to_paid },
              { label: 'Оплата → Завершение', value: conversion_rates.paid_to_completed },
              { label: 'Общая конверсия', value: conversion_rates.overall_conversion }
            ]}
            type="bar"
            color="#10b981"
          />
        </div>
      </div>
    );
  };

  const renderRevenueTab = () => {
    if (!data.revenue) return <div>Загрузка...</div>;
    
    const { total_revenue, total_transactions, average_transaction, daily_revenue } = data.revenue;
    
    const metrics = [
      {
        label: 'Общий доход',
        value: total_revenue,
        type: 'revenue',
        format: 'revenue',
        icon: <DollarSign size={16} />
      },
      {
        label: 'Транзакций',
        value: total_transactions,
        type: 'visits',
        icon: <Activity size={16} />
      },
      {
        label: 'Средний чек',
        value: average_transaction,
        type: 'revenue',
        format: 'revenue',
        icon: <TrendingUp size={16} />
      }
    ];

    return (
      <div>
        <AnalyticsMetrics metrics={metrics} />
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '24px'
        }}>
          <AnalyticsChart
            title="Доходы по дням"
            data={daily_revenue.map(item => ({
              label: new Date(item.date).toLocaleDateString('ru-RU', { 
                month: 'short', 
                day: 'numeric' 
              }),
              value: item.amount
            }))}
            type="line"
            color="#10b981"
          />
          
          <AnalyticsChart
            title="Доходы по провайдерам"
            data={Object.entries(data.revenue.provider_breakdown || {}).map(([provider, stats]) => ({
              label: provider,
              value: stats.total_amount
            }))}
            type="bar"
            color="#8b5cf6"
          />
        </div>
      </div>
    );
  };

  const renderProvidersTab = () => {
    if (!data.providers) return <div>Загрузка...</div>;
    
    const { summary, providers } = data.providers;
    
    const metrics = [
      {
        label: 'Активных провайдеров',
        value: summary.active_providers,
        type: 'visits',
        icon: <Activity size={16} />
      },
      {
        label: 'Всего транзакций',
        value: summary.total_transactions,
        type: 'visits',
        icon: <TrendingUp size={16} />
      },
      {
        label: 'Общий доход',
        value: summary.total_revenue,
        type: 'revenue',
        format: 'revenue',
        icon: <DollarSign size={16} />
      },
      {
        label: 'Комиссия',
        value: summary.total_commission,
        type: 'revenue',
        format: 'revenue',
        icon: <DollarSign size={16} />
      }
    ];

    return (
      <div>
        <AnalyticsMetrics metrics={metrics} />
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '24px'
        }}>
          <AnalyticsChart
            title="Доходы по провайдерам"
            data={Object.entries(providers).map(([code, stats]) => ({
              label: stats.name,
              value: stats.total_amount
            }))}
            type="pie"
          />
          
          <AnalyticsChart
            title="Успешность провайдеров"
            data={Object.entries(providers).map(([code, stats]) => ({
              label: stats.name,
              value: stats.success_rate
            }))}
            type="bar"
            color="#10b981"
          />
        </div>
      </div>
    );
  };

  return (
    <div style={{ padding: getSpacing('lg') }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: getSpacing('lg')
      }}>
        <h1 style={{
          fontSize: '24px',
          fontWeight: '700',
          color: getColor('primary', 900),
          margin: 0
        }}>
          Аналитика и отчёты
        </h1>
        
        <div style={{ display: 'flex', gap: getSpacing('md'), alignItems: 'center' }}>
          <button
            onClick={exportData}
            style={{
              padding: '8px 16px',
              background: 'var(--accent-color)',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <Download size={16} />
            Экспорт
          </button>
        </div>
      </div>

      {/* Фильтры */}
      <div style={{
        background: 'var(--bg-primary)',
        border: '1px solid var(--border-color)',
        borderRadius: '12px',
        padding: getSpacing('lg'),
        marginBottom: getSpacing('lg'),
        display: 'flex',
        gap: getSpacing('md'),
        alignItems: 'center',
        flexWrap: 'wrap'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Calendar size={16} color="var(--text-secondary)" />
          <input
            type="date"
            value={dateRange.start}
            onChange={(e) => setDateRange(prev => ({ ...prev, start: e.target.value }))}
            style={{
              padding: '8px',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              background: 'var(--bg-primary)',
              color: 'var(--text-primary)'
            }}
          />
          <span style={{ color: 'var(--text-secondary)' }}>—</span>
          <input
            type="date"
            value={dateRange.end}
            onChange={(e) => setDateRange(prev => ({ ...prev, end: e.target.value }))}
            style={{
              padding: '8px',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              background: 'var(--bg-primary)',
              color: 'var(--text-primary)'
            }}
          />
        </div>
        
        <select
          value={department}
          onChange={(e) => setDepartment(e.target.value)}
          style={{
            padding: '8px',
            border: '1px solid var(--border-color)',
            borderRadius: '6px',
            background: 'var(--bg-primary)',
            color: 'var(--text-primary)'
          }}
        >
          <option value="">Все отделения</option>
          <option value="General">Общее</option>
          <option value="Cardiology">Кардиология</option>
          <option value="Dermatology">Дерматология</option>
          <option value="Dentistry">Стоматология</option>
        </select>
        
        <button
          onClick={() => loadAnalytics()}
          disabled={loading}
          style={{
            padding: '8px 16px',
            background: loading ? 'var(--bg-secondary)' : 'var(--accent-color)',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: loading ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Обновить
        </button>
      </div>

      {/* Вкладки */}
      <div style={{
        display: 'flex',
        gap: '8px',
        marginBottom: getSpacing('lg'),
        borderBottom: '1px solid var(--border-color)'
      }}>
        {[
          { id: 'overview', label: 'Обзор', icon: <Activity size={16} /> },
          { id: 'appointments', label: 'Записи', icon: <Calendar size={16} /> },
          { id: 'revenue', label: 'Доходы', icon: <DollarSign size={16} /> },
          { id: 'providers', label: 'Провайдеры', icon: <TrendingUp size={16} /> },
          { id: 'visualization', label: 'Графики', icon: <BarChart3 size={16} /> }
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => handleTabChange(tab.id)}
            style={{
              padding: '12px 20px',
              background: activeTab === tab.id ? 'var(--accent-color)' : 'transparent',
              color: activeTab === tab.id ? 'white' : 'var(--text-primary)',
              border: 'none',
              borderRadius: '8px 8px 0 0',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontWeight: '500',
              transition: 'all 0.2s ease'
            }}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Контент */}
      {loading ? (
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '200px',
          color: 'var(--text-secondary)'
        }}>
          <RefreshCw size={24} className="animate-spin" />
          <span style={{ marginLeft: '12px' }}>Загрузка данных...</span>
        </div>
      ) : (
        <>
          {activeTab === 'overview' && renderOverviewTab()}
          {activeTab === 'appointments' && renderAppointmentsTab()}
          {activeTab === 'revenue' && renderRevenueTab()}
          {activeTab === 'providers' && renderProvidersTab()}
          {activeTab === 'visualization' && (
            <AnalyticsCharts
              data={data.visualization}
              loading={loading}
              onRefresh={() => loadAnalytics('visualization')}
              onExport={() => exportData('json')}
              title="Интерактивные графики аналитики"
            />
          )}
        </>
      )}
    </div>
  );
}

