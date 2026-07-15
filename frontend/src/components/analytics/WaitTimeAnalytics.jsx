import { useState, useEffect, useCallback } from 'react';
import {
  MacOSCard,
  Button,
  Badge,
  Input,
  MacOSTab,
  MacOSStatCard,
  MacOSEmptyState,
  Skeleton,
} from '../ui/macos';
import {
  Clock,
  TrendingUp,
  TrendingDown,
  Users,
  Calendar,
  BarChart3,
  Activity,
  AlertTriangle,
  CheckCircle,
  RefreshCw,

  Filter,
  Eye,
  Zap } from
'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../api/client';
import './WaitTimeAnalytics.css';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/adapter';
const WaitTimeAnalytics = () => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [dateRange, setDateRange] = useState({
    startDate: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    endDate: new Date().toISOString().split('T')[0]
  });
  const [filters, setFilters] = useState({
    department: '',
    doctorId: null
  });

  // Данные аналитики
  const [analytics, setAnalytics] = useState(null);
  const [realTimeEstimates, setRealTimeEstimates] = useState(null);
  const [serviceAnalytics, setServiceAnalytics] = useState(null);
  const [summary, setSummary] = useState(null);
  const [heatmapData, setHeatmapData] = useState(null);

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        start_date: dateRange.startDate,
        end_date: dateRange.endDate
      });

      if (filters.department) params.append('department', filters.department);
      if (filters.doctorId) params.append('doctor_id', filters.doctorId);

      const response = await api.get(`/analytics/wait-time/wait-time-analytics?${params}`);
      setAnalytics(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки аналитики времени ожидания:', error);
      toast.error('Ошибка загрузки аналитики');
    } finally {
      setLoading(false);
    }
  }, [dateRange.endDate, dateRange.startDate, filters.department, filters.doctorId]);

  const loadRealTimeEstimates = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (filters.department) params.append('department', filters.department);

      const response = await api.get(`/analytics/wait-time/real-time-wait-estimates?${params}`);
      setRealTimeEstimates(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки real-time оценок:', error);
    }
  }, [filters.department]);

  const loadServiceAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        start_date: dateRange.startDate,
        end_date: dateRange.endDate
      });

      const response = await api.get(`/analytics/wait-time/service-wait-analytics?${params}`);
      setServiceAnalytics(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки аналитики по услугам:', error);
      toast.error('Ошибка загрузки аналитики по услугам');
    } finally {
      setLoading(false);
    }
  }, [dateRange.endDate, dateRange.startDate]);

  const loadSummary = useCallback(async () => {
    try {
      const params = new URLSearchParams({ days: 7 });
      if (filters.department) params.append('department', filters.department);

      const response = await api.get(`/analytics/wait-time/wait-time-summary?${params}`);
      setSummary(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки сводки:', error);
    }
  }, [filters.department]);

  const loadHeatmap = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        start_date: dateRange.startDate,
        end_date: dateRange.endDate
      });

      if (filters.department) params.append('department', filters.department);

      const response = await api.get(`/analytics/wait-time/wait-time-heatmap?${params}`);
      setHeatmapData(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки тепловой карты:', error);
      toast.error('Ошибка загрузки тепловой карты');
    } finally {
      setLoading(false);
    }
  }, [dateRange.endDate, dateRange.startDate, filters.department]);

  useEffect(() => {
    loadAnalytics();
    loadRealTimeEstimates();
    loadSummary();

    // Обновляем real-time данные каждые 30 секунд
    const interval = setInterval(loadRealTimeEstimates, 30000);
    return () => clearInterval(interval);
  }, [loadAnalytics, loadRealTimeEstimates, loadSummary]);

  // Загружаем данные при переключении на вкладки
  useEffect(() => {
    if (activeTab === 'detailed' && !analytics) {
      loadAnalytics();
    }
    if (activeTab === 'services' && !serviceAnalytics) {
      loadServiceAnalytics();
    }
    if (activeTab === 'heatmap' && !heatmapData) {
      loadHeatmap();
    }
  }, [
    activeTab,
    analytics,
    heatmapData,
    loadAnalytics,
    loadHeatmap,
    loadServiceAnalytics,
    serviceAnalytics
  ]);

  const formatTime = (minutes) => {
    if (minutes < 60) {
      return `${Math.round(minutes)} мин`;
    }
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    return `${hours}ч ${mins}м`;
  };

  const getPerformanceColor = (rating) => {
    switch (rating) {
      case 'Отлично':return 'var(--mac-success)';
      case 'Хорошо':return 'var(--mac-info)';
      case 'Удовлетворительно':return 'var(--mac-warning)';
      case 'Требует улучшения':return 'var(--mac-warning)';
      case 'Критично':return 'var(--mac-error)';
      default:return 'var(--mac-text-secondary)';
    }
  };

  const renderOverviewTab = () =>
  <div className="wta-tab-content">
      {/* Сводка */}
      {summary &&
    <MacOSCard className="wta-card-padded">
          <div className="wta-section-header">
            <h3 className="wta-h3">
              <Activity style={{ width: '20px', height: '20px' }} />
              Сводка за последние {summary.period_days} дней
            </h3>
            <Badge
          variant="secondary"
          style={{
            backgroundColor: getPerformanceColor(summary.performance_rating),
            color: 'white'
          }}>
          
              {summary.performance_rating}
            </Badge>
          </div>

          <div className="wta-stat-grid">
            <MacOSStatCard
          title="Среднее время ожидания"
          value={formatTime(summary.average_wait_time_minutes)}
          icon={Clock}
          color="var(--mac-info)" />
        

            <MacOSStatCard
          title="Медианное время"
          value={formatTime(summary.median_wait_time_minutes)}
          icon={Activity}
          color="var(--mac-success)" />
        

            <MacOSStatCard
          title="Проанализировано записей"
          value={summary.total_analyzed_entries.toString()}
          icon={BarChart3}
          color="var(--mac-accent-purple)" />
        

            <MacOSStatCard
          title="Тренд"
          value={`${Math.abs(summary.trend_change_percent)}%`}
          icon={summary.trend_change_percent > 0 ? TrendingUp : TrendingDown}
          color={summary.trend_change_percent > 0 ? 'var(--mac-error)' : 'var(--mac-success)'} />
        
          </div>

          {summary.top_recommendations && summary.top_recommendations.length > 0 &&
      <div className="wta-mt-4">
              <h4 className="wta-h4">
                Рекомендации
              </h4>
              <div className="wta-recommendations-list">
                {summary.top_recommendations.map((recommendation, index) =>
          <div
            key={index}
            className="wta-recommendation-item wta-recommendation-warning">
            
                    <AlertTriangle style={{ width: '16px', height: '16px', color: 'var(--mac-warning)' }} />
                    <span className="wta-recommendation-text">
                      {recommendation}
                    </span>
                  </div>
          )}
              </div>
            </div>
      }
        </MacOSCard>
    }

      {/* Real-time оценки */}
      {realTimeEstimates &&
    <MacOSCard className="wta-card-padded">
          <div className="wta-section-header">
            <h3 className="wta-h3">
              <Zap style={{ width: '20px', height: '20px' }} />
              Текущие оценки времени ожидания
            </h3>
            <div className="wta-dept-median">
              Обновлено: {new Date(realTimeEstimates.timestamp).toLocaleTimeString()}
            </div>
          </div>

          {Object.keys(realTimeEstimates.queues).length === 0 ?
      <MacOSEmptyState
        icon={Clock}
        title="Нет активных очередей"
        description="В данный момент нет активных очередей для отображения" /> :


      <div className="wta-grid-gap">
              {Object.values(realTimeEstimates.queues).map((queue) =>
        <div
          key={queue.queue_id}
          className="wta-queue-card">
          
                  <div>
                    <div className="wta-queue-name">
                      {queue.department} - {queue.doctor_name}
                    </div>
                    <div className="wta-queue-stats">
                      <span className="wta-queue-stat">
                        <Users style={{ width: '14px', height: '14px' }} />
                        {queue.current_queue_length} в очереди
                      </span>
                      <span className="wta-queue-stat">
                        <Clock style={{ width: '14px', height: '14px' }} />
                        ~{formatTime(queue.average_service_time)} на пациента
                      </span>
                    </div>
                  </div>
                  <div className="wta-queue-right">
                    <div style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: queue.estimated_wait_time_minutes > 30 ? 'var(--mac-error)' : 'var(--mac-success)'
            }}>
                      {formatTime(queue.estimated_wait_time_minutes)}
                    </div>
                    <div style={{
              fontSize: 'var(--mac-font-size-xs)',
              color: 'var(--mac-text-tertiary)'
            }}>
                      Уверенность: {Math.round(queue.confidence_level * 100)}%
                    </div>
                  </div>
                </div>
        )}
            </div>
      }

          {realTimeEstimates.summary && Object.keys(realTimeEstimates.queues).length > 0 &&
      <div className="wta-summary-box">
              <div className="wta-summary-row">
                <span className="wta-recommendation-text-default">Минимальное ожидание: <strong>{formatTime(realTimeEstimates.summary.shortest_wait)}</strong></span>
                <span className="wta-recommendation-text-default">Среднее ожидание: <strong>{formatTime(realTimeEstimates.summary.average_wait)}</strong></span>
                <span className="wta-recommendation-text-default">Максимальное ожидание: <strong>{formatTime(realTimeEstimates.summary.longest_wait)}</strong></span>
              </div>
            </div>
      }
        </MacOSCard>
    }
    </div>;


  const renderDetailedTab = () =>
  <div className="wta-tab-content">
      {loading ?
    <MacOSCard className="wta-card-padded">
          <Skeleton height="200px" />
        </MacOSCard> :
    analytics ?
    <>
          {/* Общая статистика */}
          <MacOSCard className="wta-card-padded">
            <h3 className="wta-h3-mb16">
              <BarChart3 style={{ width: '20px', height: '20px' }} />
              Детальная статистика ({analytics.period.start_date} - {analytics.period.end_date})
            </h3>

            <div className="wta-stat-grid-sm">
              <MacOSStatCard
            title="Среднее"
            value={formatTime(analytics.overall_stats.average_minutes)}
            icon={Clock}
            color="var(--mac-info)" />
          

              <MacOSStatCard
            title="Медиана"
            value={formatTime(analytics.overall_stats.median_minutes)}
            icon={Activity}
            color="var(--mac-success)" />
          

              <MacOSStatCard
            title="Минимум"
            value={formatTime(analytics.overall_stats.min_minutes)}
            icon={TrendingDown}
            color="var(--mac-warning)" />
          

              <MacOSStatCard
            title="Максимум"
            value={formatTime(analytics.overall_stats.max_minutes)}
            icon={TrendingUp}
            color="var(--mac-error)" />
          

              <MacOSStatCard
            title="90-й процентиль"
            value={formatTime(analytics.overall_stats.percentile_90)}
            icon={BarChart3}
            color="var(--mac-accent-purple)" />
          
            </div>
          </MacOSCard>

          {/* Разбивка по отделениям */}
          {Object.keys(analytics.department_breakdown).length > 0 &&
      <MacOSCard className="wta-card-padded">
              <h3 className="wta-h3-mb16-no-icon">
                По отделениям
              </h3>
              <div className="wta-grid-gap">
                {Object.entries(analytics.department_breakdown).map(([dept, stats]) =>
          <div
            key={dept}
            className="wta-dept-card">
            
                    <div>
                      <div className="wta-dept-name">
                        {dept}
                      </div>
                      <div className="wta-dept-count">
                        {stats.count} записей
                      </div>
                    </div>
                    <div className="wta-queue-right">
                      <div className="wta-dept-avg">
                        {formatTime(stats.average_minutes)}
                      </div>
                      <div className="wta-dept-median">
                        медиана: {formatTime(stats.median_minutes)}
                      </div>
                    </div>
                  </div>
          )}
              </div>
            </MacOSCard>
      }

          {/* Рекомендации */}
          {analytics.recommendations && analytics.recommendations.length > 0 &&
      <MacOSCard className="wta-card-padded">
              <h3 className="wta-h3-mb16-no-icon">
                Рекомендации по улучшению
              </h3>
              <div className="wta-recommendations-list-gap2">
                {analytics.recommendations.map((recommendation, index) =>
          <div
            key={index}
            className="wta-recommendation-info">
            
                    <CheckCircle style={{ width: '16px', height: '16px', color: 'var(--mac-info)' }} />
                    <span className="wta-recommendation-text-default">
                      {recommendation}
                    </span>
                  </div>
          )}
              </div>
            </MacOSCard>
      }
        </> :

    <MacOSEmptyState
      icon={BarChart3}
      title="Нет данных для детального анализа"
      description="Примените фильтры и загрузите данные для отображения детальной статистики" />

    }
    </div>;


  const renderServicesTab = () =>
  <div className="wta-tab-content">
      <div className="wta-section-header-no-mb">
        <h3 className="wta-h3-mb16-no-icon">
          Аналитика по услугам
        </h3>
        <Button
        onClick={loadServiceAnalytics}
        disabled={loading}
        variant="outline"
        className="wta-action-btn">
        
          {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Eye style={{ width: '16px', height: '16px' }} />}
          Загрузить
        </Button>
      </div>

      {loading ?
    <MacOSCard className="wta-card-padded">
          <Skeleton height="300px" />
        </MacOSCard> :
    serviceAnalytics && Object.keys(serviceAnalytics.service_analytics).length > 0 ?
    <MacOSCard className="wta-card-padded">
          <div className="wta-grid-gap">
            {Object.entries(serviceAnalytics.service_analytics).map(([serviceCode, data]) =>
        <div
          key={serviceCode}
          className="wta-service-card">
          
                <div className="wta-service-header">
                  <div>
                    <div className="wta-dept-name">
                      {data.service_name}
                    </div>
                    <div className="wta-dept-count">
                      Код: {serviceCode} • {data.total_visits} визитов
                    </div>
                  </div>
                  {data.service_efficiency &&
            <Badge
              variant={data.service_efficiency.efficiency_score > 80 ? 'success' : 'warning'}>
              
                      {data.service_efficiency.efficiency_score}% эффективность
                    </Badge>
            }
                </div>
                
                {data.wait_time_stats &&
          <div className="wta-stat-grid-xs">
                    <MacOSStatCard
              title="Среднее"
              value={formatTime(data.wait_time_stats.average_minutes)}
              icon={Clock}
              color="var(--mac-info)"
              size="small" />
            

                    <MacOSStatCard
              title="Медиана"
              value={formatTime(data.wait_time_stats.median_minutes)}
              icon={Activity}
              color="var(--mac-success)"
              size="small" />
            

                    <MacOSStatCard
              title="Анализ"
              value={data.analyzed_visits.toString()}
              icon={BarChart3}
              color="var(--mac-accent-purple)"
              size="small" />
            
                  </div>
          }
              </div>
        )}
          </div>
        </MacOSCard> :

    <MacOSEmptyState
      icon={Users}
      title="Нет данных по услугам"
      description="Нажмите 'Загрузить' или переключитесь на эту вкладку для автоматической загрузки данных по услугам" />

    }
    </div>;


  const renderHeatmapTab = () =>
  <div className="wta-tab-content">
      <div className="wta-section-header-no-mb">
        <h3 className="wta-h3-mb16-no-icon">
          Тепловая карта времени ожидания
        </h3>
        <Button
        onClick={loadHeatmap}
        disabled={loading}
        variant="outline"
        className="wta-action-btn">
        
          {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <BarChart3 style={{ width: '16px', height: '16px' }} />}
          Загрузить
        </Button>
      </div>

      {loading ?
    <MacOSCard className="wta-card-padded">
          <Skeleton height="400px" />
        </MacOSCard> :
    heatmapData ?
    <MacOSCard className="wta-card-padded">
          <div className="wta-mb-4">
            <h4 className="wta-h4">
              Время ожидания по часам дня
            </h4>
            <div className="wta-dept-count">
              Период: {heatmapData.period.start_date} - {heatmapData.period.end_date}
            </div>
          </div>

          <div className="wta-heatmap-grid">
            {heatmapData.heatmap_data.map((hourData) =>
        <div
          key={hourData.hour}
          style={{
            padding: 'var(--mac-spacing-2)',
            backgroundColor: `rgba(59, 130, 246, ${hourData.intensity})`,
            color: hourData.intensity > 0.5 ? 'white' : 'var(--mac-text-primary)',
            borderRadius: 'var(--mac-radius-sm)',
            textAlign: 'center',
            border: '1px solid var(--mac-border)'
          }}>
          
                <div style={{ fontSize: 'var(--mac-font-size-xs)', fontWeight: 'var(--mac-font-weight-semibold)' }}>
                  {hourData.hour_label}
                </div>
                <div style={{ fontSize: 'var(--mac-font-size-xs)' }}>
                  {formatTime(hourData.average_wait_minutes)}
                </div>
                <div style={{ fontSize: 'var(--mac-font-size-xs)', opacity: 0.8 }}>
                  {hourData.patient_count} пац.
                </div>
              </div>
        )}
          </div>

          {heatmapData.summary &&
      <div style={{
        padding: 'var(--mac-spacing-4)',
        backgroundColor: 'var(--mac-bg-secondary)',
        borderRadius: 'var(--mac-radius-sm)',
        display: 'flex',
        justifyContent: 'space-between',
        fontSize: 'var(--mac-font-size-sm)'
      }}>
              <span className="wta-recommendation-text-default">Пиковый час: <strong>{heatmapData.summary.peak_hour}:00</strong></span>
              <span className="wta-recommendation-text-default">Лучший час: <strong>{heatmapData.summary.best_hour}:00</strong></span>
              <span className="wta-recommendation-text-default">Самый загруженный: <strong>{heatmapData.summary.busiest_hour}:00</strong></span>
            </div>
      }
        </MacOSCard> :

    <MacOSEmptyState
      icon={Calendar}
      title="Нет данных тепловой карты"
      description="Нажмите 'Загрузить' или переключитесь на эту вкладку для автоматической загрузки данных тепловой карты" />

    }
    </div>;


  const tabs = [
  { id: 'overview', label: 'Обзор', icon: Activity },
  { id: 'detailed', label: 'Детально', icon: BarChart3 },
  { id: 'services', label: 'По услугам', icon: Users },
  { id: 'heatmap', label: 'Тепловая карта', icon: Calendar }];


  return (
    <div className="wta-tab-content">
      {/* Заголовок */}
      <div className="wta-header">
        <Clock style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
        <div>
          <h1 className="wta-h1">
            Аналитика времени ожидания
          </h1>
          <p className="wta-h1-subtitle">
            Анализ времени ожидания пациентов и оптимизация очередей
          </p>
        </div>
      </div>

      {/* Фильтры */}
      <MacOSCard className="wta-card-padded">
        <div className="wta-stat-grid">
          <div>
            <label className="wta-filter-label">
              Начальная дата
            </label>
            <Input
              type="date"
              value={dateRange.startDate}
              onChange={(e) => setDateRange({ ...dateRange, startDate: e.target.value })} />
            
          </div>
          <div>
            <label className="wta-filter-label">
              Конечная дата
            </label>
            <Input
              type="date"
              value={dateRange.endDate}
              onChange={(e) => setDateRange({ ...dateRange, endDate: e.target.value })} />
            
          </div>
          <div>
            <label className="wta-filter-label">
              Отделение
            </label>
            <Input
              placeholder="Фильтр по отделению"
              value={filters.department}
              onChange={(e) => setFilters({ ...filters, department: e.target.value })} />
            
          </div>
          <div className="wta-action-btn-end">
            <Button
              onClick={loadAnalytics}
              disabled={loading}
              variant="primary"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--mac-spacing-2)'
              }}>
              
              {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Filter style={{ width: '16px', height: '16px' }} />}
              Применить
            </Button>
          </div>
        </div>
      </MacOSCard>

      {/* Вкладки */}
      <MacOSTab
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab} />
      

      {/* Содержимое вкладок */}
      {activeTab === 'overview' && renderOverviewTab()}
      {activeTab === 'detailed' && renderDetailedTab()}
      {activeTab === 'services' && renderServicesTab()}
      {activeTab === 'heatmap' && renderHeatmapTab()}
    </div>);

};

export default WaitTimeAnalytics;
