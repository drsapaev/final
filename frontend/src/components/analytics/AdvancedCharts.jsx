import { useEffect, useRef, useState, useCallback } from 'react';
import PropTypes from 'prop-types';
import { Chart, registerables } from 'chart.js';
import { Card, Button,
  Checkbox } from '../ui/macos';
import {
import { useTranslation } from '../../i18n/useTranslation';
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
  Filter } from
'lucide-react';

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
  title = t('misc.ac_prodvinutaya_analitika'),
  showFilters = true
}) => {
  const { t } = useTranslation();
  void title;
  const chartRefs = useRef({});
  const [activeTab, setActiveTab] = useState('overview');
  const [chartType, setChartType] = useState('line');
  const [timeRange, setTimeRange] = useState('30d');
  const [selectedMetrics, setSelectedMetrics] = useState(['revenue', 'visits', 'patients']);

  const renderAdvancedCharts = useCallback(() => {
    if (!data?.charts) return;

    // Уничтожаем существующие графики
    Object.values(chartRefs.current).forEach((chart) => {
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
                borderColor: 'color-mix(in srgb, white, transparent 90%)',
                borderWidth: 1,
                cornerRadius: 8,
                displayColors: true,
                callbacks: {
                  title: function (context) {
                    return context[0].label;
                  },
                  label: function (context) {
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
  }, [data]);

  useEffect(() => {
    if (data?.charts) {
      renderAdvancedCharts();
    }
  }, [data, activeTab, chartType, timeRange, selectedMetrics, renderAdvancedCharts]);

  const getChartIcon = (chartType) => {
    const iconStyle = { width: '16px', height: '16px' };
    switch (chartType) {
      case 'line':return <TrendingUp style={iconStyle} />;
      case 'bar':return <BarChart3 style={iconStyle} />;
      case 'doughnut':return <PieChart style={iconStyle} />;
      case 'radar':return <Activity style={iconStyle} />;
      case 'scatter':return <Target style={iconStyle} />;
      default:return <BarChart3 style={iconStyle} />;
    }
  };

  const renderChartCard = (chartName, chartConfig) => {
    const canvasId = `advanced-chart-${chartName}`;
    const chartLabel = chartConfig.options?.plugins?.title?.text || chartName;

    return (
      <Card key={chartName} className="w-full">
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              {getChartIcon(chartConfig.type)}
              <h3 className="text-lg font-semibold">
                {chartLabel}
              </h3>
            </div>
            <div className="flex items-center space-x-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                title={`Export ${chartLabel}`}
                aria-label={`Export ${chartLabel}`}
                onClick={() => onExport?.(chartName)}>

                <Download aria-hidden="true" className="w-4 h-4" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                title={`Refresh ${chartLabel}`}
                aria-label={`Refresh ${chartLabel}`}
                onClick={() => onRefresh?.(chartName)}>

                <RefreshCw aria-hidden="true" className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
        <div className="p-4">
          <div className="h-80 w-full">
            <canvas
              id={canvasId}
              role="img"
              aria-label={`${chartConfig.title || chartName} chart`}
            ></canvas>
          </div>
        </div>
      </Card>);

  };

  const renderFilters = () => {
    if (!showFilters) return null;

    return (
      <Card className="p-4 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4" />
            <span className="text-sm font-medium">{t('misc.ac_filtry')}</span>
          </div>
          
          <select
            value={chartType}
            onChange={(e) => setChartType(e.target.value)}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm">
            
            <option value="line">{t('misc.ac_lineynyy')}</option>
            <option value="bar">{t('misc.ac_stolbchatyy')}</option>
            <option value="doughnut">{t('misc.ac_krugovaya')}</option>
            <option value="radar">{t('misc.ac_radar')}</option>
            <option value="scatter">{t('misc.ac_tochechnaya')}</option>
          </select>

          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm">
            
            <option value="7d">7 дней</option>
            <option value="30d">30 дней</option>
            <option value="90d">90 дней</option>
            <option value="1y">1 год</option>
          </select>

          <div className="flex items-center space-x-2">
            <span className="text-sm">{t('misc.ac_metriki')}</span>
            {['revenue', 'visits', 'patients', 'doctors'].map((metric) =>
            <label key={metric} className="flex items-center space-x-1">
                <Checkbox aria-label={`Toggle ${metric} metric`} checked={selectedMetrics.includes(metric)} onChange={(e) => {
                  if (e.target.checked) {
                    setSelectedMetrics([...selectedMetrics, metric]);
                  } else {
                    setSelectedMetrics(selectedMetrics.filter((m) => m !== metric));
                  }
                }}
                className="rounded" />
              
                <span className="text-sm capitalize">{metric}</span>
              </label>
            )}
          </div>
        </div>
      </Card>);

  };

  const renderTabContent = (tabData) => {
    if (!tabData || !tabData.charts) return null;

    const charts = Object.entries(tabData.charts);

    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {charts.map(([chartName, chartConfig]) =>
        renderChartCard(chartName, chartConfig)
        )}
      </div>);

  };

  if (loading) {
    return (
      <Card className="w-full">
        <div className="p-8 text-center">
          <div className="flex items-center justify-center space-x-2">
            <RefreshCw className="w-5 h-5 animate-spin" />
            <span>{t('misc.ac_zagruzka_prodvinutyh_grafiko')}</span>
          </div>
        </div>
      </Card>);

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
      </Card>);

  }

  return (
    <div className="space-y-6">
      {/* Фильтры */}
      {renderFilters()}

      {/* Навигация по вкладкам */}
      {Object.keys(data.charts).length > 1 &&
      <div className="border-b border-gray-200">
          <nav className="flex space-x-8">
            {[
          { id: 'overview', label: t('misc.ac_obzor'), icon: Eye },
          { id: 'kpi', label: 'KPI', icon: Target },
          { id: 'doctors', label: t('misc.ac_vrachi'), icon: Users },
          { id: 'revenue', label: t('misc.ac_dohody'), icon: DollarSign },
          { id: 'appointments', label: t('misc.ac_zapisi'), icon: Calendar }].
          map((tab) =>
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
            activeTab === tab.id ?
            'border-blue-500 text-blue-600' :
            'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}`
            }>
            
                <tab.icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
          )}
          </nav>
        </div>
      }

      {/* Контент вкладок */}
      <div className="space-y-6">
        {activeTab === 'overview' && renderTabContent(data.charts.overview || data, 'overview')}
        {activeTab === 'kpi' && renderTabContent(data.charts.kpi, 'kpi')}
        {activeTab === 'doctors' && renderTabContent(data.charts.doctors, 'doctors')}
        {activeTab === 'revenue' && renderTabContent(data.charts.revenue, 'revenue')}
        {activeTab === 'appointments' && renderTabContent(data.charts.appointments, 'appointments')}
      </div>
    </div>);

};

AdvancedCharts.propTypes = {
  data: PropTypes.object,
  loading: PropTypes.bool,
  onRefresh: PropTypes.func,
  onExport: PropTypes.func,
  title: PropTypes.node,
  showFilters: PropTypes.bool
};

export default AdvancedCharts;
