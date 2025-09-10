import React, { useState, useEffect } from 'react';
import { Card, Button } from '../../design-system/components';
import { 
  TrendingUp, 
  TrendingDown, 
  Target, 
  AlertTriangle,
  CheckCircle,
  Clock,
  BarChart3,
  PieChart,
  Activity,
  RefreshCw,
  Download,
  Eye,
  Settings
} from 'lucide-react';

/**
 * Компонент предиктивной аналитики
 * Включает прогнозы, тренды, рекомендации
 */
const PredictiveAnalytics = ({ 
  data, 
  loading = false, 
  onRefresh,
  onExport,
  showRecommendations = true
}) => {
  const [selectedMetric, setSelectedMetric] = useState('revenue');
  const [forecastPeriod, setForecastPeriod] = useState('30d');
  const [showDetails, setShowDetails] = useState(false);

  const metricOptions = [
    { id: 'revenue', label: 'Доходы', icon: TrendingUp, color: 'green' },
    { id: 'patients', label: 'Пациенты', icon: Activity, color: 'blue' },
    { id: 'appointments', label: 'Записи', icon: Clock, color: 'purple' },
    { id: 'efficiency', label: 'Эффективность', icon: Target, color: 'orange' }
  ];

  const periodOptions = [
    { id: '7d', label: '7 дней' },
    { id: '30d', label: '30 дней' },
    { id: '90d', label: '90 дней' },
    { id: '1y', label: '1 год' }
  ];

  const getMetricIcon = (metricId) => {
    const metric = metricOptions.find(m => m.id === metricId);
    return metric ? <metric.icon className="w-5 h-5" /> : <Activity className="w-5 h-5" />;
  };

  const getMetricColor = (metricId) => {
    const metric = metricOptions.find(m => m.id === metricId);
    return metric?.color || 'gray';
  };

  const renderForecastCard = (forecast) => {
    const confidence = forecast.confidence || 0;
    const trend = forecast.trend || 0;
    const isPositive = trend > 0;
    const isHighConfidence = confidence > 0.8;

    return (
      <Card key={forecast.period} className="relative overflow-hidden">
        <div className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2">
              {getMetricIcon(selectedMetric)}
              <h4 className="font-semibold">{forecast.period}</h4>
            </div>
            <div className="flex items-center space-x-2">
              {isPositive ? (
                <TrendingUp className="w-4 h-4 text-green-500" />
              ) : (
                <TrendingDown className="w-4 h-4 text-red-500" />
              )}
              <span className={`text-sm font-medium ${
                isPositive ? 'text-green-600' : 'text-red-600'
              }`}>
                {Math.abs(trend).toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-baseline space-x-2">
              <span className="text-2xl font-bold">
                {forecast.value.toLocaleString()}
              </span>
              <span className="text-sm text-gray-500">
                {forecast.unit || ''}
              </span>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">Уверенность прогноза</span>
                <span className={`font-medium ${
                  isHighConfidence ? 'text-green-600' : 'text-yellow-600'
                }`}>
                  {(confidence * 100).toFixed(0)}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full ${
                    isHighConfidence ? 'bg-green-500' : 'bg-yellow-500'
                  }`}
                  style={{ width: `${confidence * 100}%` }}
                ></div>
              </div>
            </div>

            {forecast.factors && (
              <div className="pt-2 border-t border-gray-100">
                <div className="text-xs text-gray-600 mb-1">Ключевые факторы:</div>
                <div className="space-y-1">
                  {forecast.factors.map((factor, index) => (
                    <div key={index} className="flex items-center space-x-2 text-xs">
                      <div className={`w-2 h-2 rounded-full ${
                        factor.impact > 0 ? 'bg-green-500' : 'bg-red-500'
                      }`}></div>
                      <span>{factor.name}</span>
                      <span className="text-gray-500">
                        ({factor.impact > 0 ? '+' : ''}{factor.impact.toFixed(1)}%)
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Индикатор уверенности */}
        <div className={`absolute top-0 right-0 w-16 h-16 opacity-10 ${
          isHighConfidence ? 'bg-green-500' : 'bg-yellow-500'
        }`} style={{
          clipPath: 'polygon(100% 0, 0 0, 100% 100%)'
        }}></div>
      </Card>
    );
  };

  const renderRecommendations = () => {
    if (!data?.recommendations || !showRecommendations) return null;

    return (
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Рекомендации</h3>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onExport?.('recommendations')}
            >
              <Download className="w-4 h-4 mr-2" />
              Экспорт
            </Button>
          </div>
        </div>

        <div className="space-y-4">
          {data.recommendations.map((rec, index) => (
            <div key={index} className="flex items-start space-x-3 p-3 bg-gray-50 rounded-lg">
              <div className={`p-1 rounded-full ${
                rec.priority === 'high' ? 'bg-red-100' :
                rec.priority === 'medium' ? 'bg-yellow-100' : 'bg-green-100'
              }`}>
                {rec.priority === 'high' ? (
                  <AlertTriangle className="w-4 h-4 text-red-600" />
                ) : rec.priority === 'medium' ? (
                  <Clock className="w-4 h-4 text-yellow-600" />
                ) : (
                  <CheckCircle className="w-4 h-4 text-green-600" />
                )}
              </div>
              <div className="flex-1">
                <h4 className="font-medium text-gray-900">{rec.title}</h4>
                <p className="text-sm text-gray-600 mt-1">{rec.description}</p>
                <div className="flex items-center space-x-4 mt-2 text-xs text-gray-500">
                  <span>Приоритет: {rec.priority}</span>
                  <span>Влияние: {rec.impact}%</span>
                  <span>Срок: {rec.timeline}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    );
  };

  const renderTrendAnalysis = () => {
    if (!data?.trends) return null;

    return (
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Анализ трендов</h3>
        
        <div className="space-y-4">
          {data.trends.map((trend, index) => (
            <div key={index} className="flex items-center justify-between p-3 border rounded-lg">
              <div className="flex items-center space-x-3">
                <div className={`p-2 rounded-lg ${
                  trend.direction === 'up' ? 'bg-green-100' : 'bg-red-100'
                }`}>
                  {trend.direction === 'up' ? (
                    <TrendingUp className="w-4 h-4 text-green-600" />
                  ) : (
                    <TrendingDown className="w-4 h-4 text-red-600" />
                  )}
                </div>
                <div>
                  <h4 className="font-medium">{trend.metric}</h4>
                  <p className="text-sm text-gray-600">{trend.description}</p>
                </div>
              </div>
              <div className="text-right">
                <div className={`text-sm font-medium ${
                  trend.direction === 'up' ? 'text-green-600' : 'text-red-600'
                }`}>
                  {trend.change}%
                </div>
                <div className="text-xs text-gray-500">
                  за {trend.period}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    );
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <Card className="p-6">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-gray-200 rounded w-1/4"></div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-32 bg-gray-200 rounded"></div>
              ))}
            </div>
          </div>
        </Card>
      </div>
    );
  }

  if (!data) {
    return (
      <Card className="p-8 text-center">
        <Target className="w-12 h-12 mx-auto text-gray-400 mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">
          Нет данных для предиктивной аналитики
        </h3>
        <p className="text-gray-500 mb-4">
          Загрузите исторические данные для создания прогнозов
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
      {/* Настройки */}
      <Card className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium">Метрика:</span>
              <select
                value={selectedMetric}
                onChange={(e) => setSelectedMetric(e.target.value)}
                className="px-3 py-1 border border-gray-300 rounded-md text-sm"
              >
                {metricOptions.map(option => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            
            <div className="flex items-center space-x-2">
              <span className="text-sm font-medium">Период:</span>
              <select
                value={forecastPeriod}
                onChange={(e) => setForecastPeriod(e.target.value)}
                className="px-3 py-1 border border-gray-300 rounded-md text-sm"
              >
                {periodOptions.map(option => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowDetails(!showDetails)}
            >
              <Eye className="w-4 h-4 mr-2" />
              {showDetails ? 'Скрыть детали' : 'Показать детали'}
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
      </Card>

      {/* Прогнозы */}
      {data.forecasts && (
        <div>
          <h3 className="text-lg font-semibold mb-4">Прогнозы на {forecastPeriod}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.forecasts.map(forecast => renderForecastCard(forecast))}
          </div>
        </div>
      )}

      {/* Рекомендации */}
      {renderRecommendations()}

      {/* Анализ трендов */}
      {renderTrendAnalysis()}
    </div>
  );
};

export default PredictiveAnalytics;
