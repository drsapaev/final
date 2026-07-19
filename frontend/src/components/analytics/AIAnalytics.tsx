import { useState, useEffect, useCallback } from 'react';
import type { CSSProperties } from 'react';
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
import { useTranslation } from '../../i18n/useTranslation';
const AIAnalytics = () => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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

      const response = await api.get(`/analytics/ai/usage-analytics?${params}`) as any;
      setUsageAnalytics(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки аналитики AI:', error);
      toast.error(t('misc.aia_error_load_usage'));
    } finally {
      setLoading(false);
    }
  }, [dateRange.endDate, dateRange.startDate, filters.aiFunction, filters.userId, t]);

  const loadLearningInsights = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        start_date: dateRange.startDate,
        end_date: dateRange.endDate
      });

      const response = await api.get(`/analytics/ai/learning-insights?${params}`) as any;
      setLearningInsights(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки инсайтов обучения:', error);
      toast.error(t('misc.aia_error_load_insights'));
    } finally {
      setLoading(false);
    }
  };

  const loadUsageSummary = useCallback(async () => {
    try {
      const response = await api.get('/analytics/ai/usage-summary?days=30') as any;
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

      const response = await api.get(`/analytics/ai/cost-analysis?${params}`) as any;
      setCostAnalysis(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки анализа затрат:', error);
      toast.error(t('misc.aia_error_load_cost'));
    } finally {
      setLoading(false);
    }
  };

  const loadModelComparison = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        function: 'diagnose_symptoms',
        days: '30'
      });

      const response = await api.get(`/analytics/ai/model-comparison?${params}`) as any;
      setModelComparison(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки сравнения моделей:', error);
      toast.error(t('misc.aia_error_load_comparison'));
    } finally {
      setLoading(false);
    }
  };

  const optimizeModels = async () => {
    setLoading(true);
    try {
      const response = await api.post('/analytics/ai/optimize-models') as any;
      toast.success(t('misc.aia_optimization_started'));
      logger.log('Результат оптимизации:', response.data);
    } catch (error) {
      logger.error('Ошибка оптимизации моделей:', error);
      toast.error(t('misc.aia_error_optimization'));
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
      }) as any;
      toast.success(t('misc.aia_dataset_generated', { dataType }));
      logger.log('Информация о датасете:', response.data);
    } catch (error) {
      logger.error('Ошибка генерации датасета:', error);
      toast.error(t('misc.aia_error_dataset'));
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
    return t('misc.aia_seconds_short', { seconds: seconds.toFixed(2) });
  };





  const renderOverviewTab = () =>
  <div className="ai-analytics-tab-content">
      {/* Сводка */}
      {usageSummary &&
    <MacOSCard className="ai-analytics-card-padded">
          <div className="ai-analytics-section-header">
            <h3 className="ai-analytics-h3">
              <Activity style={{ width: '20px', height: '20px' }} />
              {t('misc.aia_overview_summary_title', { days: usageSummary.period_days })}
            </h3>
            <div className="ai-analytics-timestamp">
              {t('misc.aia_updated')} {new Date(usageSummary.last_updated).toLocaleString()}
            </div>
          </div>

          <div className="ai-analytics-stat-grid">
            <div className="ai-analytics-stat-card ai-analytics-stat-card-info">
              <div className="ai-analytics-stat-value-3xl ai-analytics-stat-value-info">
                {usageSummary.total_requests}
              </div>
              <div className="ai-analytics-stat-label">{t('misc.aia_total_requests')}</div>
            </div>

            <div className="ai-analytics-stat-card ai-analytics-stat-card-success">
              <div className="ai-analytics-stat-value-3xl ai-analytics-stat-value-success">
                {usageSummary.success_rate.toFixed(1)}%
              </div>
              <div className="ai-analytics-stat-label">{t('misc.aia_success_rate')}</div>
            </div>

            <div className="ai-analytics-stat-card ai-analytics-stat-card-accent-purple">
              <div className="ai-analytics-stat-value-3xl ai-analytics-stat-value-accent-purple">
                {formatTime(usageSummary.average_response_time)}
              </div>
              <div className="ai-analytics-stat-label">{t('misc.aia_average_time')}</div>
            </div>

            <div className="ai-analytics-stat-card ai-analytics-stat-card-warning">
              <div className="ai-analytics-stat-value-3xl ai-analytics-stat-value-warning">
                {formatCurrency(usageSummary.total_cost_usd)}
              </div>
              <div className="ai-analytics-stat-label">{t('misc.aia_total_cost')}</div>
            </div>

            <div className={`ai-analytics-stat-card ${usageSummary.cost_trend === 'increasing' ? 'ai-analytics-stat-card-trend-increasing' : 'ai-analytics-stat-card-trend-decreasing'}`}>
              <div className={`ai-analytics-trend-value ${usageSummary.cost_trend === 'increasing' ? 'ai-analytics-trend-value-increasing' : 'ai-analytics-trend-value-decreasing'}`}>
                {usageSummary.cost_trend === 'increasing' ? <TrendingUp style={{ width: '20px', height: '20px' }} /> : <TrendingDown style={{ width: '20px', height: '20px' }} />}
                {usageSummary.cost_trend}
              </div>
              <div className="ai-analytics-stat-label">{t('misc.aia_cost_trend')}</div>
            </div>

            <div className="ai-analytics-stat-card ai-analytics-stat-card-accent-blue">
              <div className="ai-analytics-stat-value-2xl ai-analytics-stat-value-accent-blue">
                {usageSummary.most_used_function || 'N/A'}
              </div>
              <div className="ai-analytics-stat-label">{t('misc.aia_popular_function')}</div>
            </div>
          </div>

          {usageSummary.recommendations && usageSummary.recommendations.length > 0 &&
      <div className="ai-analytics-mt-4">
              <h4 className="ai-analytics-h4">
                {t('misc.aia_recommendations')}
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
          {t('misc.aia_quick_actions')}
        </h3>

        <div className="ai-analytics-stat-grid-250">
          <Button
          onClick={optimizeModels}
          disabled={loading}
          variant="primary"
          className="ai-analytics-action-btn">
            {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Target style={{ width: '16px', height: '16px' }} />}
            {t('misc.aia_optimize_models_btn')}
          </Button>

          <Button
          onClick={() => generateTrainingDataset('diagnostic_patterns')}
          disabled={loading}
          variant="success"
          className="ai-analytics-action-btn">
            {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Database style={{ width: '16px', height: '16px' }} />}
            {t('misc.aia_generate_diagnostic_dataset')}
          </Button>

          <Button
          onClick={() => generateTrainingDataset('treatment_outcomes')}
          disabled={loading}
          variant="secondary"
          className="ai-analytics-action-btn">
            {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Database style={{ width: '16px', height: '16px' }} />}
            {t('misc.aia_generate_treatment_dataset')}
          </Button>

          <Button
          onClick={loadModelComparison}
          disabled={loading}
          variant="warning"
          className="ai-analytics-action-btn">
            {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <BarChart3 style={{ width: '16px', height: '16px' }} />}
            {t('misc.aia_compare_models_btn')}
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
              {t('misc.aia_usage_stats_title', { start: usageAnalytics.period.start_date, end: usageAnalytics.period.end_date })}
            </h3>

            <div className="ai-analytics-stat-grid-sm">
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-xl ai-analytics-stat-value-info">
                  {usageAnalytics.usage_statistics.total_requests}
                </div>
                <div className="ai-analytics-stat-label-xs">{t('misc.aia_total_requests')}</div>
              </div>
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-xl ai-analytics-stat-value-success">
                  {usageAnalytics.usage_statistics.success_rate?.toFixed(1)}%
                </div>
                <div className="ai-analytics-stat-label-xs">{t('misc.aia_success_rate')}</div>
              </div>
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-xl ai-analytics-stat-value-accent-purple">
                  {formatTime(usageAnalytics.usage_statistics.average_execution_time)}
                </div>
                <div className="ai-analytics-stat-label-xs">{t('misc.aia_average_time')}</div>
              </div>
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-xl ai-analytics-stat-value-error">
                  {usageAnalytics.usage_statistics.total_tokens_used}
                </div>
                <div className="ai-analytics-stat-label-xs">{t('misc.aia_tokens')}</div>
              </div>
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-xl ai-analytics-stat-value-warning">
                  {formatCurrency(usageAnalytics.usage_statistics.total_cost_usd)}
                </div>
                <div className="ai-analytics-stat-label-xs">{t('misc.aia_costs')}</div>
              </div>
            </div>
          </MacOSCard>

          {/* Разбивка по функциям */}
          {Object.keys(usageAnalytics.function_breakdown).length > 0 &&
      <MacOSCard className="ai-analytics-card-padded">
              <h3 className="ai-analytics-h3-mb16">
                {t('misc.aia_by_ai_functions')}
              </h3>
              <div className="ai-analytics-grid-gap">
                {Object.entries(usageAnalytics.function_breakdown).map(([func, stats]: [string, any]) =>
          <div
            key={func}
            className="ai-analytics-function-card">
                    <div>
                      <div className="ai-analytics-function-name">
                        {func}
                      </div>
                      <div className="ai-analytics-function-stats">
                        {t('misc.aia_function_stats', { requests: stats.requests, success: stats.success_rate?.toFixed(1) })}
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
                {t('misc.aia_optimization_recommendations')}
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
          {t('misc.aia_learning_insights_title')}
        </h3>
        <Button
        onClick={loadLearningInsights}
        disabled={loading}
        variant="outline"
        className="ai-analytics-action-btn-sm">
          {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Brain style={{ width: '16px', height: '16px' }} />}
          {t('misc.aia_refresh')}
        </Button>
      </div>

      {learningInsights &&
    <>
          {/* Медицинские паттерны */}
          {learningInsights.medical_patterns &&
      <MacOSCard className="ai-analytics-card-padded">
              <h4 className="ai-analytics-h4">
                {t('misc.aia_medical_patterns')}
              </h4>

              {learningInsights.medical_patterns.common_symptoms && Array.isArray(learningInsights.medical_patterns.common_symptoms) &&
        <div className="ai-analytics-mb-4">
                  <h5 className="ai-analytics-h5">
                    {t('misc.aia_common_symptoms')}
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
                    {t('misc.aia_top_diagnoses')}
                  </h5>
                  <div className="ai-analytics-grid-gap-1">
                    {learningInsights.medical_patterns.diagnosis_frequency.top_diagnoses?.map((item, index) =>
            <div
              key={index}
              className="ai-analytics-diagnosis-row">
                        <span className="ai-analytics-diagnosis-name">{item.diagnosis}</span>
                        <span className="ai-analytics-diagnosis-count">
                          {t('misc.aia_diagnosis_count', { count: item.count, pct: item.percentage })}
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
                {t('misc.aia_diagnostic_accuracy')}
              </h4>

              <div className="ai-analytics-stat-grid-sm">
                <div className="ai-analytics-stat-text-center">
                  <div className="ai-analytics-stat-value-3xl ai-analytics-stat-value-info">
                    {learningInsights.diagnostic_accuracy.ai_vs_doctor_accuracy?.ai_accuracy}%
                  </div>
                  <div className="ai-analytics-stat-label-xs">{t('misc.aia_ai_accuracy')}</div>
                </div>
                <div className="ai-analytics-stat-text-center">
                  <div className="ai-analytics-stat-value-3xl ai-analytics-stat-value-success">
                    {learningInsights.diagnostic_accuracy.ai_vs_doctor_accuracy?.doctor_accuracy}%
                  </div>
                  <div className="ai-analytics-stat-label-xs">{t('misc.aia_doctor_accuracy')}</div>
                </div>
                <div className="ai-analytics-stat-text-center">
                  <div className="ai-analytics-stat-value-3xl ai-analytics-stat-value-accent-purple">
                    {learningInsights.diagnostic_accuracy.ai_vs_doctor_accuracy?.agreement_rate}%
                  </div>
                  <div className="ai-analytics-stat-label-xs">{t('misc.aia_agreement_rate')}</div>
                </div>
              </div>
            </MacOSCard>
      }

          {/* Рекомендации для обучения */}
          {learningInsights.learning_recommendations &&
      <MacOSCard className="ai-analytics-card-padded">
              <h4 className="ai-analytics-h4">
                {t('misc.aia_learning_recommendations')}
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
          {t('misc.aia_cost_analysis_title')}
        </h3>
        <Button
        onClick={loadCostAnalysis}
        disabled={loading}
        variant="outline"
        className="ai-analytics-action-btn-sm">
          {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <DollarSign style={{ width: '16px', height: '16px' }} />}
          {t('misc.aia_load')}
        </Button>
      </div>

      {costAnalysis &&
    <>
          {/* Сводка затрат */}
          <MacOSCard className="ai-analytics-card-padded">
            <h4 className="ai-analytics-h4">
              {t('misc.aia_cost_summary')}
            </h4>

            <div className="ai-analytics-stat-grid-sm">
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-2xl ai-analytics-stat-value-success">
                  {formatCurrency(costAnalysis.summary?.total_cost_usd || 0)}
                </div>
                <div className="ai-analytics-stat-label-xs">{t('misc.aia_total_cost')}</div>
              </div>
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-2xl ai-analytics-stat-value-info">
                  {formatCurrency(costAnalysis.summary?.average_daily_cost || 0)}
                </div>
                <div className="ai-analytics-stat-label-xs">{t('misc.aia_per_day')}</div>
              </div>
              <div className="ai-analytics-stat-text-center">
                <div className="ai-analytics-stat-value-2xl ai-analytics-stat-value-accent-purple">
                  {formatCurrency(costAnalysis.forecasts?.monthly_usd || 0)}
                </div>
                <div className="ai-analytics-stat-label-xs">{t('misc.aia_month_forecast')}</div>
              </div>
            </div>
          </MacOSCard>

          {/* Затраты по функциям */}
          {costAnalysis.function_costs && Object.keys(costAnalysis.function_costs).length > 0 &&
      <MacOSCard className="ai-analytics-card-padded">
              <h4 className="ai-analytics-h4">
                {t('misc.aia_cost_by_function')}
              </h4>
              <div className="ai-analytics-grid-gap">
                {Object.entries(costAnalysis.function_costs).map(([func, data]: [string, any]) =>
          <div
            key={func}
            className="ai-analytics-function-card">
                    <div>
                      <div className="ai-analytics-function-name">
                        {func}
                      </div>
                      <div className="ai-analytics-function-stats">
                        {t('misc.aia_function_cost_stats', { requests: data.requests, pct: data.cost_percentage?.toFixed(1) })}
                      </div>
                    </div>
                    <div className="ai-analytics-stat-text-right">
                      <div className="ai-analytics-stat-value-lg ai-analytics-stat-value-warning">
                        {formatCurrency(data.total_cost)}
                      </div>
                      <div className="ai-analytics-timestamp">
                        {t('misc.aia_per_request', { cost: formatCurrency(data.average_cost_per_request) })}
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
                {t('misc.aia_cost_optimization')}
              </h4>

              <div className="ai-analytics-cost-savings">
                <div className="ai-analytics-cost-savings-amount">
                  {t('misc.aia_potential_savings', { amount: formatCurrency(costAnalysis.cost_optimization.potential_savings?.amount_usd || 0) })}
                </div>
                <div className="ai-analytics-stat-label">
                  {t('misc.aia_potential_savings_pct', { pct: costAnalysis.cost_optimization.potential_savings?.percentage || 0 })}
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
          {t('misc.aia_model_comparison_title')}
        </h3>
        <Button
        onClick={loadModelComparison}
        disabled={loading}
        variant="outline"
        className="ai-analytics-action-btn-sm">
          {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Cpu style={{ width: '16px', height: '16px' }} />}
          {t('misc.aia_load')}
        </Button>
      </div>

      {modelComparison &&
    <>
          {/* Сравнительная таблица */}
          <MacOSCard className="ai-analytics-card-padded">
            <h4 className="ai-analytics-h4">
              {t('misc.aia_comparison_for_function', { func: modelComparison.function })}
            </h4>
            
            <Table
          columns={[
          { key: 'model', label: t('misc.aia_col_model'), width: '20%' },
          { key: 'accuracy', label: t('misc.aia_col_accuracy'), width: '15%', align: 'center' },
          { key: 'speed', label: t('misc.aia_col_speed_seconds'), width: '15%', align: 'center' },
          { key: 'cost', label: t('misc.aia_col_cost'), width: '15%', align: 'center' },
          { key: 'satisfaction', label: t('misc.aia_col_satisfaction'), width: '15%', align: 'center' },
          { key: 'reliability', label: t('misc.aia_col_reliability'), width: '20%', align: 'center' }]
          }
          data={Object.entries(modelComparison.models).map(([model, data]: [string, any]) => ({
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
            title={t('misc.aia_empty_models_title')}
            description={t('misc.aia_empty_models_desc')} />

          } />

          </MacOSCard>

          {/* Рекомендации */}
          <MacOSCard className="ai-analytics-card-padded">
            <h4 className="ai-analytics-h4">
              {t('misc.aia_recommendations')}
            </h4>

            <div className="ai-analytics-stat-grid ai-analytics-mb-4">
              {Object.entries(modelComparison.recommendations).map(([category, model]: [string, any]) =>
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
          {t('misc.aia_page_title')}
          </h1>
          <p className="ai-analytics-h1-subtitle">
            {t('misc.aia_page_subtitle')}
          </p>
        </div>
      </div>

      {/* Фильтры */}
      <MacOSCard className="ai-analytics-card-padded-sm">
        <div className="ai-analytics-filter-grid">
          <div>
            <label className="ai-analytics-filter-label">
              {t('misc.aia_start_date')}
            </label>
            <Input
              type="date"
              value={dateRange.startDate}
              onChange={(e) => setDateRange({ ...dateRange, startDate: e.target.value })} />

          </div>
          <div>
            <label className="ai-analytics-filter-label">
              {t('misc.aia_end_date')}
            </label>
            <Input
              type="date"
              value={dateRange.endDate}
              onChange={(e) => setDateRange({ ...dateRange, endDate: e.target.value })} />

          </div>
          <div>
            <label className="ai-analytics-filter-label">
              {t('misc.aia_ai_function')}
            </label>
            <Select
              value={filters.aiFunction}
              onChange={(e) => setFilters({ ...filters, aiFunction: e.target.value })}
              options={[
              { value: '', label: t('misc.aia_all_functions') },
              { value: 'diagnose_symptoms', label: t('misc.aia_func_diagnose') },
              { value: 'analyze_medical_image', label: t('misc.aia_func_image') },
              { value: 'generate_treatment_plan', label: t('misc.aia_func_treatment') },
              { value: 'check_drug_interactions', label: t('misc.aia_func_drugs') },
              { value: 'assess_patient_risk', label: t('misc.aia_func_risk') }]
              } />

          </div>
          <div className="ai-analytics-action-btn-end">
            <Button
              onClick={loadUsageAnalytics}
              disabled={loading}
              variant="primary"
              className="ai-analytics-action-btn-full">

              {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Filter style={{ width: '16px', height: '16px' }} />}
              {t('misc.aia_apply')}
            </Button>
          </div>
        </div>
      </MacOSCard>

      {/* Вкладки */}
      <MacOSTab
        tabs={[
        { id: 'overview', label: t('misc.aia_tab_overview'), icon: Activity },
        { id: 'usage', label: t('misc.aia_tab_usage'), icon: BarChart3 },
        { id: 'learning', label: t('misc.aia_tab_learning'), icon: Brain },
        { id: 'cost', label: t('misc.aia_costs'), icon: DollarSign },
        { id: 'models', label: t('misc.aia_tab_models'), icon: Cpu }]
        }
        activeTab={activeTab}
        onTabChange={(v: unknown) => setActiveTab(String(v))}
        size="default"
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
