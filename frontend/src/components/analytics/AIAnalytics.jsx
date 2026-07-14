import { useState, useEffect, useCallback } from 'react';
import {
  MacOSCard,
  Button,
  Badge,
  Input,
  Select,
  MacOSTab,
  Table,
  MacOSEmptyState,
} from '../ui/macos';
import {
  Brain,
  TrendingUp,
  TrendingDown,
  DollarSign,

  BarChart3,
  Activity,
  AlertTriangle,
  CheckCircle,
  RefreshCw,

  Filter,


  Target,
  Settings,
  Database,
  Cpu } from

'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import './AIAnalytics.css';
const AIAnalytics = () => {
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [dateRange, setDateRange] = useState({
    startDate: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    endDate: new Date().toISOString().split('T')[0]
  });
  const [filters, setFilters] = useState({
    userId: null,
    aiFunction: ''
  });

  // Данные аналитики
  const [usageAnalytics, setUsageAnalytics] = useState(null);
  const [learningInsights, setLearningInsights] = useState(null);
  const [usageSummary, setUsageSummary] = useState(null);
  const [costAnalysis, setCostAnalysis] = useState(null);
  const [modelComparison, setModelComparison] = useState(null);

  const loadUsageAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        start_date: dateRange.startDate,
        end_date: dateRange.endDate
      });

      if (filters.userId) params.append('user_id', filters.userId);
      if (filters.aiFunction) params.append('ai_function', filters.aiFunction);

      const response = await api.get(`/analytics/ai/usage-analytics?${params}`);
      setUsageAnalytics(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки аналитики AI:', error);
      toast.error('Ошибка загрузки аналитики AI');
    } finally {
      setLoading(false);
    }
  }, [dateRange.endDate, dateRange.startDate, filters.aiFunction, filters.userId]);

  const loadLearningInsights = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        start_date: dateRange.startDate,
        end_date: dateRange.endDate
      });

      const response = await api.get(`/analytics/ai/learning-insights?${params}`);
      setLearningInsights(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки инсайтов обучения:', error);
      toast.error('Ошибка загрузки инсайтов обучения');
    } finally {
      setLoading(false);
    }
  };

  const loadUsageSummary = useCallback(async () => {
    try {
      const response = await api.get('/analytics/ai/usage-summary?days=30');
      setUsageSummary(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки сводки AI:', error);
    }
  }, []);

  useEffect(() => {
    loadUsageSummary();
    loadUsageAnalytics();
  }, [loadUsageSummary, loadUsageAnalytics]);

  const loadCostAnalysis = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        start_date: dateRange.startDate,
        end_date: dateRange.endDate,
        group_by: 'day'
      });

      const response = await api.get(`/analytics/ai/cost-analysis?${params}`);
      setCostAnalysis(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки анализа затрат:', error);
      toast.error('Ошибка загрузки анализа затрат');
    } finally {
      setLoading(false);
    }
  };

  const loadModelComparison = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        function: 'diagnose_symptoms',
        days: 30
      });

      const response = await api.get(`/analytics/ai/model-comparison?${params}`);
      setModelComparison(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки сравнения моделей:', error);
      toast.error('Ошибка загрузки сравнения моделей');
    } finally {
      setLoading(false);
    }
  };

  const optimizeModels = async () => {
    setLoading(true);
    try {
      const response = await api.post('/analytics/ai/optimize-models');
      toast.success('Оптимизация AI моделей запущена');
      logger.log('Результат оптимизации:', response.data);
    } catch (error) {
      logger.error('Ошибка оптимизации моделей:', error);
      toast.error('Ошибка оптимизации моделей');
    } finally {
      setLoading(false);
    }
  };

  const generateTrainingDataset = async (dataType) => {
    setLoading(true);
    try {
      const response = await api.post('/analytics/ai/generate-training-dataset', {
        data_type: dataType,
        start_date: dateRange.startDate,
        end_date: dateRange.endDate,
        anonymize: true
      });
      toast.success(`Датасет "${dataType}" успешно сгенерирован`);
      logger.log('Информация о датасете:', response.data);
    } catch (error) {
      logger.error('Ошибка генерации датасета:', error);
      toast.error('Ошибка генерации датасета');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 4
    }).format(amount);
  };

  const formatTime = (seconds) => {
    return `${seconds.toFixed(2)}с`;
  };











  const renderOverviewTab = () =>
  <div className="ai-analytics-tab-content">
      {/* Сводка */}
      {usageSummary &&
    <MacOSCard className="ai-analytics-card-padded">
          <div className="ai-analytics-section-header">
            <h3 className="ai-analytics-h3">
              <Activity style={{ width: '20px', height: '20px' }} />
              Сводка AI использования за {usageSummary.period_days} дней
            </h3>
            <div className="ai-analytics-timestamp">
              Обновлено: {new Date(usageSummary.last_updated).toLocaleString()}
            </div>
          </div>

          <div className="ai-analytics-stat-grid">
            <div className="ai-analytics-stat-card ai-analytics-stat-card-info">
              <div className="ai-analytics-stat-value-3xl ai-analytics-stat-value-info">
                {usageSummary.total_requests}
              </div>
              <div className="ai-analytics-stat-label">Всего запросов</div>
            </div>

            <div className="ai-analytics-stat-card ai-analytics-stat-card-success">
              <div className="ai-analytics-stat-value-3xl ai-analytics-stat-value-success">
                {usageSummary.success_rate.toFixed(1)}%
              </div>
              <div className="ai-analytics-stat-label">Успешность</div>
            </div>

            <div className="ai-analytics-stat-card ai-analytics-stat-card-accent-purple">
              <div className="ai-analytics-stat-value-3xl ai-analytics-stat-value-accent-purple">
                {formatTime(usageSummary.average_response_time)}
              </div>
              <div className="ai-analytics-stat-label">Среднее время</div>
            </div>

            <div className="ai-analytics-stat-card ai-analytics-stat-card-warning">
              <div className="ai-analytics-stat-value-3xl ai-analytics-stat-value-warning">
                {formatCurrency(usageSummary.total_cost_usd)}
              </div>
              <div className="ai-analytics-stat-label">Общие затраты</div>
            </div>

            <div className={`ai-analytics-stat-card ${usageSummary.cost_trend === 'increasing' ? 'ai-analytics-stat-card-trend-increasing' : 'ai-analytics-stat-card-trend-decreasing'}`}>
              <div className={`ai-analytics-trend-value ${usageSummary.cost_trend === 'increasing' ? 'ai-analytics-trend-value-increasing' : 'ai-analytics-trend-value-decreasing'}`}>
                {usageSummary.cost_trend === 'increasing' ? <TrendingUp style={{ width: '20px', height: '20px' }} /> : <TrendingDown style={{ width: '20px', height: '20px' }} />}
                {usageSummary.cost_trend}
              </div>
              <div className="ai-analytics-stat-label">Тренд затрат</div>
            </div>

            <div className="ai-analytics-stat-card ai-analytics-stat-card-accent-blue">
              <div className="ai-analytics-stat-value-2xl ai-analytics-stat-value-accent-blue">
                {usageSummary.most_used_function || 'N/A'}
              </div>
              <div className="ai-analytics-stat-label">Популярная функция</div>
            </div>
          </div>

          {usageSummary.recommendations && usageSummary.recommendations.length > 0 &&
      <div className="ai-analytics-mt-4">
              <h4 className="ai-analytics-h4">
                Рекомендации
              </h4>
              <div className="ai-analytics-recommendations-list">
                {usageSummary.recommendations.map((recommendation, index) =>
          <div
            key={index}
            className="ai-analytics-recommendation-item ai-analytics-recommendation-item-info">
                    <CheckCircle style={{ width: '16px', height: '16px', color: 'var(--mac-info)' }} />
                    <span className="ai-analytics-recommendation-text">
                      {recommendation}
                    </span>
                  </div>
          )}
              </div>
            </div>
      }
        </MacOSCard>
    }

      {/* Быстрые действия */}
      <MacOSCard className="ai-analytics-card-padded">
        <h3 className="ai-analytics-h3-mb16">
          <Settings style={{ width: '20px', height: '20px' }} />
          Быстрые действия
        </h3>

        <div className="ai-analytics-stat-grid-250">
          <Button
          onClick={optimizeModels}
          disabled={loading}
          variant="primary"
          className="ai-analytics-action-btn">
            {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Target style={{ width: '16px', height: '16px' }} />}
            Оптимизировать модели
          </Button>

          <Button
          onClick={() => generateTrainingDataset('diagnostic_patterns')}
          disabled={loading}
          variant="success"
          className="ai-analytics-action-btn">
            {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Database style={{ width: '16px', height: '16px' }} />}
            Генерировать датасет диагностики
          </Button>

          <Button
          onClick={() => generateTrainingDataset('treatment_outcomes')}
          disabled={loading}
          variant="secondary"
          className="ai-analytics-action-btn">
            {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Database style={{ width: '16px', height: '16px' }} />}
            Генерировать датасет лечения
          </Button>

          <Button
          onClick={loadModelComparison}
          disabled={loading}
          variant="warning"
          className="ai-analytics-action-btn">
            {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <BarChart3 style={{ width: '16px', height: '16px' }} />}
            Сравнить модели
          </Button>
        </div>
      </MacOSCard>
    </div>;


  const renderUsageTab = () =>
  <div className="ai-analytics-tab-content">
      {usageAnalytics &&
    <>
          {/* Общая статистика */}
          <MacOSCard className="ai-analytics-card-padded">
            <h3 className="ai-analytics-h3-mb16">
              <BarChart3 style={{ width: '20px', height: '20px' }} />
              Статистика использования ({usageAnalytics.period.start_date} - {usageAnalytics.period.end_date})
            </h3>

            <div className="ai-analytics-stat-grid-sm">
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-xl ai-analytics-stat-value-info">
                  {usageAnalytics.usage_statistics.total_requests}
                </div>
                <div className="ai-analytics-stat-label-xs">Всего запросов</div>
              </div>
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-xl ai-analytics-stat-value-success">
                  {usageAnalytics.usage_statistics.success_rate?.toFixed(1)}%
                </div>
                <div className="ai-analytics-stat-label-xs">Успешность</div>
              </div>
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-xl ai-analytics-stat-value-accent-purple">
                  {formatTime(usageAnalytics.usage_statistics.average_execution_time)}
                </div>
                <div className="ai-analytics-stat-label-xs">Среднее время</div>
              </div>
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-xl ai-analytics-stat-value-warning">
                  {usageAnalytics.usage_statistics.total_tokens_used}
                </div>
                <div className="ai-analytics-stat-label-xs">Токенов</div>
              </div>
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-xl ai-analytics-stat-value-error">
                  {formatCurrency(usageAnalytics.usage_statistics.total_cost_usd)}
                </div>
                <div className="ai-analytics-stat-label-xs">Затраты</div>
              </div>
            </div>
          </MacOSCard>

          {/* Разбивка по функциям */}
          {Object.keys(usageAnalytics.function_breakdown).length > 0 &&
      <MacOSCard className="ai-analytics-card-padded">
              <h3 className="ai-analytics-h3-mb16">
                По AI функциям
              </h3>
              <div className="ai-analytics-grid-gap">
                {Object.entries(usageAnalytics.function_breakdown).map(([func, stats]) =>
          <div
            key={func}
            className="ai-analytics-function-card">
                    <div>
                      <div className="ai-analytics-function-name">
                        {func}
                      </div>
                      <div className="ai-analytics-function-stats">
                        {stats.requests} запросов • {stats.success_rate?.toFixed(1)}% успешность
                      </div>
                    </div>
                    <div className="ai-analytics-stat-text-right">
                      <div className="ai-analytics-stat-value-lg ai-analytics-stat-value-info">
                        {formatTime(stats.average_time)}
                      </div>
                      <div className="ai-analytics-timestamp">
                        {formatCurrency(stats.total_cost)}
                      </div>
                    </div>
                  </div>
          )}
              </div>
            </MacOSCard>
      }

          {/* Рекомендации */}
          {usageAnalytics.recommendations && usageAnalytics.recommendations.length > 0 &&
      <MacOSCard className="ai-analytics-card-padded">
              <h3 className="ai-analytics-h3-mb16">
                Рекомендации по оптимизации
              </h3>
              <div className="ai-analytics-recommendations-list-gap2">
                {usageAnalytics.recommendations.map((recommendation, index) =>
          <div
            key={index}
            className="ai-analytics-recommendation-item-lg ai-analytics-recommendation-item-warning">
                    <AlertTriangle style={{ width: '16px', height: '16px', color: 'var(--mac-warning)' }} />
                    <span className="ai-analytics-recommendation-text-default">
                      {recommendation}
                    </span>
                  </div>
          )}
              </div>
            </MacOSCard>
      }
        </>
    }
    </div>;


  const renderLearningTab = () =>
  <div className="ai-analytics-tab-content">
      <div className="ai-analytics-section-header-no-mb">
        <h3 className="ai-analytics-h3">
          Инсайты для обучения AI
        </h3>
        <Button
        onClick={loadLearningInsights}
        disabled={loading}
        variant="outline"
        className="ai-analytics-action-btn-sm">
          {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Brain style={{ width: '16px', height: '16px' }} />}
          Обновить
        </Button>
      </div>

      {learningInsights &&
    <>
          {/* Медицинские паттерны */}
          {learningInsights.medical_patterns &&
      <MacOSCard className="ai-analytics-card-padded">
              <h4 className="ai-analytics-h4">
                Медицинские паттерны
              </h4>

              {learningInsights.medical_patterns.common_symptoms && Array.isArray(learningInsights.medical_patterns.common_symptoms) &&
        <div className="ai-analytics-mb-4">
                  <h5 className="ai-analytics-h5">
                    Частые симптомы
                  </h5>
                  <div className="ai-analytics-symptoms-wrap">
                    {learningInsights.medical_patterns.common_symptoms.map((symptom, index) =>
            <Badge
              key={index}
              variant="secondary"
              className="ai-analytics-badge-xs">
                        {symptom}
                      </Badge>
            )}
                  </div>
                </div>
        }

              {learningInsights.medical_patterns.diagnosis_frequency &&
        <div>
                  <h5 className="ai-analytics-h5">
                    Топ диагнозы
                  </h5>
                  <div className="ai-analytics-grid-gap-1">
                    {learningInsights.medical_patterns.diagnosis_frequency.top_diagnoses?.map((item, index) =>
            <div
              key={index}
              className="ai-analytics-diagnosis-row">
                        <span className="ai-analytics-diagnosis-name">{item.diagnosis}</span>
                        <span className="ai-analytics-diagnosis-count">
                          {item.count} ({item.percentage}%)
                        </span>
                      </div>
            )}
                  </div>
                </div>
        }
            </MacOSCard>
      }

          {/* Точность диагностики */}
          {learningInsights.diagnostic_accuracy &&
      <MacOSCard className="ai-analytics-card-padded">
              <h4 className="ai-analytics-h4">
                Точность диагностики
              </h4>

              <div className="ai-analytics-stat-grid-sm">
                <div className="ai-analytics-stat-text-center">
                  <div className="ai-analytics-stat-value-3xl ai-analytics-stat-value-info">
                    {learningInsights.diagnostic_accuracy.ai_vs_doctor_accuracy?.ai_accuracy}%
                  </div>
                  <div className="ai-analytics-stat-label-xs">AI точность</div>
                </div>
                <div className="ai-analytics-stat-text-center">
                  <div className="ai-analytics-stat-value-3xl ai-analytics-stat-value-success">
                    {learningInsights.diagnostic_accuracy.ai_vs_doctor_accuracy?.doctor_accuracy}%
                  </div>
                  <div className="ai-analytics-stat-label-xs">Врач точность</div>
                </div>
                <div className="ai-analytics-stat-text-center">
                  <div className="ai-analytics-stat-value-3xl ai-analytics-stat-value-accent-purple">
                    {learningInsights.diagnostic_accuracy.ai_vs_doctor_accuracy?.agreement_rate}%
                  </div>
                  <div className="ai-analytics-stat-label-xs">Согласованность</div>
                </div>
              </div>
            </MacOSCard>
      }

          {/* Рекомендации для обучения */}
          {learningInsights.learning_recommendations &&
      <MacOSCard className="ai-analytics-card-padded">
              <h4 className="ai-analytics-h4">
                Рекомендации для обучения
              </h4>
              <div className="ai-analytics-recommendations-list-gap2">
                {learningInsights.learning_recommendations.map((recommendation, index) =>
          <div
            key={index}
            className="ai-analytics-recommendation-item-lg ai-analytics-recommendation-item-success">
                    <CheckCircle style={{ width: '16px', height: '16px', color: 'var(--mac-success)' }} />
                    <span className="ai-analytics-recommendation-text-default">
                      {recommendation}
                    </span>
                  </div>
          )}
              </div>
            </MacOSCard>
      }
        </>
    }
    </div>;


  const renderCostTab = () =>
  <div className="ai-analytics-tab-content">
      <div className="ai-analytics-section-header-no-mb">
        <h3 className="ai-analytics-h3">
          Анализ затрат на AI
        </h3>
        <Button
        onClick={loadCostAnalysis}
        disabled={loading}
        variant="outline"
        className="ai-analytics-action-btn-sm">
          {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <DollarSign style={{ width: '16px', height: '16px' }} />}
          Загрузить
        </Button>
      </div>

      {costAnalysis &&
    <>
          {/* Сводка затрат */}
          <MacOSCard className="ai-analytics-card-padded">
            <h4 className="ai-analytics-h4">
              Сводка затрат
            </h4>

            <div className="ai-analytics-stat-grid-sm">
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-2xl ai-analytics-stat-value-success">
                  {formatCurrency(costAnalysis.summary?.total_cost_usd || 0)}
                </div>
                <div className="ai-analytics-stat-label-xs">Общие затраты</div>
              </div>
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-2xl ai-analytics-stat-value-info">
                  {formatCurrency(costAnalysis.summary?.average_daily_cost || 0)}
                </div>
                <div className="ai-analytics-stat-label-xs">В день</div>
              </div>
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-2xl ai-analytics-stat-value-accent-purple">
                  {formatCurrency(costAnalysis.forecasts?.monthly_usd || 0)}
                </div>
                <div className="ai-analytics-stat-label-xs">Прогноз на месяц</div>
              </div>
            </div>
          </MacOSCard>

          {/* Затраты по функциям */}
          {costAnalysis.function_costs && Object.keys(costAnalysis.function_costs).length > 0 &&
      <MacOSCard className="ai-analytics-card-padded">
              <h4 className="ai-analytics-h4">
                Затраты по функциям
              </h4>
              <div className="ai-analytics-grid-gap">
                {Object.entries(costAnalysis.function_costs).map(([func, data]) =>
          <div
            key={func}
            className="ai-analytics-function-card">
                    <div>
                      <div className="ai-analytics-function-name">
                        {func}
                      </div>
                      <div className="ai-analytics-function-stats">
                        {data.requests} запросов • {data.cost_percentage?.toFixed(1)}% от общих затрат
                      </div>
                    </div>
                    <div className="ai-analytics-stat-text-right">
                      <div className="ai-analytics-stat-value-lg ai-analytics-stat-value-warning">
                        {formatCurrency(data.total_cost)}
                      </div>
                      <div className="ai-analytics-timestamp">
                        {formatCurrency(data.average_cost_per_request)} за запрос
                      </div>
                    </div>
                  </div>
          )}
              </div>
            </MacOSCard>
      }

          {/* Рекомендации по оптимизации затрат */}
          {costAnalysis.cost_optimization?.recommendations &&
      <MacOSCard className="ai-analytics-card-padded">
              <h4 className="ai-analytics-h4">
                Оптимизация затрат
              </h4>

              <div className="ai-analytics-cost-savings">
                <div className="ai-analytics-cost-savings-amount">
                  Потенциальная экономия: {formatCurrency(costAnalysis.cost_optimization.potential_savings?.amount_usd || 0)}
                </div>
                <div className="ai-analytics-stat-label">
                  ({costAnalysis.cost_optimization.potential_savings?.percentage || 0}% от текущих затрат)
                </div>
              </div>

              <div className="ai-analytics-recommendations-list-gap2">
                {costAnalysis.cost_optimization.recommendations.map((recommendation, index) =>
          <div
            key={index}
            className="ai-analytics-recommendation-item ai-analytics-recommendation-item-info">
                    <DollarSign style={{ width: '16px', height: '16px', color: 'var(--mac-info)' }} />
                    <span className="ai-analytics-recommendation-text-default">
                      {recommendation}
                    </span>
                  </div>
          )}
              </div>
            </MacOSCard>
      }
        </>
    }
    </div>;


  const renderModelsTab = () =>
  <div className="ai-analytics-tab-content">
      <div className="ai-analytics-section-header-no-mb">
        <h3 className="ai-analytics-h3">
          Сравнение AI моделей
        </h3>
        <Button
        onClick={loadModelComparison}
        disabled={loading}
        variant="outline"
        className="ai-analytics-action-btn-sm">
          {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Cpu style={{ width: '16px', height: '16px' }} />}
          Загрузить
        </Button>
      </div>

      {modelComparison &&
    <>
          {/* Сравнительная таблица */}
          <MacOSCard className="ai-analytics-card-padded">
            <h4 className="ai-analytics-h4">
              Сравнение моделей для функции: {modelComparison.function}
            </h4>
            
            <Table
          columns={[
          { key: 'model', label: 'Модель', width: '20%' },
          { key: 'accuracy', label: 'Точность', width: '15%', align: 'center' },
          { key: 'speed', label: 'Скорость (с)', width: '15%', align: 'center' },
          { key: 'cost', label: 'Стоимость', width: '15%', align: 'center' },
          { key: 'satisfaction', label: 'Удовлетворенность', width: '15%', align: 'center' },
          { key: 'reliability', label: 'Надежность', width: '20%', align: 'center' }]
          }
          data={Object.entries(modelComparison.models).map(([model, data]) => ({
            model: <span className="ai-analytics-function-name">{model}</span>,
            accuracy: `${data.accuracy}%`,
            speed: data.speed,
            cost: formatCurrency(data.cost_per_request),
            satisfaction: `${data.user_satisfaction}/5`,
            reliability: `${data.reliability}%`
          }))}
          emptyState={
          <MacOSEmptyState
            icon={Cpu}
            title="Нет данных о моделях"
            description="Загрузите данные для сравнения AI моделей" />

          } />

          </MacOSCard>

          {/* Рекомендации */}
          <MacOSCard className="ai-analytics-card-padded">
            <h4 className="ai-analytics-h4">
              Рекомендации
            </h4>

            <div className="ai-analytics-stat-grid ai-analytics-mb-4">
              {Object.entries(modelComparison.recommendations).map(([category, model]) =>
          <div
            key={category}
            className="ai-analytics-model-rec-card">
                  <div className="ai-analytics-model-rec-label">
                    {category.replace('best_for_', '').replace('_', ' ')}
                  </div>
                  <div className="ai-analytics-model-rec-value">
                    {model}
                  </div>
                </div>
          )}
            </div>

            <div className="ai-analytics-recommendations-list-gap2">
              {modelComparison.optimization_suggestions?.map((suggestion, index) =>
          <div
            key={index}
            className="ai-analytics-recommendation-item ai-analytics-recommendation-item-success">
                  <Target style={{ width: '16px', height: '16px', color: 'var(--mac-success)' }} />
                  <span className="ai-analytics-recommendation-text-default">
                    {suggestion}
                  </span>
                </div>
          )}
            </div>
          </MacOSCard>
        </>
    }
    </div>;



  return (
    <div className="ai-analytics-root">
      {/* Заголовок */}
      <div className="ai-analytics-header">
        <Brain style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
        <div>
          <h1 className="ai-analytics-h1">
          Расширенная аналитика AI
          </h1>
          <p className="ai-analytics-h1-subtitle">
            Мониторинг и оптимизация использования искусственного интеллекта
          </p>
        </div>
      </div>

      {/* Фильтры */}
      <MacOSCard className="ai-analytics-card-padded-sm">
        <div className="ai-analytics-filter-grid">
          <div>
            <label className="ai-analytics-filter-label">
              Начальная дата
            </label>
            <Input
              type="date"
              value={dateRange.startDate}
              onChange={(e) => setDateRange({ ...dateRange, startDate: e.target.value })} />

          </div>
          <div>
            <label className="ai-analytics-filter-label">
              Конечная дата
            </label>
            <Input
              type="date"
              value={dateRange.endDate}
              onChange={(e) => setDateRange({ ...dateRange, endDate: e.target.value })} />

          </div>
          <div>
            <label className="ai-analytics-filter-label">
              AI функция
            </label>
            <Select
              value={filters.aiFunction}
              onChange={(e) => setFilters({ ...filters, aiFunction: e.target.value })}
              options={[
              { value: '', label: 'Все функции' },
              { value: 'diagnose_symptoms', label: 'Диагностика симптомов' },
              { value: 'analyze_medical_image', label: 'Анализ изображений' },
              { value: 'generate_treatment_plan', label: 'Планы лечения' },
              { value: 'check_drug_interactions', label: 'Взаимодействия препаратов' },
              { value: 'assess_patient_risk', label: 'Оценка рисков' }]
              } />

          </div>
          <div className="ai-analytics-action-btn-end">
            <Button
              onClick={loadUsageAnalytics}
              disabled={loading}
              variant="primary"
              className="ai-analytics-action-btn-full">

              {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Filter style={{ width: '16px', height: '16px' }} />}
              Применить
            </Button>
          </div>
        </div>
      </MacOSCard>

      {/* Вкладки */}
      <MacOSTab
        tabs={[
        { id: 'overview', label: 'Обзор', icon: Activity },
        { id: 'usage', label: 'Использование', icon: BarChart3 },
        { id: 'learning', label: 'Обучение', icon: Brain },
        { id: 'cost', label: 'Затраты', icon: DollarSign },
        { id: 'models', label: 'Модели', icon: Cpu }]
        }
        activeTab={activeTab}
        onTabChange={setActiveTab}
        size="md"
        variant="default" />
      

      {/* Содержимое вкладок */}
      {activeTab === 'overview' && renderOverviewTab()}
      {activeTab === 'usage' && renderUsageTab()}
      {activeTab === 'learning' && renderLearningTab()}
      {activeTab === 'cost' && renderCostTab()}
      {activeTab === 'models' && renderModelsTab()}
    </div>);

};

export default AIAnalytics;
