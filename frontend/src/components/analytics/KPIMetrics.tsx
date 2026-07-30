
import { useState, useEffect, useCallback } from 'react';
import { Card, Button } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import {
  TrendingUp,
  TrendingDown,
  Users,
  Calendar,
  DollarSign,
  Activity,
  Target,
  Award,
  Clock,
  CheckCircle,




  Download,
  RefreshCw } from
'lucide-react';

/**
 * Компонент для отображения KPI метрик
 * Включает анимированные карточки, тренды, сравнения
 */
interface KPIMetricsData {
  metrics?: Record<string, Record<string, unknown>>;
  summary?: Record<string, number>;
}

interface KPIMetricsProps {
  data?: KPIMetricsData | null;
  loading?: boolean;
  onRefresh?: (chart?: string) => void;
  onExport?: (chart?: string) => void;
  showTrends?: boolean;
  showComparisons?: boolean;
}

const KPIMetrics = ({
  data,
  loading = false,
  onRefresh,
  onExport,
  showTrends = true,
  showComparisons = true
}: KPIMetricsProps) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [animatedValues, setAnimatedValues] = useState<Record<string, { current: number; target: number; trend: number }>>({});
  const [selectedPeriod, setSelectedPeriod] = useState('30d');

  const animateValues = useCallback(() => {
    if (!data?.metrics) return;
    const metrics = data.metrics;
    const animated: Record<string, { current: number; target: number; trend: number }> = {};

    Object.keys(metrics).forEach((key) => {
      const metric = metrics[key];
      animated[key] = {
        current: 0,
        target: Number(metric.value ?? 0),
        trend: Number(metric.trend ?? 0)
      };
    });

    setAnimatedValues(animated);

    // Анимация значений
    Object.keys(animated).forEach((key) => {
      const metric = metrics[key];
      const value = Number(metric.value ?? 0);
      const duration = 2000;
      const steps = 60;
      const stepValue = value / steps;
      const stepDuration = duration / steps;

      let currentStep = 0;
      const interval = setInterval(() => {
        currentStep++;
        setAnimatedValues((prev) => ({
          ...prev,
          [key]: {
            ...prev[key],
            current: Math.min(stepValue * currentStep, value)
          }
        }));

        if (currentStep >= steps) {
          clearInterval(interval);
        }
      }, stepDuration);
    });
  }, [data]);

  useEffect(() => {
    if (data?.metrics) {
      animateValues();
    }
  }, [data, animateValues]);

  const getMetricIcon = (type: string) => {
    const iconStyle = { width: '20px', height: '20px' };
    switch (type) {
      case 'revenue':return <DollarSign style={iconStyle} />;
      case 'patients':return <Users style={iconStyle} />;
      case 'appointments':return <Calendar style={iconStyle} />;
      case 'doctors':return <Award style={iconStyle} />;
      case 'efficiency':return <Target style={iconStyle} />;
      case 'satisfaction':return <CheckCircle style={iconStyle} />;
      case 'wait_time':return <Clock style={iconStyle} />;
      default:return <Activity style={iconStyle} />;
    }
  };

  const getTrendIcon = (trend: number) => {
    if (trend > 0) return <TrendingUp className="w-4 h-4 text-green-500" />;
    if (trend < 0) return <TrendingDown className="w-4 h-4 text-red-500" />;
    return <Activity className="w-4 h-4 text-gray-500" />;
  };

  const getTrendColor = (trend: number) => {
    if (trend > 0) return 'text-green-600';
    if (trend < 0) return 'text-red-600';
    return 'text-gray-600';
  };

  const formatValue = (value: number, type: string) => {
    switch (type) {
      case 'revenue':
        // UX Audit: валюта — узбекский сум (не рубль ₽).
        return t('misc.km_value_tolocalestring_ru_ru_s', { RU: value.toLocaleString('ru-RU') });
      case 'percentage':
        return `${value.toFixed(1)}%`;
      case 'time':
        return t('misc.km_value_min', { value: value });
      case 'count':
        return value.toLocaleString();
      default:
        return value.toString();
    }
  };

  const renderMetricCard = (key: string, metric: Record<string, unknown>) => {
    const animated = animatedValues[key] || { current: 0, target: 0, trend: 0 };
    const trend = Number(metric.trend ?? 0);
    const isPositive = trend > 0;
    const isNegative = trend < 0;
    const metricType = String(metric.type ?? '');
    const metricFormat = String(metric.format ?? '');
    const metricTarget = Number(metric.target ?? 0);
    const metricComparison = Number(metric.comparison ?? 0);
    const metricGoal = Number(metric.goal ?? 0);

    return (
      <Card key={key} className="relative overflow-hidden">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className={`p-2 rounded-lg ${
              isPositive ? 'bg-green-100' :
              isNegative ? 'bg-red-100' : 'bg-gray-100'}`
              }>
                {getMetricIcon(metricType)}
              </div>
              <div>
                <h3 className="text-sm font-medium text-gray-600">
                  {String(metric.label ?? '')}
                </h3>
                <p className="text-xs text-gray-500">
                  {String(metric.description ?? '')}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              {getTrendIcon(trend)}
              <span className={`text-sm font-medium ${getTrendColor(trend)}`}>
                {Math.abs(trend).toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-baseline space-x-2">
              <span className="text-3xl font-bold text-gray-900">
                {formatValue(animated.current, metricFormat)}
              </span>
              {metric.target != null &&
              <span className="text-sm text-gray-500">
                  / {formatValue(metricTarget, metricFormat)}
                </span>
              }
            </div>

            {showTrends && trend !== 0 &&
            <div className="flex items-center space-x-2">
                <span className="text-xs text-gray-500">vs предыдущий период</span>
                <div className={`flex items-center space-x-1 ${
              isPositive ? 'text-green-600' : 'text-red-600'}`
              }>
                  {isPositive ?
                <TrendingUp className="w-3 h-3" /> :

                <TrendingDown className="w-3 h-3" />
                }
                  <span className="text-xs font-medium">
                    {Math.abs(trend).toFixed(1)}%
                  </span>
                </div>
              </div>
            }

            {showComparisons && metric.comparison != null &&
            <div className="pt-2 border-t border-gray-100">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-500">{t('misc.km_srednee_po_otrasli')}</span>
                  <span className="font-medium">
                    {formatValue(metricComparison, metricFormat)}
                  </span>
                </div>
                <div className="mt-1">
                  <div className="w-full bg-gray-200 rounded-full h-1">
                    <div
                    className={`h-1 rounded-full ${
                    animated.current > metricComparison ? 'bg-green-500' : 'bg-yellow-500'}`
                    }
                    style={{
                      width: `${Math.min(animated.current / metricComparison * 100, 100)}%`
                    }}>
                  </div>
                  </div>
                </div>
              </div>
            }

            {metric.goal != null &&
            <div className="pt-2 border-t border-gray-100">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-500">{t('misc.km_tsel')}</span>
                  <span className="font-medium">
                    {formatValue(metricGoal, metricFormat)}
                  </span>
                </div>
                <div className="mt-1">
                  <div className="w-full bg-gray-200 rounded-full h-1">
                    <div
                    className="h-1 rounded-full bg-blue-500"
                    style={{
                      width: `${Math.min(animated.current / metricGoal * 100, 100)}%`
                    }}>
                  </div>
                  </div>
                </div>
              </div>
            }
          </div>
        </div>

        {/* Декоративный элемент */}
        <div className={`absolute top-0 right-0 w-20 h-20 opacity-5 ${
        isPositive ? 'bg-green-500' :
        isNegative ? 'bg-red-500' : 'bg-gray-500'}`
        } style={{
          clipPath: 'polygon(100% 0, 0 0, 100% 100%)'
        }}></div>
      </Card>);

  };

  const renderSummary = () => {
    if (!data?.summary) return null;

    return (
      <Card className="p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">{t('misc.km_svodka_kpi')}</h3>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="small"
              onClick={() => onExport?.('summary')}>
              
              <Download className="w-4 h-4 mr-2" />
              Экспорт
            </Button>
            <Button
              variant="outline"
              size="small"
              onClick={() => onRefresh?.()}>
              
              <RefreshCw className="w-4 h-4 mr-2" />
              Обновить
            </Button>
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">
              {data.summary.positive_trends || 0}
            </div>
            <div className="text-sm text-gray-600">{t('misc.km_polozhitelnye_trendy')}</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-red-600">
              {data.summary.negative_trends || 0}
            </div>
            <div className="text-sm text-gray-600">{t('misc.km_otritsatelnye_trendy')}</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">
              {data.summary.achieved_goals || 0}
            </div>
            <div className="text-sm text-gray-600">{t('misc.km_dostignutye_tseli')}</div>
          </div>
        </div>
      </Card>);

  };

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {[...Array(8)].map((_, i) =>
        <Card key={i} className="p-6">
            <div className="animate-pulse">
              <div className="flex items-center space-x-3 mb-4">
                <div className="w-10 h-10 bg-gray-200 rounded-lg"></div>
                <div className="space-y-2">
                  <div className="h-4 bg-gray-200 rounded w-24"></div>
                  <div className="h-3 bg-gray-200 rounded w-32"></div>
                </div>
              </div>
              <div className="space-y-3">
                <div className="h-8 bg-gray-200 rounded w-20"></div>
                <div className="h-4 bg-gray-200 rounded w-16"></div>
                <div className="h-2 bg-gray-200 rounded w-full"></div>
              </div>
            </div>
          </Card>
        )}
      </div>);

  }

  if (!data || !data.metrics) {
    return (
      <Card className="p-8 text-center">
        <Target className="w-12 h-12 mx-auto text-gray-400 mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Нет данных KPI
        </h3>
        <p className="text-gray-500 mb-4">
          Загрузите данные для отображения ключевых показателей
        </p>
        <Button onClick={() => onRefresh?.()}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Загрузить данные
        </Button>
      </Card>);

  }

  return (
    <div className="space-y-6">
      {/* Сводка */}
      {renderSummary()}

      {/* Период */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-sm font-medium">{t('misc.km_period')}</span>
          <select
            value={selectedPeriod}
            onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setSelectedPeriod(e.target.value)}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm">
            
            <option value="7d">7 дней</option>
            <option value="30d">30 дней</option>
            <option value="90d">90 дней</option>
            <option value="1y">1 год</option>
          </select>
        </div>
      </div>

      {/* Метрики */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {Object.entries(data.metrics).map(([key, metric]) =>
        renderMetricCard(key, metric as Record<string, unknown>)
        )}
      </div>
    </div>);

};


export default KPIMetrics;
