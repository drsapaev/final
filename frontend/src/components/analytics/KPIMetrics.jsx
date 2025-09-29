import React, { useState, useEffect } from 'react';
import { Card, Button } from '../ui/native';
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
  AlertCircle,
  BarChart3,
  PieChart,
  Eye,
  Download,
  RefreshCw
} from 'lucide-react';

/**
 * Компонент для отображения KPI метрик
 * Включает анимированные карточки, тренды, сравнения
 */
const KPIMetrics = ({ 
  data, 
  loading = false, 
  onRefresh,
  onExport,
  showTrends = true,
  showComparisons = true
}) => {
  const [animatedValues, setAnimatedValues] = useState({});
  const [selectedPeriod, setSelectedPeriod] = useState('30d');

  useEffect(() => {
    if (data?.metrics) {
      animateValues();
    }
  }, [data]);

  const animateValues = () => {
    const metrics = data.metrics;
    const animated = {};
    
    Object.keys(metrics).forEach(key => {
      const metric = metrics[key];
      animated[key] = {
        current: 0,
        target: metric.value,
        trend: metric.trend || 0
      };
    });
    
    setAnimatedValues(animated);
    
    // Анимация значений
    Object.keys(animated).forEach(key => {
      const metric = metrics[key];
      const duration = 2000;
      const steps = 60;
      const stepValue = metric.value / steps;
      const stepDuration = duration / steps;
      
      let currentStep = 0;
      const interval = setInterval(() => {
        currentStep++;
        setAnimatedValues(prev => ({
          ...prev,
          [key]: {
            ...prev[key],
            current: Math.min(stepValue * currentStep, metric.value)
          }
        }));
        
        if (currentStep >= steps) {
          clearInterval(interval);
        }
      }, stepDuration);
    });
  };

  const getMetricIcon = (type) => {
    const iconStyle = { width: '20px', height: '20px' };
    switch (type) {
      case 'revenue': return <DollarSign style={iconStyle} />;
      case 'patients': return <Users style={iconStyle} />;
      case 'appointments': return <Calendar style={iconStyle} />;
      case 'doctors': return <Award style={iconStyle} />;
      case 'efficiency': return <Target style={iconStyle} />;
      case 'satisfaction': return <CheckCircle style={iconStyle} />;
      case 'wait_time': return <Clock style={iconStyle} />;
      default: return <Activity style={iconStyle} />;
    }
  };

  const getTrendIcon = (trend) => {
    if (trend > 0) return <TrendingUp className="w-4 h-4 text-green-500" />;
    if (trend < 0) return <TrendingDown className="w-4 h-4 text-red-500" />;
    return <Activity className="w-4 h-4 text-gray-500" />;
  };

  const getTrendColor = (trend) => {
    if (trend > 0) return 'text-green-600';
    if (trend < 0) return 'text-red-600';
    return 'text-gray-600';
  };

  const formatValue = (value, type) => {
    switch (type) {
      case 'revenue':
        return `₽${value.toLocaleString()}`;
      case 'percentage':
        return `${value.toFixed(1)}%`;
      case 'time':
        return `${value} мин`;
      case 'count':
        return value.toLocaleString();
      default:
        return value.toString();
    }
  };

  const renderMetricCard = (key, metric) => {
    const animated = animatedValues[key] || { current: 0, trend: 0 };
    const trend = metric.trend || 0;
    const isPositive = trend > 0;
    const isNegative = trend < 0;

    return (
      <Card key={key} className="relative overflow-hidden">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className={`p-2 rounded-lg ${
                isPositive ? 'bg-green-100' : 
                isNegative ? 'bg-red-100' : 'bg-gray-100'
              }`}>
                {getMetricIcon(metric.type)}
              </div>
              <div>
                <h3 className="text-sm font-medium text-gray-600">
                  {metric.label}
                </h3>
                <p className="text-xs text-gray-500">
                  {metric.description}
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
                {formatValue(animated.current, metric.format)}
              </span>
              {metric.target && (
                <span className="text-sm text-gray-500">
                  / {formatValue(metric.target, metric.format)}
                </span>
              )}
            </div>

            {showTrends && trend !== 0 && (
              <div className="flex items-center space-x-2">
                <span className="text-xs text-gray-500">vs предыдущий период</span>
                <div className={`flex items-center space-x-1 ${
                  isPositive ? 'text-green-600' : 'text-red-600'
                }`}>
                  {isPositive ? (
                    <TrendingUp className="w-3 h-3" />
                  ) : (
                    <TrendingDown className="w-3 h-3" />
                  )}
                  <span className="text-xs font-medium">
                    {Math.abs(trend).toFixed(1)}%
                  </span>
                </div>
              </div>
            )}

            {showComparisons && metric.comparison && (
              <div className="pt-2 border-t border-gray-100">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-500">Среднее по отрасли</span>
                  <span className="font-medium">
                    {formatValue(metric.comparison, metric.format)}
                  </span>
                </div>
                <div className="mt-1">
                  <div className="w-full bg-gray-200 rounded-full h-1">
                    <div 
                      className={`h-1 rounded-full ${
                        animated.current > metric.comparison ? 'bg-green-500' : 'bg-yellow-500'
                      }`}
                      style={{ 
                        width: `${Math.min((animated.current / metric.comparison) * 100, 100)}%` 
                      }}
                    ></div>
                  </div>
                </div>
              </div>
            )}

            {metric.goal && (
              <div className="pt-2 border-t border-gray-100">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-500">Цель</span>
                  <span className="font-medium">
                    {formatValue(metric.goal, metric.format)}
                  </span>
                </div>
                <div className="mt-1">
                  <div className="w-full bg-gray-200 rounded-full h-1">
                    <div 
                      className="h-1 rounded-full bg-blue-500"
                      style={{ 
                        width: `${Math.min((animated.current / metric.goal) * 100, 100)}%` 
                      }}
                    ></div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Декоративный элемент */}
        <div className={`absolute top-0 right-0 w-20 h-20 opacity-5 ${
          isPositive ? 'bg-green-500' : 
          isNegative ? 'bg-red-500' : 'bg-gray-500'
        }`} style={{
          clipPath: 'polygon(100% 0, 0 0, 100% 100%)'
        }}></div>
      </Card>
    );
  };

  const renderSummary = () => {
    if (!data?.summary) return null;

    return (
      <Card className="p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Сводка KPI</h3>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onExport?.('summary')}
            >
              <Download className="w-4 h-4 mr-2" />
              Экспорт
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onRefresh?.()}
            >
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
            <div className="text-sm text-gray-600">Положительные тренды</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-red-600">
              {data.summary.negative_trends || 0}
            </div>
            <div className="text-sm text-gray-600">Отрицательные тренды</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">
              {data.summary.achieved_goals || 0}
            </div>
            <div className="text-sm text-gray-600">Достигнутые цели</div>
          </div>
        </div>
      </Card>
    );
  };

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {[...Array(8)].map((_, i) => (
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
        ))}
      </div>
    );
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
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Сводка */}
      {renderSummary()}

      {/* Период */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-sm font-medium">Период:</span>
          <select
            value={selectedPeriod}
            onChange={(e) => setSelectedPeriod(e.target.value)}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm"
          >
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
          renderMetricCard(key, metric)
        )}
      </div>
    </div>
  );
};

export default KPIMetrics;

