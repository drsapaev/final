import React, { useEffect, useRef, useState } from 'react';
import { Chart, registerables } from 'chart.js';
import { Card, Button } from '../ui/native';
import { 
  Download, 
  RefreshCw, 
  BarChart3, 
  PieChart, 
  TrendingUp, 
  Activity,
  Target,
  Users,
  DollarSign,
  Calendar,
  Eye,
  Filter
} from 'lucide-react';

// Регистрируем все компоненты Chart.js
Chart.register(...registerables);

/**
 * Продвинутые графики для аналитики
 * Включает интерактивные диаграммы, анимации, фильтры
 */
const AdvancedCharts = ({ 
  data, 
  loading = false, 
  onRefresh,
  onExport,
  title = 'Продвинутая аналитика',
  showFilters = true
}) => {
  const chartRefs = useRef({});
  const [activeTab, setActiveTab] = useState('overview');
  const [chartType, setChartType] = useState('line');
  const [timeRange, setTimeRange] = useState('30d');
  const [selectedMetrics, setSelectedMetrics] = useState(['revenue', 'visits', 'patients']);

  useEffect(() => {
    if (data?.charts) {
      renderAdvancedCharts();
    }
  }, [data, activeTab, chartType, timeRange, selectedMetrics]);

  const renderAdvancedCharts = () => {
    if (!data?.charts) return;

    // Уничтожаем существующие графики
    Object.values(chartRefs.current).forEach(chart => {
      if (chart) chart.destroy();
    });
    chartRefs.current = {};

    // Рендерим новые графики с продвинутыми настройками
    for (const [chartName, chartConfig] of Object.entries(data.charts)) {
      const canvasId = `advanced-chart-${chartName}`;
      const canvas = document.getElementById(canvasId);
      
      if (canvas) {
        const ctx = canvas.getContext('2d');
        
        // Добавляем продвинутые настройки
        const advancedConfig = {
          ...chartConfig,
          options: {
            ...chartConfig.options,
            responsive: true,
            maintainAspectRatio: false,
            animation: {
              duration: 2000,
              easing: 'easeInOutQuart'
            },
            interaction: {
              intersect: false,
              mode: 'index'
            },
            plugins: {
              ...chartConfig.options?.plugins,
              legend: {
                position: 'top',
                labels: {
                  usePointStyle: true,
                  padding: 20
                }
              },
              tooltip: {
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                titleColor: 'white',
                bodyColor: 'white',
                borderColor: 'rgba(255, 255, 255, 0.1)',
                borderWidth: 1,
                cornerRadius: 8,
                displayColors: true,
                callbacks: {
                  title: function(context) {
                    return context[0].label;
                  },
                  label: function(context) {
                    const label = context.dataset.label || '';
                    const value = context.parsed.y || context.parsed;
                    return `${label}: ${value.toLocaleString()}`;
                  }
                }
              }
            }
          }
        };

        chartRefs.current[chartName] = new Chart(ctx, advancedConfig);
      }
    }
  };

  const getChartIcon = (chartType) => {
    const iconStyle = { width: '16px', height: '16px' };
    switch (chartType) {
      case 'line': return <TrendingUp style={iconStyle} />;
      case 'bar': return <BarChart3 style={iconStyle} />;
      case 'doughnut': return <PieChart style={iconStyle} />;
      case 'radar': return <Activity style={iconStyle} />;
      case 'scatter': return <Target style={iconStyle} />;
      default: return <BarChart3 style={iconStyle} />;
    }
  };

  const renderChartCard = (chartName, chartConfig) => {
    const canvasId = `advanced-chart-${chartName}`;
    
    return (
      <Card key={chartName} className="w-full">
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              {getChartIcon(chartConfig.type)}
              <h3 className="text-lg font-semibold">
                {chartConfig.options?.plugins?.title?.text || chartName}
              </h3>
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onExport?.(chartName)}
              >
                <Download className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onRefresh?.(chartName)}
              >
                <RefreshCw className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
        <div className="p-4">
          <div className="h-80 w-full">
            <canvas id={canvasId}></canvas>
          </div>
        </div>
      </Card>
    );
  };

  const renderFilters = () => {
    if (!showFilters) return null;

    return (
      <Card className="p-4 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4" />
            <span className="text-sm font-medium">Фильтры:</span>
          </div>
          
          <select
            value={chartType}
            onChange={(e) => setChartType(e.target.value)}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm"
          >
            <option value="line">Линейный</option>
            <option value="bar">Столбчатый</option>
            <option value="doughnut">Круговая</option>
            <option value="radar">Радар</option>
            <option value="scatter">Точечная</option>
          </select>

          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm"
          >
            <option value="7d">7 дней</option>
            <option value="30d">30 дней</option>
            <option value="90d">90 дней</option>
            <option value="1y">1 год</option>
          </select>

          <div className="flex items-center space-x-2">
            <span className="text-sm">Метрики:</span>
            {['revenue', 'visits', 'patients', 'doctors'].map(metric => (
              <label key={metric} className="flex items-center space-x-1">
                <input
                  type="checkbox"
                  checked={selectedMetrics.includes(metric)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedMetrics([...selectedMetrics, metric]);
                    } else {
                      setSelectedMetrics(selectedMetrics.filter(m => m !== metric));
                    }
                  }}
                  className="rounded"
                />
                <span className="text-sm capitalize">{metric}</span>
              </label>
            ))}
          </div>
        </div>
      </Card>
    );
  };

  const renderTabContent = (tabData, tabName) => {
    if (!tabData || !tabData.charts) return null;

    const charts = Object.entries(tabData.charts);
    
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {charts.map(([chartName, chartConfig]) => 
          renderChartCard(chartName, chartConfig)
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <Card className="w-full">
        <div className="p-8 text-center">
          <div className="flex items-center justify-center space-x-2">
            <RefreshCw className="w-5 h-5 animate-spin" />
            <span>Загрузка продвинутых графиков...</span>
          </div>
        </div>
      </Card>
    );
  }

  if (!data || !data.charts) {
    return (
      <Card className="w-full">
        <div className="p-8 text-center">
          <BarChart3 className="w-12 h-12 mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Нет данных для отображения
          </h3>
          <p className="text-gray-500 mb-4">
            Выберите период и параметры для загрузки аналитики
          </p>
          <Button onClick={() => onRefresh?.()}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Загрузить данные
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Фильтры */}
      {renderFilters()}

      {/* Навигация по вкладкам */}
      {Object.keys(data.charts).length > 1 && (
        <div className="border-b border-gray-200">
          <nav className="flex space-x-8">
            {[
              { id: 'overview', label: 'Обзор', icon: Eye },
              { id: 'kpi', label: 'KPI', icon: Target },
              { id: 'doctors', label: 'Врачи', icon: Users },
              { id: 'revenue', label: 'Доходы', icon: DollarSign },
              { id: 'appointments', label: 'Записи', icon: Calendar }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>
      )}

      {/* Контент вкладок */}
      <div className="space-y-6">
        {activeTab === 'overview' && renderTabContent(data.charts.overview || data, 'overview')}
        {activeTab === 'kpi' && renderTabContent(data.charts.kpi, 'kpi')}
        {activeTab === 'doctors' && renderTabContent(data.charts.doctors, 'doctors')}
        {activeTab === 'revenue' && renderTabContent(data.charts.revenue, 'revenue')}
        {activeTab === 'appointments' && renderTabContent(data.charts.appointments, 'appointments')}
      </div>
    </div>
  );
};

export default AdvancedCharts;

