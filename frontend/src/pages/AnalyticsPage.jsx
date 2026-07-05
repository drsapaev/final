import { useState, useEffect, useCallback } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { api } from '../api/client';
import KPIMetrics from '../components/analytics/KPIMetrics';
import AdvancedCharts from '../components/analytics/AdvancedCharts';

import PredictiveAnalytics from '../components/analytics/PredictiveAnalytics';
import AdminRouteSwitcher from '../components/admin/AdminRouteSwitcher';
import {
  Input, Button, Select, SegmentedControl,
} from '../components/ui/macos';
import logger from '../utils/logger';
import {
  Calendar,
  TrendingUp,
  Users,
  DollarSign,
  Activity,
  Download,

  RefreshCw,
  BarChart3,
  Target,
  Building2,
  Wallet,
  ArrowUpRight,
  Clock3 } from
'lucide-react';

const DAY_MS = 24 * 60 * 60 * 1000;

const TAB_DEFINITIONS = [
  { id: 'overview', label: 'Обзор', description: 'Сводка ключевых показателей за выбранный период', icon: Activity },
  { id: 'appointments', label: 'Записи', description: 'Воронка записи, оплат и завершения', icon: Calendar },
  { id: 'revenue', label: 'Доходы', description: 'Динамика выручки и структура оплат', icon: DollarSign },
  { id: 'providers', label: 'Провайдеры', description: 'Сравнение платёжных провайдеров', icon: Wallet },
  { id: 'visualization', label: 'Графики', description: 'Расширенные интерактивные графики', icon: BarChart3 },
  { id: 'kpi', label: 'KPI', description: 'Операционные метрики и эффективность', icon: Target },
  { id: 'predictive', label: 'Прогнозы', description: 'Тренды, сценарии и прогнозы', icon: TrendingUp }
];

const DEPARTMENT_OPTIONS = [
{ value: '', label: 'Все отделения' },
{ value: 'General', label: 'Общее' },
{ value: 'Cardiology', label: 'Кардиология' },
{ value: 'Dermatology', label: 'Дерматология' },
{ value: 'Dentistry', label: 'Стоматология' }];

function buildRelativeDateRange(days) {
  const end = new Date();
  const start = new Date(Date.now() - (days - 1) * DAY_MS);
  return {
    start: start.toISOString().split('T')[0],
    end: end.toISOString().split('T')[0]
  };
}

function formatMetricValue(value, format = 'count') {
  const safeValue = Number.isFinite(Number(value)) ? Number(value) : 0;
  switch (format) {
    case 'revenue':
      return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'UZS',
        maximumFractionDigits: 0
      }).format(safeValue);
    case 'percentage':
      return `${safeValue.toFixed(1)}%`;
    default:
      return new Intl.NumberFormat('ru-RU', {
        maximumFractionDigits: 0
      }).format(safeValue);
  }
}

function getActivePreset(start, end) {
  const startDate = new Date(`${start}T00:00:00`);
  const endDate = new Date(`${end}T00:00:00`);
  const diff = Math.round((endDate - startDate) / DAY_MS) + 1;
  if ([7, 30, 90].includes(diff)) {
    return diff;
  }
  return null;
}

function normalizePairs(source, formatter) {
  return Object.entries(source || {}).map(([key, value]) => formatter(key, value)).filter(Boolean);
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

const analyticsSurface = 'linear-gradient(180deg, color-mix(in srgb, var(--mac-card-bg), white 68%) 0%, color-mix(in srgb, var(--mac-card-bg), white 60%) 100%)';
const analyticsSurfaceStrong = 'linear-gradient(180deg, color-mix(in srgb, var(--mac-card-bg), white 74%) 0%, color-mix(in srgb, var(--mac-card-bg), white 66%) 100%)';
const analyticsBorder = '1px solid color-mix(in srgb, var(--mac-card-border), white 10%)';
const analyticsInsetSurface = 'color-mix(in srgb, var(--mac-card-bg), white 78%)';
const analyticsTextPrimary = 'color-mix(in srgb, var(--mac-text-primary), black 72%)';
const analyticsTextSecondary = 'color-mix(in srgb, var(--mac-text-secondary), black 48%)';

function AnalyticsSectionCard({ title, subtitle, children, action, compact = false }) {
  return (
    <section style={{
      background: analyticsSurface,
      border: analyticsBorder,
      borderRadius: '18px',
      padding: compact ? '16px' : '20px',
      boxShadow: 'var(--mac-shadow-sm)'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: '16px',
        marginBottom: '18px'
      }}>
        <div>
          <h3 style={{
            margin: 0,
            fontSize: compact ? '16px' : '18px',
            fontWeight: 700,
            color: analyticsTextPrimary
          }}>
            {title}
          </h3>
          {subtitle ?
          <p style={{
            margin: '6px 0 0 0',
            fontSize: compact ? '12px' : '13px',
            color: analyticsTextSecondary,
            lineHeight: 1.5
          }}>
              {subtitle}
            </p> :
          null}
        </div>
        {action}
      </div>
      {children}
    </section>);
}

function AnalyticsStatCard({ icon, label, value, helper, accent = 'var(--mac-accent-blue, #2563eb)', format = 'count', compact = false }) {
  return (
    <article style={{
      background: analyticsSurfaceStrong,
      border: analyticsBorder,
      borderRadius: '18px',
      padding: compact ? '14px' : '18px',
      minHeight: compact ? '108px' : '126px',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      boxShadow: 'var(--mac-shadow-sm)'
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px'
      }}>
        <span style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: compact ? '38px' : '42px',
          height: compact ? '38px' : '42px',
          borderRadius: '14px',
          background: `${accent}14`,
          color: accent
        }}>
          {icon}
        </span>
        {helper ?
        <span style={{
          fontSize: '12px',
          fontWeight: 600,
          color: accent,
          background: `${accent}12`,
          padding: '6px 10px',
          borderRadius: '999px'
        }}>
            {helper}
          </span> :
        null}
      </div>

      <div>
        <div style={{
          fontSize: compact ? '12px' : '13px',
          color: analyticsTextSecondary,
          marginBottom: '8px'
        }}>
          {label}
        </div>
        <div style={{
          fontSize: compact ? '24px' : '28px',
          fontWeight: 800,
          letterSpacing: '-0.02em',
          color: analyticsTextPrimary,
          lineHeight: 1.1
        }}>
          {formatMetricValue(value, format)}
        </div>
      </div>
    </article>);
}

function AnalyticsComparisonList({ items, format = 'count', accent = 'var(--mac-accent-blue, #2563eb)' }) {
  if (!items.length) {
    return <div style={{ color: analyticsTextSecondary }}>Данных пока недостаточно для сравнения.</div>;
  }

  const maxValue = Math.max(...items.map((item) => Number(item.value) || 0), 1);

  return (
    <div style={{ display: 'grid', gap: '14px' }}>
      {items.map((item) =>
      <div key={item.label} style={{ display: 'grid', gap: '8px' }}>
          <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          gap: '12px'
        }}>
            <span style={{ fontSize: '14px', color: analyticsTextPrimary, fontWeight: 600 }}>
              {item.label}
            </span>
            <span style={{ fontSize: '13px', color: analyticsTextSecondary }}>
              {formatMetricValue(item.value, format)}
            </span>
          </div>
          <div style={{
          height: '10px',
          borderRadius: '999px',
          background: 'color-mix(in srgb, var(--mac-card-border), transparent 38%)',
          overflow: 'hidden'
        }}>
            <div style={{
            width: `${clamp(Number(item.value) / maxValue * 100, 6, 100)}%`,
            height: '100%',
            borderRadius: '999px',
            background: `linear-gradient(90deg, ${accent}, ${accent}bb)`
          }}></div>
          </div>
        </div>
      )}
    </div>);
}

function AnalyticsLineTrend({ items, format = 'count', accent = 'var(--mac-accent-blue, #2563eb)', compact = false }) {
  if (!items.length) {
    return <div style={{ color: analyticsTextSecondary }}>История для графика пока пуста.</div>;
  }

  const values = items.map((item) => Number(item.value) || 0);
  const maxValue = Math.max(...values, 1);
  const minValue = Math.min(...values, 0);
  const range = Math.max(maxValue - minValue, 1);
  const points = items.map((item, index) => {
    const x = items.length === 1 ? 0 : index / (items.length - 1) * 100;
    const y = 100 - (Number(item.value) - minValue) / range * 100;
    return `${x},${y}`;
  }).join(' ');

  return (
    <div style={{ display: 'grid', gap: '14px' }}>
      <div style={{
        height: compact ? '180px' : '210px',
        borderRadius: '16px',
        background: 'linear-gradient(180deg, color-mix(in srgb, var(--mac-card-bg), white 6%) 0%, color-mix(in srgb, var(--mac-main-shell-bg), white 12%) 100%)',
        border: analyticsBorder,
        padding: '16px'
      }}>
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
          <defs>
            <linearGradient id="analyticsLineFill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={accent} stopOpacity="0.22" />
              <stop offset="100%" stopColor={accent} stopOpacity="0.02" />
            </linearGradient>
          </defs>
          <polyline fill="none" stroke={accent} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" points={points} />
          <polygon fill="url(#analyticsLineFill)" points={`0,100 ${points} 100,100`} />
        </svg>
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: compact ? 'repeat(auto-fit, minmax(84px, 1fr))' : `repeat(${Math.min(items.length, 6)}, minmax(0, 1fr))`,
        gap: '10px'
      }}>
        {items.slice(0, 6).map((item) =>
        <div key={item.label} style={{ background: analyticsInsetSurface, border: analyticsBorder, borderRadius: '12px', padding: '10px 12px' }}>
            <div style={{ fontSize: '12px', color: analyticsTextSecondary, marginBottom: '4px' }}>{item.label}</div>
            <div style={{ fontSize: '14px', fontWeight: 700, color: analyticsTextPrimary }}>
              {formatMetricValue(item.value, format)}
            </div>
          </div>
        )}
      </div>
    </div>);
}

function AnalyticsEmptyState({ title, description }) {
  return (
    <div style={{
      background: analyticsSurface,
      border: '1px dashed color-mix(in srgb, var(--mac-card-border), white 8%)',
      borderRadius: '18px',
      padding: '36px',
      textAlign: 'center',
      color: analyticsTextSecondary
    }}>
      <div style={{ fontSize: '16px', fontWeight: 700, color: analyticsTextPrimary, marginBottom: '8px' }}>{title}</div>
      <div style={{ fontSize: '14px', lineHeight: 1.6 }}>{description}</div>
    </div>);
}

export default function AnalyticsPage() {
  const { getColor, getSpacing } = useTheme();
  const [loading, setLoading] = useState(false);
  const [dateRange, setDateRange] = useState(buildRelativeDateRange(30));
  const [department, setDepartment] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const [isCompactLayout, setIsCompactLayout] = useState(() => typeof window !== 'undefined' ? window.innerWidth < 900 : false);
  const [data, setData] = useState({
    overview: null,
    appointments: null,
    revenue: null,
    providers: null,
    visualization: null,
    kpi: null,
    predictive: null
  });
  const activeTabMeta = TAB_DEFINITIONS.find((tab) => tab.id === activeTab) || TAB_DEFINITIONS[0];
  const activePreset = getActivePreset(dateRange.start, dateRange.end);

  useEffect(() => {
    const updateLayoutMode = () => {
      setIsCompactLayout(window.innerWidth < 900);
    };

    updateLayoutMode();
    window.addEventListener('resize', updateLayoutMode);
    return () => window.removeEventListener('resize', updateLayoutMode);
  }, []);

  const loadAnalytics = useCallback(async (tab = activeTab) => {
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
        case 'kpi':
          response = await api.get(`/analytics/kpi-metrics?${params}`);
          break;
        case 'predictive':
          response = await api.get(`/analytics/predictive?${params}`);
          break;
        default:
          response = await api.get(`/analytics/dashboard?${params}`);
      }

      setData((prev) => ({ ...prev, [tab]: response?.data ?? null }));
    } catch (error) {
      logger.error('Ошибка загрузки аналитики:', error);
    } finally {
      setLoading(false);
    }
  }, [activeTab, dateRange.start, dateRange.end, department]);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

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

      const blob = new Blob([response?.data ?? response], {
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
      logger.error('Ошибка экспорта:', error);
    }
  };

  const setQuickRange = (days) => {
    setDateRange(buildRelativeDateRange(days));
  };

  const renderMetricsRow = (metrics) =>
  <div style={{
    display: 'grid',
    gridTemplateColumns: isCompactLayout ? '1fr' : 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: '16px'
  }}>
      {metrics.map((metric) =>
    <AnalyticsStatCard
      key={metric.label}
      icon={metric.icon}
      label={metric.label}
      value={metric.value}
      helper={metric.helper}
      accent={metric.accent}
      format={metric.format}
      compact={isCompactLayout}
    />
    )}
    </div>;

  const renderOverviewTab = () => {
    if (!data.overview) {
      return <AnalyticsEmptyState title="Нет обзорных данных" description="Попробуй обновить диапазон или перезагрузить аналитический срез." />;
    }

    const { today = {}, month = {} } = data.overview || {};

    const metrics = [
    {
      label: 'Визиты сегодня',
      value: today?.visits?.total_visits || 0,
      helper: 'Сегодня',
      accent: 'var(--mac-accent-blue, #2563eb)',
      icon: <Calendar size={18} />
    },
    {
      label: 'Доходы сегодня',
      value: today?.revenue?.total_revenue || 0,
      helper: 'Касса',
      accent: 'var(--mac-success)',
      format: 'revenue',
      icon: <DollarSign size={18} />
    },
    {
      label: 'Пациенты за период',
      value: month?.patients?.total_patients || 0,
      helper: 'База',
      accent: 'var(--mac-accent-purple)',
      icon: <Users size={18} />
    },
    {
      label: 'Конверсия завершения',
      value: month?.visits?.completion_rate || 0,
      helper: 'Эффективность',
      accent: 'var(--mac-warning)',
      format: 'percentage',
      icon: <TrendingUp size={18} />
    }];

    const visitTrend = normalizePairs(month?.visits?.day_stats, (day, count) => ({
      label: day,
      value: count
    }));
    const departmentRevenue = normalizePairs(month?.revenue?.department_stats, (departmentName, stats) => ({
      label: departmentName,
      value: stats?.total_revenue || 0
    }));

    return (
      <div style={{ display: 'grid', gap: '18px' }}>
        {renderMetricsRow(metrics)}
        <div style={{
          display: 'grid',
          gridTemplateColumns: isCompactLayout ? '1fr' : 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '18px'
        }}>
          <AnalyticsSectionCard
            title="Ритм визитов"
            subtitle="Быстрый обзор нагрузки по дням недели."
            compact={isCompactLayout}
          >
            <AnalyticsLineTrend items={visitTrend} accent="var(--mac-accent-blue, #2563eb)" compact={isCompactLayout} />
          </AnalyticsSectionCard>
          <AnalyticsSectionCard
            title="Доход по отделениям"
            subtitle="Сразу видно, какие отделения тянут выручку."
            compact={isCompactLayout}
          >
            <AnalyticsComparisonList items={departmentRevenue} format="revenue" accent="var(--mac-success)" />
          </AnalyticsSectionCard>
        </div>
      </div>);

  };

  const renderAppointmentsTab = () => {
    if (!data.appointments) {
      return <AnalyticsEmptyState title="Нет данных по записям" description="Этот блок появится, когда backend вернёт воронку записи и статусы." />;
    }

    const {
      summary = {},
      status_distribution = {},
      conversion_rates = {}
    } = data.appointments || {};

    const metrics = [
    {
      label: 'Всего записей',
      value: summary.total_appointments || 0,
      helper: 'Поток',
      accent: 'var(--mac-accent-blue, #2563eb)',
      icon: <Calendar size={18} />
    },
    {
      label: 'Оплачено',
      value: summary.paid_appointments || 0,
      helper: 'Оплата',
      accent: 'var(--mac-success)',
      icon: <DollarSign size={18} />
    },
    {
      label: 'Завершено',
      value: summary.completed_appointments || 0,
      helper: 'Финал',
      accent: 'var(--mac-accent-purple)',
      icon: <Activity size={18} />
    },
    {
      label: 'Общая конверсия',
      value: conversion_rates.overall_conversion || 0,
      helper: 'Воронка',
      accent: 'var(--mac-warning)',
      format: 'percentage',
      icon: <TrendingUp size={18} />
    }];

    const statuses = normalizePairs(status_distribution, (status, count) => ({
      label: status,
      value: count
    }));
    const funnel = [
    { label: 'Запись -> Оплата', value: conversion_rates.pending_to_paid || 0 },
    { label: 'Оплата -> Завершение', value: conversion_rates.paid_to_completed || 0 },
    { label: 'Итоговая конверсия', value: conversion_rates.overall_conversion || 0 }];


    return (
      <div style={{ display: 'grid', gap: '18px' }}>
        {renderMetricsRow(metrics)}
        <div style={{
          display: 'grid',
          gridTemplateColumns: isCompactLayout ? '1fr' : 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '18px'
        }}>
          <AnalyticsSectionCard
            title="Статусы записей"
            subtitle="Что происходит с записями в текущем окне."
            compact={isCompactLayout}
          >
            <AnalyticsComparisonList items={statuses} accent="var(--mac-accent-blue, #2563eb)" />
          </AnalyticsSectionCard>
          <AnalyticsSectionCard
            title="Качество воронки"
            subtitle="Где путь пациента сужается сильнее всего."
            compact={isCompactLayout}
          >
            <AnalyticsComparisonList items={funnel} format="percentage" accent="var(--mac-warning)" />
          </AnalyticsSectionCard>
        </div>
      </div>);

  };

  const renderRevenueTab = () => {
    if (!data.revenue) {
      return <AnalyticsEmptyState title="Нет данных по доходам" description="Попробуй другой диапазон или обновление среза." />;
    }

    const {
      total_revenue = 0,
      total_transactions = 0,
      average_transaction = 0,
      daily_revenue = [],
      provider_breakdown = {}
    } = data.revenue || {};

    const metrics = [
    {
      label: 'Общий доход',
      value: total_revenue,
      helper: 'Сумма',
      accent: 'var(--mac-success)',
      format: 'revenue',
      icon: <DollarSign size={18} />
    },
    {
      label: 'Транзакций',
      value: total_transactions,
      helper: 'Платежи',
      accent: 'var(--mac-accent-blue, #2563eb)',
      icon: <Activity size={18} />
    },
    {
      label: 'Средний чек',
      value: average_transaction,
      helper: 'Среднее',
      accent: 'var(--mac-accent-purple)',
      format: 'revenue',
      icon: <ArrowUpRight size={18} />
    }];

    const dailyTrend = (daily_revenue || []).map((item) => ({
      label: new Date(item.date).toLocaleDateString('ru-RU', {
        month: 'short',
        day: 'numeric'
      }),
      value: item.amount
    }));
    const providerRevenue = normalizePairs(provider_breakdown, (providerName, stats) => ({
      label: providerName,
      value: stats?.total_amount || 0
    }));


    return (
      <div style={{ display: 'grid', gap: '18px' }}>
        {renderMetricsRow(metrics)}
        <div style={{
          display: 'grid',
          gridTemplateColumns: isCompactLayout ? '1fr' : 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '18px'
        }}>
          <AnalyticsSectionCard
            title="Доход по дням"
            subtitle="Насколько ровно идёт денежный поток."
            compact={isCompactLayout}
          >
            <AnalyticsLineTrend items={dailyTrend} format="revenue" accent="var(--mac-success)" compact={isCompactLayout} />
          </AnalyticsSectionCard>
          <AnalyticsSectionCard
            title="Доход по провайдерам"
            subtitle="Какие платёжные каналы приносят больше."
            compact={isCompactLayout}
          >
            <AnalyticsComparisonList items={providerRevenue} format="revenue" accent="#7c3aed" />
          </AnalyticsSectionCard>
        </div>
      </div>);

  };

  const renderProvidersTab = () => {
    if (!data.providers) {
      return <AnalyticsEmptyState title="Нет данных по провайдерам" description="Провайдеры появятся здесь после успешной загрузки аналитики платежей." />;
    }

    const { summary = {}, providers = {} } = data.providers || {};

    const metrics = [
    {
      label: 'Активных провайдеров',
      value: summary.active_providers || 0,
      helper: 'Каналы',
      accent: 'var(--mac-accent-blue, #2563eb)',
      icon: <Building2 size={18} />
    },
    {
      label: 'Всего транзакций',
      value: summary.total_transactions || 0,
      helper: 'Операции',
      accent: 'var(--mac-success)',
      icon: <Activity size={18} />
    },
    {
      label: 'Общий доход',
      value: summary.total_revenue || 0,
      helper: 'Выручка',
      accent: 'var(--mac-accent-purple)',
      format: 'revenue',
      icon: <DollarSign size={18} />
    },
    {
      label: 'Комиссия',
      value: summary.total_commission || 0,
      helper: 'Издержки',
      accent: 'var(--mac-warning)',
      format: 'revenue',
      icon: <Wallet size={18} />
    }];

    const providerAmount = normalizePairs(providers, (_, stats) => ({
      label: stats?.name || 'Без названия',
      value: stats?.total_amount || 0
    }));
    const providerSuccess = normalizePairs(providers, (_, stats) => ({
      label: stats?.name || 'Без названия',
      value: stats?.success_rate || 0
    }));


    return (
      <div style={{ display: 'grid', gap: '18px' }}>
        {renderMetricsRow(metrics)}
        <div style={{
          display: 'grid',
          gridTemplateColumns: isCompactLayout ? '1fr' : 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '18px'
        }}>
          <AnalyticsSectionCard
            title="Доходность провайдеров"
            subtitle="Сравнение по выручке без визуального шума."
            compact={isCompactLayout}
          >
            <AnalyticsComparisonList items={providerAmount} format="revenue" accent="var(--mac-accent-blue, #2563eb)" />
          </AnalyticsSectionCard>
          <AnalyticsSectionCard
            title="Успешность операций"
            subtitle="Где меньше отказов и стабильнее обработка."
            compact={isCompactLayout}
          >
            <AnalyticsComparisonList items={providerSuccess} format="percentage" accent="var(--mac-success)" />
          </AnalyticsSectionCard>
        </div>
      </div>);

  };

  const renderCurrentTab = () => {
    switch (activeTab) {
      case 'overview':
        return renderOverviewTab();
      case 'appointments':
        return renderAppointmentsTab();
      case 'revenue':
        return renderRevenueTab();
      case 'providers':
        return renderProvidersTab();
      case 'visualization':
        return (
          <AnalyticsSectionCard title="Глубокая визуализация" subtitle="Расширенные интерактивные графики для детального разбора." compact={isCompactLayout}>
            <AdvancedCharts
              data={data.visualization}
              loading={loading}
              onRefresh={() => loadAnalytics('visualization')}
              onExport={() => exportData('json')}
              title="Интерактивные графики аналитики" />
          </AnalyticsSectionCard>);
      case 'kpi':
        return (
          <AnalyticsSectionCard title="KPI-панель" subtitle="Управленческие метрики и сравнения без смешения с обзорным экраном." compact={isCompactLayout}>
            <KPIMetrics
              data={data.kpi}
              loading={loading}
              onRefresh={() => loadAnalytics('kpi')}
              onExport={() => exportData('json')} />
          </AnalyticsSectionCard>);
      case 'predictive':
        return (
          <AnalyticsSectionCard title="Прогнозная аналитика" subtitle="Будущие тренды и сценарии на основе текущих данных." compact={isCompactLayout}>
            <PredictiveAnalytics
              data={data.predictive}
              loading={loading}
              onRefresh={() => loadAnalytics('predictive')}
              onExport={() => exportData('json')} />
          </AnalyticsSectionCard>);
      default:
        return renderOverviewTab();
    }
  };

  return (
    <div style={{ padding: isCompactLayout ? getSpacing('md') : getSpacing('lg'), display: 'grid', gap: getSpacing('lg') }}>
      <section style={{
        background: analyticsSurface,
        border: analyticsBorder,
        borderRadius: '22px',
        padding: isCompactLayout ? '18px' : '24px',
        boxShadow: 'var(--mac-shadow-sm)'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: isCompactLayout ? 'stretch' : 'flex-start',
          gap: '18px',
          flexWrap: 'wrap',
          flexDirection: isCompactLayout ? 'column' : 'row'
        }}>
          <div style={{ maxWidth: '760px' }}>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 12px',
              borderRadius: '999px',
              background: analyticsInsetSurface,
              color: getColor('primary', 800),
              fontSize: '12px',
              fontWeight: 700,
              marginBottom: '14px',
              width: isCompactLayout ? 'fit-content' : 'auto'
            }}>
              <BarChart3 size={14} />
              Админ / аналитика
            </div>
            <h1 style={{
              fontSize: isCompactLayout ? '26px' : '32px',
              lineHeight: 1.1,
              fontWeight: 800,
              color: getColor('primary', 900),
              margin: 0
            }}>
              Аналитика
            </h1>
            <p style={{ margin: '10px 0 0 0', fontSize: isCompactLayout ? '14px' : '15px', lineHeight: 1.65, color: analyticsTextSecondary }}>
              Быстрый обзор вынесен отдельно, а здесь собраны подробные разрезы по записям, выручке, провайдерам и прогнозам.
            </p>
          </div>
          <Button
            variant="primary"
            size="lg"
            startIcon={<Download size={16} />}
            onClick={() => exportData('json')}
            style={{
              borderRadius: '14px',
              boxShadow: '0 10px 24px rgba(37, 99, 235, 0.22)',
              width: isCompactLayout ? '100%' : 'auto',
              justifyContent: 'center'
            }}>
            Экспорт JSON
          </Button>
        </div>
      </section>

      <AdminRouteSwitcher current="analytics" />

      <section style={{
        background: analyticsSurface,
        border: analyticsBorder,
        borderRadius: '20px',
        padding: isCompactLayout ? '16px' : '20px',
        display: 'grid',
        gap: '18px',
        boxShadow: 'var(--mac-shadow-sm)'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: isCompactLayout ? 'stretch' : 'center',
          gap: '16px',
          flexWrap: 'wrap',
          flexDirection: isCompactLayout ? 'column' : 'row'
        }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: analyticsTextSecondary, marginBottom: '6px' }}>
              Период и разрез
            </div>
            <div style={{ fontSize: isCompactLayout ? '15px' : '16px', fontWeight: 700, color: analyticsTextPrimary }}>
              {activeTabMeta.label}: {activeTabMeta.description}
            </div>
          </div>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 12px',
            borderRadius: '999px',
            background: analyticsInsetSurface,
            border: analyticsBorder,
            color: analyticsTextSecondary,
            fontSize: '13px',
            width: isCompactLayout ? '100%' : 'auto',
            justifyContent: 'center'
          }}>
            <Clock3 size={14} />
            {dateRange.start} {' -> '} {dateRange.end}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <SegmentedControl
            aria-label="Быстрый диапазон аналитики"
            value={activePreset || ''}
            onChange={(days) => setQuickRange(Number(days))}
            options={[7, 30, 90].map((days) => ({
              value: days,
              label: `${days} дней`
            }))}
            size="large"
            style={{
              width: isCompactLayout ? '100%' : 'auto',
              overflowX: 'auto',
              background: analyticsInsetSurface,
              border: analyticsBorder,
              borderRadius: '14px'
            }} />
        </div>

        <div style={{
          display: 'flex',
          gap: '14px',
          alignItems: 'end',
          flexWrap: 'wrap',
          flexDirection: isCompactLayout ? 'column' : 'row'
        }}>
          <div style={{ flex: isCompactLayout ? '1 1 100%' : '1 1 220px', width: isCompactLayout ? '100%' : 'auto' }}>
            <Input
              type="date"
              label="Начало периода"
              aria-label="Дата начала периода"
              value={dateRange.start}
              onChange={(e) => setDateRange((prev) => ({ ...prev, start: e.target.value }))}
              style={{
                width: '100%',
                minHeight: '40px',
                borderRadius: '12px',
                boxSizing: 'border-box'
              }} />
          </div>

          <div style={{ flex: isCompactLayout ? '1 1 100%' : '1 1 220px', width: isCompactLayout ? '100%' : 'auto' }}>
            <Input
              type="date"
              label="Конец периода"
              aria-label="Дата окончания периода"
              value={dateRange.end}
              onChange={(e) => setDateRange((prev) => ({ ...prev, end: e.target.value }))}
              style={{
                width: '100%',
                minHeight: '40px',
                borderRadius: '12px',
                boxSizing: 'border-box'
              }} />
          </div>

          <div style={{ flex: isCompactLayout ? '1 1 100%' : '1 1 220px', width: isCompactLayout ? '100%' : 'auto' }}>
            <Select
              label="Отделение"
              value={department}
              onChange={setDepartment}
              options={DEPARTMENT_OPTIONS}
              size="large"
              style={{
                width: '100%'
              }} />
          </div>

          <Button
            variant="primary"
            size="lg"
            onClick={() => loadAnalytics()}
            disabled={loading}
            startIcon={<RefreshCw size={16} style={loading ? { animation: 'mac-spin 1s linear infinite' } : undefined} />}
            style={{
              borderRadius: '14px',
              minWidth: '156px',
              flex: isCompactLayout ? '1 1 100%' : '0 0 auto',
              width: isCompactLayout ? '100%' : 'auto'
            }}>
            {loading ? 'Обновляем...' : 'Обновить'}
          </Button>
        </div>
      </section>

      <section style={{
        background: analyticsSurface,
        border: analyticsBorder,
        borderRadius: '20px',
        padding: isCompactLayout ? '10px' : '12px',
        boxShadow: 'var(--mac-shadow-sm)'
      }}>
        <div style={{
          display: 'flex',
          gap: '10px',
          flexWrap: isCompactLayout ? 'nowrap' : 'wrap',
          overflowX: isCompactLayout ? 'auto' : 'visible',
          paddingBottom: isCompactLayout ? '4px' : 0,
          scrollbarWidth: 'none'
        }}>
          {TAB_DEFINITIONS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <Button
                key={tab.id}
                type="button"
                variant={isActive ? 'primary' : 'secondary'}
                size={isCompactLayout ? 'md' : 'lg'}
                startIcon={<Icon size={16} />}
                onClick={() => handleTabChange(tab.id)}
                style={{
                  borderRadius: '14px',
                  boxShadow: isActive ? '0 10px 20px rgba(37, 99, 235, 0.18)' : 'var(--mac-shadow-sm)',
                  whiteSpace: 'nowrap',
                  flex: isCompactLayout ? '0 0 auto' : 'none'
                }}>
                {tab.label}
              </Button>);
          })}
        </div>
      </section>

      {loading ?
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: isCompactLayout ? '160px' : '200px', color: analyticsTextSecondary }}>
          <RefreshCw size={24} style={{ animation: 'mac-spin 1s linear infinite' }} />
          <span style={{ marginLeft: '12px' }}>Подготавливаем аналитический срез...</span>
        </div> :
      renderCurrentTab()
      }
    </div>);

}
