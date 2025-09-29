import React, { useState, useEffect } from 'react';
import { Card, Button, Badge, Input, Label, Select } from '../ui/native';
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
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';
import api from '../../utils/api';

const AIAnalytics = () => {
  const { theme, getColor, getSpacing } = useTheme();
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
      case 'Отлично': return getColor('green', 600);
      case 'Хорошо': return getColor('blue', 600);
      case 'Удовлетворительно': return getColor('yellow', 600);
      case 'Требует улучшения': return getColor('orange', 600);
      default: return getColor('gray', 600);
    }
  };

  const renderOverviewTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('lg') }}>
      {/* Сводка */}
      {usageSummary && (
        <Card style={{ padding: getSpacing('lg') }}>
          <div style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            marginBottom: getSpacing('md')
          }}>
            <h3 style={{ 
              margin: 0,
              color: getColor('text', 900),
              display: 'flex',
              alignItems: 'center',
              gap: getSpacing('sm')
            }}>
              <Activity size={20} />
              Сводка AI использования за {usageSummary.period_days} дней
            </h3>
            <div style={{ fontSize: '12px', color: getColor('text', 500) }}>
              Обновлено: {new Date(usageSummary.last_updated).toLocaleString()}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: getSpacing('md') }}>
            <div style={{ 
              padding: getSpacing('md'),
              backgroundColor: getColor('blue', 50),
              borderRadius: '8px',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('blue', 600) }}>
                {usageSummary.total_requests}
              </div>
              <div style={{ color: getColor('text', 600) }}>Всего запросов</div>
            </div>

            <div style={{ 
              padding: getSpacing('md'),
              backgroundColor: getColor('green', 50),
              borderRadius: '8px',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('green', 600) }}>
                {usageSummary.success_rate.toFixed(1)}%
              </div>
              <div style={{ color: getColor('text', 600) }}>Успешность</div>
            </div>

            <div style={{ 
              padding: getSpacing('md'),
              backgroundColor: getColor('purple', 50),
              borderRadius: '8px',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('purple', 600) }}>
                {formatTime(usageSummary.average_response_time)}
              </div>
              <div style={{ color: getColor('text', 600) }}>Среднее время</div>
            </div>

            <div style={{ 
              padding: getSpacing('md'),
              backgroundColor: getColor('orange', 50),
              borderRadius: '8px',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('orange', 600) }}>
                {formatCurrency(usageSummary.total_cost_usd)}
              </div>
              <div style={{ color: getColor('text', 600) }}>Общие затраты</div>
            </div>

            <div style={{ 
              padding: getSpacing('md'),
              backgroundColor: usageSummary.cost_trend === 'increasing' ? getColor('red', 50) : getColor('green', 50),
              borderRadius: '8px',
              textAlign: 'center'
            }}>
              <div style={{ 
                fontSize: '20px', 
                fontWeight: 'bold', 
                color: usageSummary.cost_trend === 'increasing' ? getColor('red', 600) : getColor('green', 600),
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: getSpacing('xs')
              }}>
                {usageSummary.cost_trend === 'increasing' ? <TrendingUp size={20} /> : <TrendingDown size={20} />}
                {usageSummary.cost_trend}
              </div>
              <div style={{ color: getColor('text', 600) }}>Тренд затрат</div>
            </div>

            <div style={{ 
              padding: getSpacing('md'),
              backgroundColor: getColor('indigo', 50),
              borderRadius: '8px',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '20px', fontWeight: 'bold', color: getColor('indigo', 600) }}>
                {usageSummary.most_used_function || 'N/A'}
              </div>
              <div style={{ color: getColor('text', 600) }}>Популярная функция</div>
            </div>
          </div>

          {usageSummary.recommendations && usageSummary.recommendations.length > 0 && (
            <div style={{ marginTop: getSpacing('md') }}>
              <h4 style={{ 
                margin: `0 0 ${getSpacing('sm')} 0`,
                color: getColor('text', 900)
              }}>
                Рекомендации
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('xs') }}>
                {usageSummary.recommendations.map((recommendation, index) => (
                  <div
                    key={index}
                    style={{
                      padding: getSpacing('sm'),
                      backgroundColor: getColor('blue', 50),
                      border: `1px solid ${getColor('blue', 200)}`,
                      borderRadius: '6px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: getSpacing('sm')
                    }}
                  >
                    <CheckCircle size={16} color={getColor('blue', 600)} />
                    <span style={{ fontSize: '14px', color: getColor('text', 700) }}>
                      {recommendation}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Быстрые действия */}
      <Card style={{ padding: getSpacing('lg') }}>
        <h3 style={{ 
          margin: `0 0 ${getSpacing('md')} 0`,
          color: getColor('text', 900),
          display: 'flex',
          alignItems: 'center',
          gap: getSpacing('sm')
        }}>
          <Settings size={20} />
          Быстрые действия
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: getSpacing('md') }}>
          <Button 
            onClick={optimizeModels}
            disabled={loading}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: getSpacing('sm'),
              backgroundColor: getColor('primary', 600),
              color: 'white',
              padding: getSpacing('md')
            }}
          >
            {loading ? <RefreshCw size={16} className="animate-spin" /> : <Target size={16} />}
            Оптимизировать модели
          </Button>

          <Button 
            onClick={() => generateTrainingDataset('diagnostic_patterns')}
            disabled={loading}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: getSpacing('sm'),
              backgroundColor: getColor('green', 600),
              color: 'white',
              padding: getSpacing('md')
            }}
          >
            {loading ? <RefreshCw size={16} className="animate-spin" /> : <Database size={16} />}
            Генерировать датасет диагностики
          </Button>

          <Button 
            onClick={() => generateTrainingDataset('treatment_outcomes')}
            disabled={loading}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: getSpacing('sm'),
              backgroundColor: getColor('purple', 600),
              color: 'white',
              padding: getSpacing('md')
            }}
          >
            {loading ? <RefreshCw size={16} className="animate-spin" /> : <Database size={16} />}
            Генерировать датасет лечения
          </Button>

          <Button 
            onClick={loadModelComparison}
            disabled={loading}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: getSpacing('sm'),
              backgroundColor: getColor('orange', 600),
              color: 'white',
              padding: getSpacing('md')
            }}
          >
            {loading ? <RefreshCw size={16} className="animate-spin" /> : <BarChart3 size={16} />}
            Сравнить модели
          </Button>
        </div>
      </Card>
    </div>
  );

  const renderUsageTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('lg') }}>
      {usageAnalytics && (
        <>
          {/* Общая статистика */}
          <Card style={{ padding: getSpacing('lg') }}>
            <h3 style={{ 
              margin: `0 0 ${getSpacing('md')} 0`,
              color: getColor('text', 900),
              display: 'flex',
              alignItems: 'center',
              gap: getSpacing('sm')
            }}>
              <BarChart3 size={20} />
              Статистика использования ({usageAnalytics.period.start_date} - {usageAnalytics.period.end_date})
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: getSpacing('md') }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: getColor('blue', 600) }}>
                  {usageAnalytics.usage_statistics.total_requests}
                </div>
                <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Всего запросов</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: getColor('green', 600) }}>
                  {usageAnalytics.usage_statistics.success_rate?.toFixed(1)}%
                </div>
                <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Успешность</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: getColor('purple', 600) }}>
                  {formatTime(usageAnalytics.usage_statistics.average_execution_time)}
                </div>
                <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Среднее время</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: getColor('orange', 600) }}>
                  {usageAnalytics.usage_statistics.total_tokens_used}
                </div>
                <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Токенов</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: getColor('red', 600) }}>
                  {formatCurrency(usageAnalytics.usage_statistics.total_cost_usd)}
                </div>
                <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Затраты</div>
              </div>
            </div>
          </Card>

          {/* Разбивка по функциям */}
          {Object.keys(usageAnalytics.function_breakdown).length > 0 && (
            <Card style={{ padding: getSpacing('lg') }}>
              <h3 style={{ 
                margin: `0 0 ${getSpacing('md')} 0`,
                color: getColor('text', 900)
              }}>
                По AI функциям
              </h3>
              <div style={{ display: 'grid', gap: getSpacing('md') }}>
                {Object.entries(usageAnalytics.function_breakdown).map(([func, stats]) => (
                  <div
                    key={func}
                    style={{
                      padding: getSpacing('md'),
                      border: `1px solid ${getColor('gray', 200)}`,
                      borderRadius: '8px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 'bold', color: getColor('text', 900) }}>
                        {func}
                      </div>
                      <div style={{ fontSize: '14px', color: getColor('text', 600) }}>
                        {stats.requests} запросов • {stats.success_rate?.toFixed(1)}% успешность
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '16px', fontWeight: 'bold', color: getColor('blue', 600) }}>
                        {formatTime(stats.average_time)}
                      </div>
                      <div style={{ fontSize: '12px', color: getColor('text', 500) }}>
                        {formatCurrency(stats.total_cost)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Рекомендации */}
          {usageAnalytics.recommendations && usageAnalytics.recommendations.length > 0 && (
            <Card style={{ padding: getSpacing('lg') }}>
              <h3 style={{ 
                margin: `0 0 ${getSpacing('md')} 0`,
                color: getColor('text', 900)
              }}>
                Рекомендации по оптимизации
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('sm') }}>
                {usageAnalytics.recommendations.map((recommendation, index) => (
                  <div
                    key={index}
                    style={{
                      padding: getSpacing('md'),
                      backgroundColor: getColor('yellow', 50),
                      border: `1px solid ${getColor('yellow', 200)}`,
                      borderRadius: '6px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: getSpacing('sm')
                    }}
                  >
                    <AlertTriangle size={16} color={getColor('yellow', 600)} />
                    <span style={{ color: getColor('text', 700) }}>
                      {recommendation}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );

  const renderLearningTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('lg') }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, color: getColor('text', 900) }}>
          Инсайты для обучения AI
        </h3>
        <Button 
          onClick={loadLearningInsights}
          disabled={loading}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: getSpacing('sm')
          }}
        >
          {loading ? <RefreshCw size={16} className="animate-spin" /> : <Brain size={16} />}
          Обновить
        </Button>
      </div>

      {learningInsights && (
        <>
          {/* Медицинские паттерны */}
          {learningInsights.medical_patterns && (
            <Card style={{ padding: getSpacing('lg') }}>
              <h4 style={{ 
                margin: `0 0 ${getSpacing('md')} 0`,
                color: getColor('text', 900)
              }}>
                Медицинские паттерны
              </h4>
              
              {learningInsights.medical_patterns.common_symptoms && (
                <div style={{ marginBottom: getSpacing('md') }}>
                  <h5 style={{ margin: `0 0 ${getSpacing('sm')} 0`, color: getColor('text', 800) }}>
                    Частые симптомы
                  </h5>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: getSpacing('xs') }}>
                    {learningInsights.medical_patterns.common_symptoms.map((symptom, index) => (
                      <Badge
                        key={index}
                        style={{
                          backgroundColor: getColor('blue', 100),
                          color: getColor('blue', 800),
                          padding: `${getSpacing('xs')} ${getSpacing('sm')}`
                        }}
                      >
                        {symptom}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {learningInsights.medical_patterns.diagnosis_frequency && (
                <div>
                  <h5 style={{ margin: `0 0 ${getSpacing('sm')} 0`, color: getColor('text', 800) }}>
                    Топ диагнозы
                  </h5>
                  <div style={{ display: 'grid', gap: getSpacing('xs') }}>
                    {learningInsights.medical_patterns.diagnosis_frequency.top_diagnoses?.map((item, index) => (
                      <div
                        key={index}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          padding: getSpacing('sm'),
                          backgroundColor: getColor('gray', 50),
                          borderRadius: '4px'
                        }}
                      >
                        <span>{item.diagnosis}</span>
                        <span style={{ fontWeight: 'bold' }}>
                          {item.count} ({item.percentage}%)
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          )}

          {/* Точность диагностики */}
          {learningInsights.diagnostic_accuracy && (
            <Card style={{ padding: getSpacing('lg') }}>
              <h4 style={{ 
                margin: `0 0 ${getSpacing('md')} 0`,
                color: getColor('text', 900)
              }}>
                Точность диагностики
              </h4>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: getSpacing('md') }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('blue', 600) }}>
                    {learningInsights.diagnostic_accuracy.ai_vs_doctor_accuracy?.ai_accuracy}%
                  </div>
                  <div style={{ fontSize: '12px', color: getColor('text', 600) }}>AI точность</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('green', 600) }}>
                    {learningInsights.diagnostic_accuracy.ai_vs_doctor_accuracy?.doctor_accuracy}%
                  </div>
                  <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Врач точность</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('purple', 600) }}>
                    {learningInsights.diagnostic_accuracy.ai_vs_doctor_accuracy?.agreement_rate}%
                  </div>
                  <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Согласованность</div>
                </div>
              </div>
            </Card>
          )}

          {/* Рекомендации для обучения */}
          {learningInsights.learning_recommendations && (
            <Card style={{ padding: getSpacing('lg') }}>
              <h4 style={{ 
                margin: `0 0 ${getSpacing('md')} 0`,
                color: getColor('text', 900)
              }}>
                Рекомендации для обучения
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('sm') }}>
                {learningInsights.learning_recommendations.map((recommendation, index) => (
                  <div
                    key={index}
                    style={{
                      padding: getSpacing('md'),
                      backgroundColor: getColor('green', 50),
                      border: `1px solid ${getColor('green', 200)}`,
                      borderRadius: '6px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: getSpacing('sm')
                    }}
                  >
                    <CheckCircle size={16} color={getColor('green', 600)} />
                    <span style={{ color: getColor('text', 700) }}>
                      {recommendation}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );

  const renderCostTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('lg') }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, color: getColor('text', 900) }}>
          Анализ затрат на AI
        </h3>
        <Button 
          onClick={loadCostAnalysis}
          disabled={loading}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: getSpacing('sm')
          }}
        >
          {loading ? <RefreshCw size={16} className="animate-spin" /> : <DollarSign size={16} />}
          Загрузить
        </Button>
      </div>

      {costAnalysis && (
        <>
          {/* Сводка затрат */}
          <Card style={{ padding: getSpacing('lg') }}>
            <h4 style={{ 
              margin: `0 0 ${getSpacing('md')} 0`,
              color: getColor('text', 900)
            }}>
              Сводка затрат
            </h4>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: getSpacing('md') }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '20px', fontWeight: 'bold', color: getColor('green', 600) }}>
                  {formatCurrency(costAnalysis.summary?.total_cost_usd || 0)}
                </div>
                <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Общие затраты</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '20px', fontWeight: 'bold', color: getColor('blue', 600) }}>
                  {formatCurrency(costAnalysis.summary?.average_daily_cost || 0)}
                </div>
                <div style={{ fontSize: '12px', color: getColor('text', 600) }}>В день</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '20px', fontWeight: 'bold', color: getColor('purple', 600) }}>
                  {formatCurrency(costAnalysis.forecasts?.monthly_usd || 0)}
                </div>
                <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Прогноз на месяц</div>
              </div>
            </div>
          </Card>

          {/* Затраты по функциям */}
          {costAnalysis.function_costs && Object.keys(costAnalysis.function_costs).length > 0 && (
            <Card style={{ padding: getSpacing('lg') }}>
              <h4 style={{ 
                margin: `0 0 ${getSpacing('md')} 0`,
                color: getColor('text', 900)
              }}>
                Затраты по функциям
              </h4>
              <div style={{ display: 'grid', gap: getSpacing('md') }}>
                {Object.entries(costAnalysis.function_costs).map(([func, data]) => (
                  <div
                    key={func}
                    style={{
                      padding: getSpacing('md'),
                      border: `1px solid ${getColor('gray', 200)}`,
                      borderRadius: '8px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 'bold', color: getColor('text', 900) }}>
                        {func}
                      </div>
                      <div style={{ fontSize: '14px', color: getColor('text', 600) }}>
                        {data.requests} запросов • {data.cost_percentage?.toFixed(1)}% от общих затрат
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '16px', fontWeight: 'bold', color: getColor('orange', 600) }}>
                        {formatCurrency(data.total_cost)}
                      </div>
                      <div style={{ fontSize: '12px', color: getColor('text', 500) }}>
                        {formatCurrency(data.average_cost_per_request)} за запрос
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Рекомендации по оптимизации затрат */}
          {costAnalysis.cost_optimization?.recommendations && (
            <Card style={{ padding: getSpacing('lg') }}>
              <h4 style={{ 
                margin: `0 0 ${getSpacing('md')} 0`,
                color: getColor('text', 900)
              }}>
                Оптимизация затрат
              </h4>
              
              <div style={{ 
                padding: getSpacing('md'),
                backgroundColor: getColor('green', 50),
                borderRadius: '6px',
                marginBottom: getSpacing('md')
              }}>
                <div style={{ fontWeight: 'bold', color: getColor('green', 800) }}>
                  Потенциальная экономия: {formatCurrency(costAnalysis.cost_optimization.potential_savings?.amount_usd || 0)}
                </div>
                <div style={{ fontSize: '14px', color: getColor('text', 600) }}>
                  ({costAnalysis.cost_optimization.potential_savings?.percentage || 0}% от текущих затрат)
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('sm') }}>
                {costAnalysis.cost_optimization.recommendations.map((recommendation, index) => (
                  <div
                    key={index}
                    style={{
                      padding: getSpacing('sm'),
                      backgroundColor: getColor('blue', 50),
                      border: `1px solid ${getColor('blue', 200)}`,
                      borderRadius: '6px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: getSpacing('sm')
                    }}
                  >
                    <DollarSign size={16} color={getColor('blue', 600)} />
                    <span style={{ color: getColor('text', 700) }}>
                      {recommendation}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );

  const renderModelsTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('lg') }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, color: getColor('text', 900) }}>
          Сравнение AI моделей
        </h3>
        <Button 
          onClick={loadModelComparison}
          disabled={loading}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: getSpacing('sm')
          }}
        >
          {loading ? <RefreshCw size={16} className="animate-spin" /> : <Cpu size={16} />}
          Загрузить
        </Button>
      </div>

      {modelComparison && (
        <>
          {/* Сравнительная таблица */}
          <Card style={{ padding: getSpacing('lg') }}>
            <h4 style={{ 
              margin: `0 0 ${getSpacing('md')} 0`,
              color: getColor('text', 900)
            }}>
              Сравнение моделей для функции: {modelComparison.function}
            </h4>
            
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ backgroundColor: getColor('gray', 50) }}>
                    <th style={{ padding: getSpacing('sm'), textAlign: 'left', border: `1px solid ${getColor('gray', 200)}` }}>
                      Модель
                    </th>
                    <th style={{ padding: getSpacing('sm'), textAlign: 'center', border: `1px solid ${getColor('gray', 200)}` }}>
                      Точность
                    </th>
                    <th style={{ padding: getSpacing('sm'), textAlign: 'center', border: `1px solid ${getColor('gray', 200)}` }}>
                      Скорость (с)
                    </th>
                    <th style={{ padding: getSpacing('sm'), textAlign: 'center', border: `1px solid ${getColor('gray', 200)}` }}>
                      Стоимость
                    </th>
                    <th style={{ padding: getSpacing('sm'), textAlign: 'center', border: `1px solid ${getColor('gray', 200)}` }}>
                      Удовлетворенность
                    </th>
                    <th style={{ padding: getSpacing('sm'), textAlign: 'center', border: `1px solid ${getColor('gray', 200)}` }}>
                      Надежность
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(modelComparison.models).map(([model, data]) => (
                    <tr key={model}>
                      <td style={{ padding: getSpacing('sm'), border: `1px solid ${getColor('gray', 200)}`, fontWeight: 'bold' }}>
                        {model}
                      </td>
                      <td style={{ padding: getSpacing('sm'), border: `1px solid ${getColor('gray', 200)}`, textAlign: 'center' }}>
                        {data.accuracy}%
                      </td>
                      <td style={{ padding: getSpacing('sm'), border: `1px solid ${getColor('gray', 200)}`, textAlign: 'center' }}>
                        {data.speed}
                      </td>
                      <td style={{ padding: getSpacing('sm'), border: `1px solid ${getColor('gray', 200)}`, textAlign: 'center' }}>
                        {formatCurrency(data.cost_per_request)}
                      </td>
                      <td style={{ padding: getSpacing('sm'), border: `1px solid ${getColor('gray', 200)}`, textAlign: 'center' }}>
                        {data.user_satisfaction}/5
                      </td>
                      <td style={{ padding: getSpacing('sm'), border: `1px solid ${getColor('gray', 200)}`, textAlign: 'center' }}>
                        {data.reliability}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Рекомендации */}
          <Card style={{ padding: getSpacing('lg') }}>
            <h4 style={{ 
              margin: `0 0 ${getSpacing('md')} 0`,
              color: getColor('text', 900)
            }}>
              Рекомендации
            </h4>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: getSpacing('md'), marginBottom: getSpacing('md') }}>
              {Object.entries(modelComparison.recommendations).map(([category, model]) => (
                <div
                  key={category}
                  style={{
                    padding: getSpacing('md'),
                    backgroundColor: getColor('blue', 50),
                    borderRadius: '6px',
                    textAlign: 'center'
                  }}
                >
                  <div style={{ fontSize: '14px', color: getColor('text', 600), marginBottom: getSpacing('xs') }}>
                    {category.replace('best_for_', '').replace('_', ' ')}
                  </div>
                  <div style={{ fontWeight: 'bold', color: getColor('blue', 700) }}>
                    {model}
                  </div>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('sm') }}>
              {modelComparison.optimization_suggestions?.map((suggestion, index) => (
                <div
                  key={index}
                  style={{
                    padding: getSpacing('sm'),
                    backgroundColor: getColor('green', 50),
                    border: `1px solid ${getColor('green', 200)}`,
                    borderRadius: '6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: getSpacing('sm')
                  }}
                >
                  <Target size={16} color={getColor('green', 600)} />
                  <span style={{ color: getColor('text', 700) }}>
                    {suggestion}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  );

  const tabs = [
    { id: 'overview', label: 'Обзор', icon: Activity },
    { id: 'usage', label: 'Использование', icon: BarChart3 },
    { id: 'learning', label: 'Обучение', icon: Brain },
    { id: 'cost', label: 'Затраты', icon: DollarSign },
    { id: 'models', label: 'Модели', icon: Cpu }
  ];

  return (
    <div style={{ padding: getSpacing('lg') }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: getSpacing('md'),
        marginBottom: getSpacing('lg')
      }}>
        <Brain size={24} color={getColor('primary', 600)} />
        <h2 style={{ 
          margin: 0, 
          color: getColor('text', 900),
          fontSize: '24px',
          fontWeight: 'bold'
        }}>
          Расширенная аналитика AI
        </h2>
      </div>

      {/* Фильтры */}
      <Card style={{ padding: getSpacing('md'), marginBottom: getSpacing('lg') }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: getSpacing('md') }}>
          <div>
            <Label>Начальная дата</Label>
            <Input
              type="date"
              value={dateRange.startDate}
              onChange={(e) => setDateRange({...dateRange, startDate: e.target.value})}
            />
          </div>
          <div>
            <Label>Конечная дата</Label>
            <Input
              type="date"
              value={dateRange.endDate}
              onChange={(e) => setDateRange({...dateRange, endDate: e.target.value})}
            />
          </div>
          <div>
            <Label>AI функция</Label>
            <Select
              value={filters.aiFunction}
              onChange={(e) => setFilters({...filters, aiFunction: e.target.value})}
            >
              <option value="">Все функции</option>
              <option value="diagnose_symptoms">Диагностика симптомов</option>
              <option value="analyze_medical_image">Анализ изображений</option>
              <option value="generate_treatment_plan">Планы лечения</option>
              <option value="check_drug_interactions">Взаимодействия препаратов</option>
              <option value="assess_patient_risk">Оценка рисков</option>
            </Select>
          </div>
          <div style={{ display: 'flex', alignItems: 'end' }}>
            <Button 
              onClick={loadUsageAnalytics}
              disabled={loading}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: getSpacing('sm'),
                backgroundColor: getColor('primary', 600),
                color: 'white'
              }}
            >
              {loading ? <RefreshCw size={16} className="animate-spin" /> : <Filter size={16} />}
              Применить
            </Button>
          </div>
        </div>
      </Card>

      {/* Вкладки */}
      <div style={{ 
        display: 'flex', 
        borderBottom: `1px solid ${getColor('gray', 200)}`,
        marginBottom: getSpacing('lg')
      }}>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: `${getSpacing('md')} ${getSpacing('lg')}`,
                border: 'none',
                background: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: getSpacing('sm'),
                borderBottom: activeTab === tab.id ? `2px solid ${getColor('primary', 600)}` : '2px solid transparent',
                color: activeTab === tab.id ? getColor('primary', 600) : getColor('text', 600),
                fontWeight: activeTab === tab.id ? 'bold' : 'normal'
              }}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

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

