
import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import Chart from 'chart.js/auto';
import type { ChartConfiguration } from 'chart.js';
import { Card, Button,
  Checkbox } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import i18n from '../../i18n';
import {
  Download,
  RefreshCw,
  BarChart3,
  PieChart,
  TrendingUp,
  Activity,
  Target,
  Filter } from
'lucide-react';

const t18 = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;

/**
 * Продвинутые графики для аналитики
 * Включает интерактивные диаграммы, анимации, фильтры
 */
interface AdvancedChartsProps {
  data?: Record<string, unknown> | null;
  loading?: boolean;
  onRefresh?: (chartName?: string) => void;
  onExport?: (chartName?: string) => void;
  title?: string;
  showFilters?: boolean;
}

type ChartConfigData = Record<string, unknown>;
type ChartGroups = Record<string, Record<string, ChartConfigData>>;

interface ChartEntry {
  id: string;
  name: string;
  config: ChartConfigData;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const isChartConfig = (value: unknown): value is ChartConfigData =>
  isRecord(value) && typeof value.type === 'string' && isRecord(value.data);

/** Accept the comprehensive API's category groups and the legacy flat chart map. */
const getChartGroups = (data?: Record<string, unknown> | null): ChartGroups => {
  if (!isRecord(data?.charts)) return {};

  const groups: ChartGroups = {};
  for (const [groupName, groupValue] of Object.entries(data.charts)) {
    if (!isRecord(groupValue)) continue;

    if (isChartConfig(groupValue)) {
      (groups.overview ??= {})[groupName] = groupValue;
      continue;
    }

    const group: Record<string, ChartConfigData> = {};
    for (const [chartName, config] of Object.entries(groupValue)) {
      if (isChartConfig(config)) group[chartName] = config;
    }
    if (Object.keys(group).length > 0) groups[groupName] = group;
  }

  return groups;
};

const AdvancedCharts = ({
  data,
  loading = false,
  onRefresh,
  onExport,
  title = t18('misc.ac_prodvinutaya_analitika'),
  showFilters = true
}: AdvancedChartsProps) => {
  useTranslation();
  void title;
  const chartRefs = useRef<Record<string, { destroy: () => void }>>({});
  const [activeTab, setActiveTab] = useState('overview');
  const [chartType, setChartType] = useState('line');
  const [timeRange, setTimeRange] = useState('30d');
  const [selectedMetrics, setSelectedMetrics] = useState(['revenue', 'visits', 'patients']);
  const chartGroups = useMemo(() => getChartGroups(data), [data]);
  const visibleTab = activeTab === 'overview' || chartGroups[activeTab] ? activeTab : 'overview';
  const visibleCharts = useMemo<ChartEntry[]>(() => {
    const entries: ChartEntry[] = [];
    const groups = visibleTab === 'overview'
      ? Object.entries(chartGroups)
      : [[visibleTab, chartGroups[visibleTab] ?? {}] as [string, Record<string, ChartConfigData>]];

    for (const [groupName, charts] of groups) {
      for (const [chartName, config] of Object.entries(charts)) {
        entries.push({ id: groupName + ':' + chartName, name: chartName, config });
      }
    }
    return entries;
  }, [chartGroups, visibleTab]);

  const renderAdvancedCharts = useCallback(() => {
    // Уничтожаем существующие графики
    Object.values(chartRefs.current).forEach((chart) => {
      if (chart) (chart as { destroy: () => void }).destroy();
    });
    chartRefs.current = {};

    // Рендерим новые графики с продвинутыми настройками
    for (const { id, config: chartConfig } of visibleCharts) {
      const canvasId = 'advanced-chart-' + id;
      const canvas = document.getElementById(canvasId);

      if (canvas) {
        const ctx = (canvas as HTMLCanvasElement).getContext('2d');
        if (!ctx) continue;

        // Добавляем продвинутые настройки
        const advancedConfig = {
          ...(chartConfig as Record<string, unknown>),
          options: {
            ...((chartConfig as Record<string, unknown>).options as Record<string, unknown>),
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
              ...(((chartConfig as Record<string, unknown>).options as Record<string, unknown>)?.plugins as Record<string, unknown>),
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
                  title: function (context: Array<{ label?: string }>) {
                    return context[0].label;
                  },
                  label: function (context: { dataset?: { label?: string }; parsed: { y?: number; [key: string]: unknown } }) {
                    const label = context.dataset?.label || '';
                    const value = (context.parsed.y ?? context.parsed) as number;
                    return `${label}: ${value.toLocaleString()}`;
                  }
                }
              }
            }
          }
        };

        chartRefs.current[id] = new Chart(ctx, advancedConfig as unknown as ChartConfiguration) as unknown as { destroy: () => void };
      }
    }
  }, [visibleCharts]);

  useEffect(() => {
    renderAdvancedCharts();
  }, [visibleCharts, chartType, timeRange, selectedMetrics, renderAdvancedCharts]);

  const getChartIcon = (chartType: string) => {
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

  const renderChartCard = (chartId: string, chartName: string, chartConfig: Record<string, unknown>) => {
    const canvasId = 'advanced-chart-' + chartId;
    const opts = (chartConfig.options ?? {}) as Record<string, unknown>;
    const plugins = (opts.plugins ?? {}) as Record<string, unknown>;
    const titleObj = (plugins.title ?? {}) as Record<string, unknown>;
    const chartLabel = (titleObj.text as string | undefined) || chartName;

    return (
      <Card key={chartName} className="w-full">
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              {getChartIcon(String(chartConfig.type))}
              <h3 className="text-lg font-semibold">
                {chartLabel}
              </h3>
            </div>
            <div className="flex items-center space-x-2">
              <Button
                type="button"
                variant="ghost"
                size="small"
                title={`Export ${chartLabel}`}
                aria-label={`Export ${chartLabel}`}
                onClick={() => onExport?.(chartName)}>

                <Download aria-hidden="true" className="w-4 h-4" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="small"
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
              aria-label={`${(chartConfig.title as string | undefined) || chartName} chart`}
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
            <span className="text-sm font-medium">{t18('misc.ac_filtry')}</span>
          </div>

          <select
            value={chartType}
            onChange={(e) => setChartType(e.target.value)}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm">

            <option value="line">{t18('misc.ac_lineynyy')}</option>
            <option value="bar">{t18('misc.ac_stolbchatyy')}</option>
            <option value="doughnut">{t18('misc.ac_krugovaya')}</option>
            <option value="radar">{t18('misc.ac_radar')}</option>
            <option value="scatter">{t18('misc.ac_tochechnaya')}</option>
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
            <span className="text-sm">{t18('misc.ac_metriki')}</span>
            {['revenue', 'visits', 'patients', 'doctors'].map((metric) =>
            <label key={metric} className="flex items-center space-x-1">
                <Checkbox aria-label={`Toggle ${metric} metric`} checked={selectedMetrics.includes(metric)} onChange={(e) => {
                  if (e) {
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

  const renderChartList = (charts: ChartEntry[]) => {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
        {charts.map(({ id, name, config }) => renderChartCard(id, name, config))}
      </div>);

  };

  if (loading) {
    return (
      <Card className="w-full">
        <div className="p-8 text-center">
          <div className="flex items-center justify-center space-x-2">
            <RefreshCw className="w-5 h-5 animate-spin" />
            <span>{t18('misc.ac_zagruzka_prodvinutyh_grafiko')}</span>
          </div>
        </div>
      </Card>);

  }

  if (!data || visibleCharts.length === 0) {
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

  const chartTabs = [
    { id: 'overview', label: t18('misc.ac_obzor') },
    ...Object.keys(chartGroups)
      .filter((groupName) => groupName !== 'overview')
      .map((groupName) => ({
        id: groupName,
        label: groupName === 'kpi' ? 'KPI'
          : groupName === 'doctors' ? t18('misc.ac_vrachi')
          : groupName === 'patients' ? t18('patients')
          : groupName === 'revenue' ? t18('misc.ac_dohody')
          : groupName,
      })),
  ];

  return (
    <div className="space-y-6">
      {/* Фильтры */}
      {renderFilters()}

      {/* Навигация по вкладкам */}
      {chartTabs.length > 1 &&
      <div className="border-b border-gray-200">
          <nav className="flex space-x-8">
            {chartTabs.map((tab) =>
          <button
            key={tab.id}
            type="button"
            aria-pressed={visibleTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
            visibleTab === tab.id ?
            'border-blue-500 text-blue-600' :
            'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}`
            }>

                <span>{tab.label}</span>
              </button>
          )}
          </nav>
        </div>
      }

      {/* Контент вкладок */}
      <div className="space-y-6">
        {renderChartList(visibleCharts)}
      </div>
    </div>);

};


export default AdvancedCharts;
