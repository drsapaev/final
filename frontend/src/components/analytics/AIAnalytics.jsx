import React, { useState, useEffect } from 'react';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSBadge, 
  MacOSInput, 
  MacOSSelect,
  MacOSTab,
  MacOSTable,
  MacOSEmptyState,
  MacOSLoadingSkeleton,
  MacOSStatCard
} from '../ui/macos';
import { 
  Brain, 
  TrendingUp, 
  TrendingDown, 
  DollarSign, 
  Clock,
  BarChart3,
  Activity,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Download,
  Filter,
  Eye,
  Zap,
  Target,
  Settings,
  Database,
  Cpu,
  PieChart
} from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../utils/api';

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

  useEffect(() => {
    loadUsageSummary();
    loadUsageAnalytics();
  }, [dateRange, filters]);

  const loadUsageAnalytics = async () => {
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
      console.error('Ошибка загрузки аналитики AI:', error);
      toast.error('Ошибка загрузки аналитики AI');
    } finally {
      setLoading(false);
    }
  };

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
      console.error('Ошибка загрузки инсайтов обучения:', error);
      toast.error('Ошибка загрузки инсайтов обучения');
    } finally {
      setLoading(false);
    }
  };

  const loadUsageSummary = async () => {
    try {
      const response = await api.get('/analytics/ai/usage-summary?days=30');
      setUsageSummary(response.data);
    } catch (error) {
      console.error('Ошибка загрузки сводки AI:', error);
    }
  };

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
      console.error('Ошибка загрузки анализа затрат:', error);
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
      console.error('Ошибка загрузки сравнения моделей:', error);
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
      console.log('Результат оптимизации:', response.data);
    } catch (error) {
      console.error('Ошибка оптимизации моделей:', error);
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
      console.log('Информация о датасете:', response.data);
    } catch (error) {
      console.error('Ошибка генерации датасета:', error);
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

  const getPerformanceColor = (rating) => {
    switch (rating) {
      case 'Отлично': return 'var(--mac-success)';
      case 'Хорошо': return 'var(--mac-info)';
      case 'Удовлетворительно': return 'var(--mac-warning)';
      case 'Требует улучшения': return 'var(--mac-error)';
      default: return 'var(--mac-text-tertiary)';
    }
  };

  const renderOverviewTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Сводка */}
      {usageSummary && (
        <MacOSCard style={{ padding: '24px' }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginBottom: '16px'
          }}>
            <h3 style={{ 
              margin: 0,
              color: 'var(--mac-text-primary)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
              <Activity style={{ width: '20px', height: '20px' }} />
              Сводка AI использования за {usageSummary.period_days} дней
            </h3>
            <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)' }}>
              Обновлено: {new Date(usageSummary.last_updated).toLocaleString()}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div style={{ 
              padding: '16px',
              backgroundColor: 'var(--mac-info-bg)',
              borderRadius: 'var(--mac-radius-md)',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '24px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-info)' }}>
                {usageSummary.total_requests}
              </div>
              <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>Всего запросов</div>
            </div>

            <div style={{ 
              padding: '16px',
              backgroundColor: 'var(--mac-success-bg)',
              borderRadius: 'var(--mac-radius-md)',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '24px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-success)' }}>
                {usageSummary.success_rate.toFixed(1)}%
              </div>
              <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>Успешность</div>
            </div>

            <div style={{ 
              padding: '16px',
              backgroundColor: 'var(--mac-accent-purple-bg)',
              borderRadius: 'var(--mac-radius-md)',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '24px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-accent-purple)' }}>
                {formatTime(usageSummary.average_response_time)}
              </div>
              <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>Среднее время</div>
            </div>

            <div style={{ 
              padding: '16px',
              backgroundColor: 'var(--mac-warning-bg)',
              borderRadius: 'var(--mac-radius-md)',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '24px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-warning)' }}>
                {formatCurrency(usageSummary.total_cost_usd)}
              </div>
              <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>Общие затраты</div>
            </div>

            <div style={{ 
              padding: '16px',
              backgroundColor: usageSummary.cost_trend === 'increasing' ? 'var(--mac-error-bg)' : 'var(--mac-success-bg)',
              borderRadius: 'var(--mac-radius-md)',
              textAlign: 'center'
            }}>
              <div style={{ 
                fontSize: '20px', 
                fontWeight: 'var(--mac-font-weight-bold)', 
                color: usageSummary.cost_trend === 'increasing' ? 'var(--mac-error)' : 'var(--mac-success)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '4px'
              }}>
                {usageSummary.cost_trend === 'increasing' ? <TrendingUp style={{ width: '20px', height: '20px' }} /> : <TrendingDown style={{ width: '20px', height: '20px' }} />}
                {usageSummary.cost_trend}
              </div>
              <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>Тренд затрат</div>
            </div>

            <div style={{ 
              padding: '16px',
              backgroundColor: 'var(--mac-accent-blue-bg)',
              borderRadius: 'var(--mac-radius-md)',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '20px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-accent-blue)' }}>
                {usageSummary.most_used_function || 'N/A'}
              </div>
              <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>Популярная функция</div>
            </div>
          </div>

          {usageSummary.recommendations && usageSummary.recommendations.length > 0 && (
            <div style={{ marginTop: '16px' }}>
              <h4 style={{ 
                margin: `0 0 8px 0`,
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                fontWeight: 'var(--mac-font-weight-semibold)'
              }}>
                Рекомендации
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {usageSummary.recommendations.map((recommendation, index) => (
                  <div
                    key={index}
                    style={{
                      padding: '8px',
                      backgroundColor: 'var(--mac-info-bg)',
                      border: '1px solid var(--mac-info-border)',
                      borderRadius: 'var(--mac-radius-sm)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                  >
                    <CheckCircle style={{ width: '16px', height: '16px', color: 'var(--mac-info)' }} />
                    <span style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-primary)' }}>
                      {recommendation}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </MacOSCard>
      )}

      {/* Быстрые действия */}
      <MacOSCard style={{ padding: '24px' }}>
        <h3 style={{ 
          margin: `0 0 16px 0`,
          color: 'var(--mac-text-primary)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>
          <Settings style={{ width: '20px', height: '20px' }} />
          Быстрые действия
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
          <MacOSButton 
            onClick={optimizeModels}
            disabled={loading}
            variant="primary"
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              padding: '12px'
            }}
          >
            {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Target style={{ width: '16px', height: '16px' }} />}
            Оптимизировать модели
          </MacOSButton>

          <MacOSButton 
            onClick={() => generateTrainingDataset('diagnostic_patterns')}
            disabled={loading}
            variant="success"
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              padding: '12px'
            }}
          >
            {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Database style={{ width: '16px', height: '16px' }} />}
            Генерировать датасет диагностики
          </MacOSButton>

          <MacOSButton 
            onClick={() => generateTrainingDataset('treatment_outcomes')}
            disabled={loading}
            variant="secondary"
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              padding: '12px'
            }}
          >
            {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Database style={{ width: '16px', height: '16px' }} />}
            Генерировать датасет лечения
          </MacOSButton>

          <MacOSButton 
            onClick={loadModelComparison}
            disabled={loading}
            variant="warning"
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              padding: '12px'
            }}
          >
            {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <BarChart3 style={{ width: '16px', height: '16px' }} />}
            Сравнить модели
          </MacOSButton>
        </div>
      </MacOSCard>
    </div>
  );

  const renderUsageTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {usageAnalytics && (
        <>
          {/* Общая статистика */}
          <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{ 
              margin: `0 0 16px 0`,
              color: 'var(--mac-text-primary)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
              <BarChart3 style={{ width: '20px', height: '20px' }} />
              Статистика использования ({usageAnalytics.period.start_date} - {usageAnalytics.period.end_date})
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-info)' }}>
                  {usageAnalytics.usage_statistics.total_requests}
                </div>
                <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>Всего запросов</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-success)' }}>
                  {usageAnalytics.usage_statistics.success_rate?.toFixed(1)}%
                </div>
                <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>Успешность</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-accent-purple)' }}>
                  {formatTime(usageAnalytics.usage_statistics.average_execution_time)}
                </div>
                <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>Среднее время</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-warning)' }}>
                  {usageAnalytics.usage_statistics.total_tokens_used}
                </div>
                <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>Токенов</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-error)' }}>
                  {formatCurrency(usageAnalytics.usage_statistics.total_cost_usd)}
                </div>
                <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>Затраты</div>
              </div>
            </div>
          </MacOSCard>

          {/* Разбивка по функциям */}
          {Object.keys(usageAnalytics.function_breakdown).length > 0 && (
            <MacOSCard style={{ padding: '24px' }}>
              <h3 style={{ 
                margin: `0 0 16px 0`,
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-semibold)'
              }}>
                По AI функциям
              </h3>
              <div style={{ display: 'grid', gap: '16px' }}>
                {Object.entries(usageAnalytics.function_breakdown).map(([func, stats]) => (
                  <div
                    key={func}
                    style={{
                      padding: '16px',
                      border: '1px solid var(--mac-border)',
                      borderRadius: 'var(--mac-radius-md)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      backgroundColor: 'var(--mac-bg-secondary)'
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                        {func}
                      </div>
                      <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                        {stats.requests} запросов • {stats.success_rate?.toFixed(1)}% успешность
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '16px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-info)' }}>
                        {formatTime(stats.average_time)}
                      </div>
                      <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)' }}>
                        {formatCurrency(stats.total_cost)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </MacOSCard>
          )}

          {/* Рекомендации */}
          {usageAnalytics.recommendations && usageAnalytics.recommendations.length > 0 && (
            <MacOSCard style={{ padding: '24px' }}>
              <h3 style={{ 
                margin: `0 0 16px 0`,
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-semibold)'
              }}>
                Рекомендации по оптимизации
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {usageAnalytics.recommendations.map((recommendation, index) => (
                  <div
                    key={index}
                    style={{
                      padding: '16px',
                      backgroundColor: 'var(--mac-warning-bg)',
                      border: '1px solid var(--mac-warning-border)',
                      borderRadius: 'var(--mac-radius-sm)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                  >
                    <AlertTriangle style={{ width: '16px', height: '16px', color: 'var(--mac-warning)' }} />
                    <span style={{ color: 'var(--mac-text-primary)' }}>
                      {recommendation}
                    </span>
                  </div>
                ))}
              </div>
            </MacOSCard>
          )}
        </>
      )}
    </div>
  );

  const renderLearningTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ 
          margin: 0, 
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>
          Инсайты для обучения AI
        </h3>
        <MacOSButton 
          onClick={loadLearningInsights}
          disabled={loading}
          variant="outline"
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px'
          }}
        >
          {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Brain style={{ width: '16px', height: '16px' }} />}
          Обновить
        </MacOSButton>
      </div>

      {learningInsights && (
        <>
          {/* Медицинские паттерны */}
          {learningInsights.medical_patterns && (
            <MacOSCard style={{ padding: '24px' }}>
              <h4 style={{ 
                margin: `0 0 16px 0`,
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                fontWeight: 'var(--mac-font-weight-semibold)'
              }}>
                Медицинские паттерны
              </h4>
              
              {learningInsights.medical_patterns.common_symptoms && Array.isArray(learningInsights.medical_patterns.common_symptoms) && (
                <div style={{ marginBottom: '16px' }}>
                  <h5 style={{ 
                    margin: `0 0 8px 0`, 
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)'
                  }}>
                    Частые симптомы
                  </h5>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {learningInsights.medical_patterns.common_symptoms.map((symptom, index) => (
                      <MacOSBadge
                        key={index}
                        variant="secondary"
                        style={{
                          fontSize: 'var(--mac-font-size-xs)'
                        }}
                      >
                        {symptom}
                      </MacOSBadge>
                    ))}
                  </div>
                </div>
              )}

              {learningInsights.medical_patterns.diagnosis_frequency && (
                <div>
                  <h5 style={{ 
                    margin: `0 0 8px 0`, 
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)'
                  }}>
                    Топ диагнозы
                  </h5>
                  <div style={{ display: 'grid', gap: '4px' }}>
                    {learningInsights.medical_patterns.diagnosis_frequency.top_diagnoses?.map((item, index) => (
                      <div
                        key={index}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          padding: '8px',
                          backgroundColor: 'var(--mac-bg-secondary)',
                          borderRadius: 'var(--mac-radius-sm)'
                        }}
                      >
                        <span style={{ color: 'var(--mac-text-primary)' }}>{item.diagnosis}</span>
                        <span style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                          {item.count} ({item.percentage}%)
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </MacOSCard>
          )}

          {/* Точность диагностики */}
          {learningInsights.diagnostic_accuracy && (
            <MacOSCard style={{ padding: '24px' }}>
              <h4 style={{ 
                margin: `0 0 16px 0`,
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                fontWeight: 'var(--mac-font-weight-semibold)'
              }}>
                Точность диагностики
              </h4>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px' }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-info)' }}>
                    {learningInsights.diagnostic_accuracy.ai_vs_doctor_accuracy?.ai_accuracy}%
                  </div>
                  <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>AI точность</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-success)' }}>
                    {learningInsights.diagnostic_accuracy.ai_vs_doctor_accuracy?.doctor_accuracy}%
                  </div>
                  <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>Врач точность</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-accent-purple)' }}>
                    {learningInsights.diagnostic_accuracy.ai_vs_doctor_accuracy?.agreement_rate}%
                  </div>
                  <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>Согласованность</div>
                </div>
              </div>
            </MacOSCard>
          )}

          {/* Рекомендации для обучения */}
          {learningInsights.learning_recommendations && (
            <MacOSCard style={{ padding: '24px' }}>
              <h4 style={{ 
                margin: `0 0 16px 0`,
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                fontWeight: 'var(--mac-font-weight-semibold)'
              }}>
                Рекомендации для обучения
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {learningInsights.learning_recommendations.map((recommendation, index) => (
                  <div
                    key={index}
                    style={{
                      padding: '16px',
                      backgroundColor: 'var(--mac-success-bg)',
                      border: '1px solid var(--mac-success-border)',
                      borderRadius: 'var(--mac-radius-sm)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                  >
                    <CheckCircle style={{ width: '16px', height: '16px', color: 'var(--mac-success)' }} />
                    <span style={{ color: 'var(--mac-text-primary)' }}>
                      {recommendation}
                    </span>
                  </div>
                ))}
              </div>
            </MacOSCard>
          )}
        </>
      )}
    </div>
  );

  const renderCostTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ 
          margin: 0, 
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>
          Анализ затрат на AI
        </h3>
        <MacOSButton 
          onClick={loadCostAnalysis}
          disabled={loading}
          variant="outline"
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px'
          }}
        >
          {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <DollarSign style={{ width: '16px', height: '16px' }} />}
          Загрузить
        </MacOSButton>
      </div>

      {costAnalysis && (
        <>
          {/* Сводка затрат */}
          <MacOSCard style={{ padding: '24px' }}>
            <h4 style={{ 
              margin: `0 0 16px 0`,
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
              Сводка затрат
            </h4>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '20px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-success)' }}>
                  {formatCurrency(costAnalysis.summary?.total_cost_usd || 0)}
                </div>
                <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>Общие затраты</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '20px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-info)' }}>
                  {formatCurrency(costAnalysis.summary?.average_daily_cost || 0)}
                </div>
                <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>В день</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '20px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-accent-purple)' }}>
                  {formatCurrency(costAnalysis.forecasts?.monthly_usd || 0)}
                </div>
                <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)' }}>Прогноз на месяц</div>
              </div>
            </div>
          </MacOSCard>

          {/* Затраты по функциям */}
          {costAnalysis.function_costs && Object.keys(costAnalysis.function_costs).length > 0 && (
            <MacOSCard style={{ padding: '24px' }}>
              <h4 style={{ 
                margin: `0 0 16px 0`,
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                fontWeight: 'var(--mac-font-weight-semibold)'
              }}>
                Затраты по функциям
              </h4>
              <div style={{ display: 'grid', gap: '16px' }}>
                {Object.entries(costAnalysis.function_costs).map(([func, data]) => (
                  <div
                    key={func}
                    style={{
                      padding: '16px',
                      border: '1px solid var(--mac-border)',
                      borderRadius: 'var(--mac-radius-md)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      backgroundColor: 'var(--mac-bg-secondary)'
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                        {func}
                      </div>
                      <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                        {data.requests} запросов • {data.cost_percentage?.toFixed(1)}% от общих затрат
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '16px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-warning)' }}>
                        {formatCurrency(data.total_cost)}
                      </div>
                      <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)' }}>
                        {formatCurrency(data.average_cost_per_request)} за запрос
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </MacOSCard>
          )}

          {/* Рекомендации по оптимизации затрат */}
          {costAnalysis.cost_optimization?.recommendations && (
            <MacOSCard style={{ padding: '24px' }}>
              <h4 style={{ 
                margin: `0 0 16px 0`,
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                fontWeight: 'var(--mac-font-weight-semibold)'
              }}>
                Оптимизация затрат
              </h4>
              
              <div style={{ 
                padding: '16px',
                backgroundColor: 'var(--mac-success-bg)',
                borderRadius: 'var(--mac-radius-sm)',
                marginBottom: '16px'
              }}>
                <div style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-success)' }}>
                  Потенциальная экономия: {formatCurrency(costAnalysis.cost_optimization.potential_savings?.amount_usd || 0)}
                </div>
                <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                  ({costAnalysis.cost_optimization.potential_savings?.percentage || 0}% от текущих затрат)
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {costAnalysis.cost_optimization.recommendations.map((recommendation, index) => (
                  <div
                    key={index}
                    style={{
                      padding: '8px',
                      backgroundColor: 'var(--mac-info-bg)',
                      border: '1px solid var(--mac-info-border)',
                      borderRadius: 'var(--mac-radius-sm)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                  >
                    <DollarSign style={{ width: '16px', height: '16px', color: 'var(--mac-info)' }} />
                    <span style={{ color: 'var(--mac-text-primary)' }}>
                      {recommendation}
                    </span>
                  </div>
                ))}
              </div>
            </MacOSCard>
          )}
        </>
      )}
    </div>
  );

  const renderModelsTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ 
          margin: 0, 
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>
          Сравнение AI моделей
        </h3>
        <MacOSButton 
          onClick={loadModelComparison}
          disabled={loading}
          variant="outline"
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px'
          }}
        >
          {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Cpu style={{ width: '16px', height: '16px' }} />}
          Загрузить
        </MacOSButton>
      </div>

      {modelComparison && (
        <>
          {/* Сравнительная таблица */}
          <MacOSCard style={{ padding: '24px' }}>
            <h4 style={{ 
              margin: `0 0 16px 0`,
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
              Сравнение моделей для функции: {modelComparison.function}
            </h4>
            
            <MacOSTable
              columns={[
                { key: 'model', label: 'Модель', width: '20%' },
                { key: 'accuracy', label: 'Точность', width: '15%', align: 'center' },
                { key: 'speed', label: 'Скорость (с)', width: '15%', align: 'center' },
                { key: 'cost', label: 'Стоимость', width: '15%', align: 'center' },
                { key: 'satisfaction', label: 'Удовлетворенность', width: '15%', align: 'center' },
                { key: 'reliability', label: 'Надежность', width: '20%', align: 'center' }
              ]}
              data={Object.entries(modelComparison.models).map(([model, data]) => ({
                model: <span style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>{model}</span>,
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
                  description="Загрузите данные для сравнения AI моделей"
                />
              }
            />
          </MacOSCard>

          {/* Рекомендации */}
          <MacOSCard style={{ padding: '24px' }}>
            <h4 style={{ 
              margin: `0 0 16px 0`,
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
              Рекомендации
            </h4>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '16px' }}>
              {Object.entries(modelComparison.recommendations).map(([category, model]) => (
                <div
                  key={category}
                  style={{
                    padding: '16px',
                    backgroundColor: 'var(--mac-info-bg)',
                    borderRadius: 'var(--mac-radius-sm)',
                    textAlign: 'center'
                  }}
                >
                  <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)', marginBottom: '4px' }}>
                    {category.replace('best_for_', '').replace('_', ' ')}
                  </div>
                  <div style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-info)' }}>
                    {model}
                  </div>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {modelComparison.optimization_suggestions?.map((suggestion, index) => (
                <div
                  key={index}
                  style={{
                    padding: '8px',
                    backgroundColor: 'var(--mac-success-bg)',
                    border: '1px solid var(--mac-success-border)',
                    borderRadius: 'var(--mac-radius-sm)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}
                >
                  <Target style={{ width: '16px', height: '16px', color: 'var(--mac-success)' }} />
                  <span style={{ color: 'var(--mac-text-primary)' }}>
                    {suggestion}
                  </span>
                </div>
              ))}
            </div>
          </MacOSCard>
        </>
      )}
    </div>
  );


  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Заголовок */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '16px'
      }}>
        <Brain style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
        <div>
          <h1 style={{ 
          margin: 0, 
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-2xl)',
            fontWeight: 'var(--mac-font-weight-bold)'
        }}>
          Расширенная аналитика AI
          </h1>
          <p style={{ 
            margin: '4px 0 0 0',
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-base)'
          }}>
            Мониторинг и оптимизация использования искусственного интеллекта
          </p>
        </div>
      </div>

      {/* Фильтры */}
      <MacOSCard style={{ padding: '16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)',
              marginBottom: '4px'
            }}>
              Начальная дата
            </label>
            <MacOSInput
              type="date"
              value={dateRange.startDate}
              onChange={(e) => setDateRange({...dateRange, startDate: e.target.value})}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)',
              marginBottom: '4px'
            }}>
              Конечная дата
            </label>
            <MacOSInput
              type="date"
              value={dateRange.endDate}
              onChange={(e) => setDateRange({...dateRange, endDate: e.target.value})}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)',
              marginBottom: '4px'
            }}>
              AI функция
            </label>
            <MacOSSelect
              value={filters.aiFunction}
              onChange={(e) => setFilters({...filters, aiFunction: e.target.value})}
              options={[
                { value: '', label: 'Все функции' },
                { value: 'diagnose_symptoms', label: 'Диагностика симптомов' },
                { value: 'analyze_medical_image', label: 'Анализ изображений' },
                { value: 'generate_treatment_plan', label: 'Планы лечения' },
                { value: 'check_drug_interactions', label: 'Взаимодействия препаратов' },
                { value: 'assess_patient_risk', label: 'Оценка рисков' }
              ]}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'end' }}>
            <MacOSButton 
              onClick={loadUsageAnalytics}
              disabled={loading}
              variant="primary"
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                width: '100%'
              }}
            >
              {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Filter style={{ width: '16px', height: '16px' }} />}
              Применить
            </MacOSButton>
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
          { id: 'models', label: 'Модели', icon: Cpu }
        ]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        size="md"
        variant="default"
      />

      {/* Содержимое вкладок */}
      {activeTab === 'overview' && renderOverviewTab()}
      {activeTab === 'usage' && renderUsageTab()}
      {activeTab === 'learning' && renderLearningTab()}
      {activeTab === 'cost' && renderCostTab()}
      {activeTab === 'models' && renderModelsTab()}
    </div>
  );
};

export default AIAnalytics;

