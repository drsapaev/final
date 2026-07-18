import { useState, useEffect, useCallback } from 'react';
import type { CSSProperties } from "react";
import PropTypes from 'prop-types';
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
import { useTranslation } from '../i18n/useTranslation';

const DAY_MS = 24 * 60 * 60 * 1000;

const TAB_DEFINITIONS = [
  { id: 'overview', labelKey: 'misc.an_tab_overview', descriptionKey: 'misc.an_tab_overview_desc', icon: Activity },
  { id: 'appointments', labelKey: 'misc.an_tab_appointments', descriptionKey: 'misc.an_tab_appointments_desc', icon: Calendar },
  { id: 'revenue', labelKey: 'misc.an_tab_revenue', descriptionKey: 'misc.an_tab_revenue_desc', icon: DollarSign },
  { id: 'providers', labelKey: 'misc.an_tab_providers', descriptionKey: 'misc.an_tab_providers_desc', icon: Wallet },
  { id: 'visualization', labelKey: 'misc.an_tab_visualization', descriptionKey: 'misc.an_tab_visualization_desc', icon: BarChart3 },
  { id: 'kpi', label: 'KPI', descriptionKey: 'misc.an_tab_kpi_desc', icon: Target },
  { id: 'predictive', labelKey: 'misc.an_tab_predictive', descriptionKey: 'misc.an_tab_predictive_desc', icon: TrendingUp }
];

const DEPARTMENT_OPTION_KEYS = [
  { value: '', labelKey: 'misc.an_dept_all' },
  { value: 'General', labelKey: 'misc.an_dept_general' },
  { value: 'Cardiology', labelKey: 'misc.an_dept_cardiology' },
  { value: 'Dermatology', labelKey: 'misc.an_dept_dermatology' },
  { value: 'Dentistry', labelKey: 'misc.an_dept_dentistry' }
];

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

function AnalyticsSectionCard({ title, subtitle, children, action, compact = false }: any) {
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
        gap: 'var(--mac-spacing-4)',
        marginBottom: '18px'
      }}>
        <div>
          <h3 style={{
            margin: 0,
            fontSize: compact ? '16px' : '18px',
            fontWeight: 'var(--mac-font-weight-bold)',
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

AnalyticsSectionCard.propTypes = {
  title: PropTypes.string,
  subtitle: PropTypes.string,
  children: PropTypes.node,
  action: PropTypes.node,
  compact: PropTypes.bool,
};

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
        gap: 'var(--mac-spacing-3)'
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
          fontSize: 'var(--mac-font-size-xs)',
          fontWeight: 'var(--mac-font-weight-semibold)',
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
          marginBottom: 'var(--mac-spacing-2)'
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

AnalyticsStatCard.propTypes = {
  icon: PropTypes.node,
  label: PropTypes.string,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  helper: PropTypes.string,
  accent: PropTypes.string,
  format: PropTypes.string,
  compact: PropTypes.bool,
};

function AnalyticsComparisonList({ items, format = 'count', accent = 'var(--mac-accent-blue, #2563eb)', t }) {
  if (!items.length) {
    return <div style={{ color: analyticsTextSecondary }}>{t('misc.an_compare_empty')}</div>;
  }

  const maxValue = Math.max(...items.map((item) => Number(item.value) || 0), 1);

  return (
    <div style={{ display: 'grid', gap: '14px' }}>
      {items.map((item) =>
      <div key={item.label} style={{ display: 'grid', gap: 'var(--mac-spacing-2)' }}>
          <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          gap: 'var(--mac-spacing-3)'
        }}>
            <span style={{ fontSize: 'var(--mac-font-size-base)', color: analyticsTextPrimary, fontWeight: 'var(--mac-font-weight-semibold)' }}>
              {item.label}
            </span>
            <span style={{ fontSize: 'var(--mac-font-size-sm)', color: analyticsTextSecondary }}>
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

AnalyticsComparisonList.propTypes = {
  items: PropTypes.array,
  format: PropTypes.string,
  accent: PropTypes.string,
  t: PropTypes.func,
};

function AnalyticsLineTrend({ items, format = 'count', accent = 'var(--mac-accent-blue, #2563eb)', compact = false, t }) {
  if (!items.length) {
    return <div style={{ color: analyticsTextSecondary }}>{t('misc.an_trend_empty')}</div>;
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
        borderRadius: 'var(--mac-radius-xl)',
        background: 'linear-gradient(180deg, color-mix(in srgb, var(--mac-card-bg), white 6%) 0%, color-mix(in srgb, var(--mac-main-shell-bg), white 12%) 100%)',
        border: analyticsBorder,
        padding: 'var(--mac-spacing-4)'
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
        <div key={item.label} style={{ background: analyticsInsetSurface, border: analyticsBorder, borderRadius: 'var(--mac-radius-lg)', padding: '10px 12px' }}>
            <div style={{ fontSize: 'var(--mac-font-size-xs)', color: analyticsTextSecondary, marginBottom: 'var(--mac-spacing-1)' }}>{item.label}</div>
            <div style={{ fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-bold)', color: analyticsTextPrimary }}>
              {formatMetricValue(item.value, format)}
            </div>
          </div>
        )}
      </div>
    </div>);
}

AnalyticsLineTrend.propTypes = {
  items: PropTypes.array,
  format: PropTypes.string,
  accent: PropTypes.string,
  compact: PropTypes.bool,
  t: PropTypes.func,
};

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
      <div style={{ fontSize: 'var(--mac-font-size-lg)', fontWeight: 'var(--mac-font-weight-bold)', color: analyticsTextPrimary, marginBottom: 'var(--mac-spacing-2)' }}>{title}</div>
      <div style={{ fontSize: 'var(--mac-font-size-base)', lineHeight: 1.6 }}>{description}</div>
    </div>);
}

AnalyticsEmptyState.propTypes = {
  title: PropTypes.string,
  description: PropTypes.string,
};

export default function AnalyticsPage() {
  const { getColor, getSpacing } = useTheme();
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
  const activeTabLabel = activeTabMeta.label !== undefined ? activeTabMeta.label : t(activeTabMeta.labelKey);
  const activeTabDescription = t(activeTabMeta.descriptionKey);
  const departmentOptions = DEPARTMENT_OPTION_KEYS.map((opt) => ({ value: opt.value, label: t(opt.labelKey) }));
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
      }) as any;

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
    gap: 'var(--mac-spacing-4)'
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
      return <AnalyticsEmptyState title={t('misc.an_overview_empty_title')} description={t('misc.an_overview_empty_desc')} />;
    }

    const { today = {}, month = {} } = data.overview || {};

    const metrics = [
    {
      label: t('misc.an_overview_metric_visits_today'),
      value: today?.visits?.total_visits || 0,
      helper: t('misc.an_overview_helper_today'),
      accent: 'var(--mac-accent-blue, #2563eb)',
      icon: <Calendar size={18} />
    },
    {
      label: t('misc.an_overview_metric_revenue_today'),
      value: today?.revenue?.total_revenue || 0,
      helper: t('misc.an_overview_helper_register'),
      accent: 'var(--mac-success)',
      format: 'revenue',
      icon: <DollarSign size={18} />
    },
    {
      label: t('misc.an_overview_metric_patients_period'),
      value: month?.patients?.total_patients || 0,
      helper: t('misc.an_overview_helper_base'),
      accent: 'var(--mac-accent-purple)',
      icon: <Users size={18} />
    },
    {
      label: t('misc.an_overview_metric_completion'),
      value: month?.visits?.completion_rate || 0,
      helper: t('misc.an_overview_helper_efficiency'),
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
            title={t('misc.an_overview_section_visits_title')}
            subtitle={t('misc.an_overview_section_visits_subtitle')}
            compact={isCompactLayout}
          >
            <AnalyticsLineTrend items={visitTrend} accent="var(--mac-accent-blue, #2563eb)" compact={isCompactLayout} t={t} />
          </AnalyticsSectionCard>
          <AnalyticsSectionCard
            title={t('misc.an_overview_section_dept_revenue_title')}
            subtitle={t('misc.an_overview_section_dept_revenue_subtitle')}
            compact={isCompactLayout}
          >
            <AnalyticsComparisonList items={departmentRevenue} format="revenue" accent="var(--mac-success)" t={t} />
          </AnalyticsSectionCard>
        </div>
      </div>);

  };

  const renderAppointmentsTab = () => {
    if (!data.appointments) {
      return <AnalyticsEmptyState title={t('misc.an_appt_empty_title')} description={t('misc.an_appt_empty_desc')} />;
    }

    const {
      summary = {},
      status_distribution = {},
      conversion_rates = {}
    } = data.appointments || {};

    const metrics = [
    {
      label: t('misc.an_appt_metric_total'),
      value: summary.total_appointments || 0,
      helper: t('misc.an_appt_helper_flow'),
      accent: 'var(--mac-accent-blue, #2563eb)',
      icon: <Calendar size={18} />
    },
    {
      label: t('misc.an_appt_metric_paid'),
      value: summary.paid_appointments || 0,
      helper: t('misc.an_appt_helper_payment'),
      accent: 'var(--mac-success)',
      icon: <DollarSign size={18} />
    },
    {
      label: t('misc.an_appt_metric_completed'),
      value: summary.completed_appointments || 0,
      helper: t('misc.an_appt_helper_final'),
      accent: 'var(--mac-accent-purple)',
      icon: <Activity size={18} />
    },
    {
      label: t('misc.an_appt_metric_conversion'),
      value: conversion_rates.overall_conversion || 0,
      helper: t('misc.an_appt_helper_funnel'),
      accent: 'var(--mac-warning)',
      format: 'percentage',
      icon: <TrendingUp size={18} />
    }];

    const statuses = normalizePairs(status_distribution, (status, count) => ({
      label: status,
      value: count
    }));
    const funnel = [
    { label: t('misc.an_appt_funnel_book_to_paid'), value: conversion_rates.pending_to_paid || 0 },
    { label: t('misc.an_appt_funnel_paid_to_completed'), value: conversion_rates.paid_to_completed || 0 },
    { label: t('misc.an_appt_funnel_total_conversion'), value: conversion_rates.overall_conversion || 0 }];


    return (
      <div style={{ display: 'grid', gap: '18px' }}>
        {renderMetricsRow(metrics)}
        <div style={{
          display: 'grid',
          gridTemplateColumns: isCompactLayout ? '1fr' : 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '18px'
        }}>
          <AnalyticsSectionCard
            title={t('misc.an_appt_section_statuses_title')}
            subtitle={t('misc.an_appt_section_statuses_subtitle')}
            compact={isCompactLayout}
          >
            <AnalyticsComparisonList items={statuses} accent="var(--mac-accent-blue, #2563eb)" t={t} />
          </AnalyticsSectionCard>
          <AnalyticsSectionCard
            title={t('misc.an_appt_section_funnel_title')}
            subtitle={t('misc.an_appt_section_funnel_subtitle')}
            compact={isCompactLayout}
          >
            <AnalyticsComparisonList items={funnel} format="percentage" accent="var(--mac-warning)" t={t} />
          </AnalyticsSectionCard>
        </div>
      </div>);

  };

  const renderRevenueTab = () => {
    if (!data.revenue) {
      return <AnalyticsEmptyState title={t('misc.an_rev_empty_title')} description={t('misc.an_rev_empty_desc')} />;
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
      label: t('misc.an_rev_metric_total'),
      value: total_revenue,
      helper: t('misc.an_rev_helper_amount'),
      accent: 'var(--mac-success)',
      format: 'revenue',
      icon: <DollarSign size={18} />
    },
    {
      label: t('misc.an_rev_metric_transactions'),
      value: total_transactions,
      helper: t('misc.an_rev_helper_payments'),
      accent: 'var(--mac-accent-blue, #2563eb)',
      icon: <Activity size={18} />
    },
    {
      label: t('misc.an_rev_metric_avg_check'),
      value: average_transaction,
      helper: t('misc.an_rev_helper_average'),
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
            title={t('misc.an_rev_section_daily_title')}
            subtitle={t('misc.an_rev_section_daily_subtitle')}
            compact={isCompactLayout}
          >
            <AnalyticsLineTrend items={dailyTrend} format="revenue" accent="var(--mac-success)" compact={isCompactLayout} t={t} />
          </AnalyticsSectionCard>
          <AnalyticsSectionCard
            title={t('misc.an_rev_section_providers_title')}
            subtitle={t('misc.an_rev_section_providers_subtitle')}
            compact={isCompactLayout}
          >
            <AnalyticsComparisonList items={providerRevenue} format="revenue" accent="#7c3aed" t={t} />
          </AnalyticsSectionCard>
        </div>
      </div>);

  };

  const renderProvidersTab = () => {
    if (!data.providers) {
      return <AnalyticsEmptyState title={t('misc.an_prov_empty_title')} description={t('misc.an_prov_empty_desc')} />;
    }

    const { summary = {}, providers = {} } = data.providers || {};

    const metrics = [
    {
      label: t('misc.an_prov_metric_active'),
      value: summary.active_providers || 0,
      helper: t('misc.an_prov_helper_channels'),
      accent: 'var(--mac-accent-blue, #2563eb)',
      icon: <Building2 size={18} />
    },
    {
      label: t('misc.an_prov_metric_transactions'),
      value: summary.total_transactions || 0,
      helper: t('misc.an_prov_helper_operations'),
      accent: 'var(--mac-success)',
      icon: <Activity size={18} />
    },
    {
      label: t('misc.an_prov_metric_total'),
      value: summary.total_revenue || 0,
      helper: t('misc.an_prov_helper_revenue'),
      accent: 'var(--mac-accent-purple)',
      format: 'revenue',
      icon: <DollarSign size={18} />
    },
    {
      label: t('misc.an_prov_metric_commission'),
      value: summary.total_commission || 0,
      helper: t('misc.an_prov_helper_costs'),
      accent: 'var(--mac-warning)',
      format: 'revenue',
      icon: <Wallet size={18} />
    }];

    const providerAmount = normalizePairs(providers, (_, stats) => ({
      label: stats?.name || t('misc.an_prov_no_name'),
      value: stats?.total_amount || 0
    }));
    const providerSuccess = normalizePairs(providers, (_, stats) => ({
      label: stats?.name || t('misc.an_prov_no_name'),
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
            title={t('misc.an_prov_section_yield_title')}
            subtitle={t('misc.an_prov_section_yield_subtitle')}
            compact={isCompactLayout}
          >
            <AnalyticsComparisonList items={providerAmount} format="revenue" accent="var(--mac-accent-blue, #2563eb)" t={t} />
          </AnalyticsSectionCard>
          <AnalyticsSectionCard
            title={t('misc.an_prov_section_success_title')}
            subtitle={t('misc.an_prov_section_success_subtitle')}
            compact={isCompactLayout}
          >
            <AnalyticsComparisonList items={providerSuccess} format="percentage" accent="var(--mac-success)" t={t} />
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
          <AnalyticsSectionCard title={t('misc.an_viz_section_title')} subtitle={t('misc.an_viz_section_subtitle')} compact={isCompactLayout}>
            <AdvancedCharts
              data={data.visualization}
              loading={loading}
              onRefresh={() => loadAnalytics('visualization')}
              onExport={() => exportData('json')}
              title={t('misc.an_viz_advanced_charts_title')} />
          </AnalyticsSectionCard>);
      case 'kpi':
        return (
          <AnalyticsSectionCard title={t('misc.an_kpi_section_title')} subtitle={t('misc.an_kpi_section_subtitle')} compact={isCompactLayout}>
            <KPIMetrics
              data={data.kpi}
              loading={loading}
              onRefresh={() => loadAnalytics('kpi')}
              onExport={() => exportData('json')} />
          </AnalyticsSectionCard>);
      case 'predictive':
        return (
          <AnalyticsSectionCard title={t('misc.an_pred_section_title')} subtitle={t('misc.an_pred_section_subtitle')} compact={isCompactLayout}>
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
              gap: 'var(--mac-spacing-2)',
              padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
              borderRadius: '999px',
              background: analyticsInsetSurface,
              color: getColor('primary', 800),
              fontSize: 'var(--mac-font-size-xs)',
              fontWeight: 'var(--mac-font-weight-bold)',
              marginBottom: '14px',
              width: isCompactLayout ? 'fit-content' : 'auto'
            }}>
              <BarChart3 size={14} />
              {t('misc.an_header_badge')}
            </div>
            <h1 style={{
              fontSize: isCompactLayout ? '26px' : '32px',
              lineHeight: 1.1,
              fontWeight: 800,
              color: getColor('primary', 900),
              margin: 0
            }}>
              {t('misc.an_header_title')}
            </h1>
            <p style={{ margin: '10px 0 0 0', fontSize: isCompactLayout ? '14px' : '15px', lineHeight: 1.65, color: analyticsTextSecondary }}>
              {t('misc.an_header_description')}
            </p>
          </div>
          <Button
            variant="primary"
            size="large"
            startIcon={<Download size={16} />}
            onClick={() => exportData('json')}
            style={{
              borderRadius: '14px',
              boxShadow: '0 10px 24px rgba(37, 99, 235, 0.22)',
              width: isCompactLayout ? '100%' : 'auto',
              justifyContent: 'center'
            }}>
            {t('misc.an_header_export_btn')}
          </Button>
        </div>
      </section>

      <AdminRouteSwitcher current="analytics" />

      <section style={{
        background: analyticsSurface,
        border: analyticsBorder,
        borderRadius: 'var(--mac-radius-xl)',
        padding: isCompactLayout ? '16px' : '20px',
        display: 'grid',
        gap: '18px',
        boxShadow: 'var(--mac-shadow-sm)'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: isCompactLayout ? 'stretch' : 'center',
          gap: 'var(--mac-spacing-4)',
          flexWrap: 'wrap',
          flexDirection: isCompactLayout ? 'column' : 'row'
        }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 'var(--mac-font-size-xs)', fontWeight: 'var(--mac-font-weight-bold)', letterSpacing: '0.08em', textTransform: 'uppercase', color: analyticsTextSecondary, marginBottom: 'var(--mac-spacing-2)' }}>
              {t('misc.an_filter_section_label')}
            </div>
            <div style={{ fontSize: isCompactLayout ? '15px' : '16px', fontWeight: 'var(--mac-font-weight-bold)', color: analyticsTextPrimary }}>
              {activeTabLabel}: {activeTabDescription}
            </div>
          </div>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
            borderRadius: '999px',
            background: analyticsInsetSurface,
            border: analyticsBorder,
            color: analyticsTextSecondary,
            fontSize: 'var(--mac-font-size-sm)',
            width: isCompactLayout ? '100%' : 'auto',
            justifyContent: 'center'
          }}>
            <Clock3 size={14} />
            {dateRange.start} {' -> '} {dateRange.end}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <SegmentedControl
            aria-label={t('misc.an_filter_quick_range_aria')}
            value={activePreset || ''}
            onChange={(days) => setQuickRange(Number(days))}
            options={[7, 30, 90].map((days) => ({
              value: days,
              label: t('misc.an_filter_days', { days })
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
              label={t('misc.an_filter_start_label')}
              aria-label={t('misc.an_filter_start_aria')}
              value={dateRange.start}
              onChange={(e) => setDateRange((prev) => ({ ...prev, start: e.target.value }))}
              style={{
                width: '100%',
                minHeight: '40px',
                borderRadius: 'var(--mac-radius-lg)',
                boxSizing: 'border-box'
              }} />
          </div>

          <div style={{ flex: isCompactLayout ? '1 1 100%' : '1 1 220px', width: isCompactLayout ? '100%' : 'auto' }}>
            <Input
              type="date"
              label={t('misc.an_filter_end_label')}
              aria-label={t('misc.an_filter_end_aria')}
              value={dateRange.end}
              onChange={(e) => setDateRange((prev) => ({ ...prev, end: e.target.value }))}
              style={{
                width: '100%',
                minHeight: '40px',
                borderRadius: 'var(--mac-radius-lg)',
                boxSizing: 'border-box'
              }} />
          </div>

          <div style={{ flex: isCompactLayout ? '1 1 100%' : '1 1 220px', width: isCompactLayout ? '100%' : 'auto' }}>
            <Select
              label={t('misc.an_filter_department_label')}
              value={department}
              onChange={(v: unknown) => setDepartment(String(v))}
              options={departmentOptions}
              size="large"
              style={{
                width: '100%'
              }} />
          </div>

          <Button
            variant="primary"
            size="large"
            onClick={() => loadAnalytics()}
            disabled={loading}
            startIcon={<RefreshCw size={16} style={loading ? { animation: 'mac-spin 1s linear infinite' } : undefined} />}
            style={{
              borderRadius: '14px',
              minWidth: '156px',
              flex: isCompactLayout ? '1 1 100%' : '0 0 auto',
              width: isCompactLayout ? '100%' : 'auto'
            }}>
            {loading ? t('misc.an_filter_refreshing_btn') : t('misc.an_filter_refresh_btn')}
          </Button>
        </div>
      </section>

      <section style={{
        background: analyticsSurface,
        border: analyticsBorder,
        borderRadius: 'var(--mac-radius-xl)',
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
                {tab.label !== undefined ? tab.label : t(tab.labelKey)}
              </Button>);
          })}
        </div>
      </section>

      {loading ?
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: isCompactLayout ? '160px' : '200px', color: analyticsTextSecondary }}>
          <RefreshCw size={24} style={{ animation: 'mac-spin 1s linear infinite' }} />
          <span style={{ marginLeft: 'var(--mac-spacing-3)' }}>{t('misc.an_loading_msg')}</span>
        </div> :
      renderCurrentTab()
      }
    </div>);

}
