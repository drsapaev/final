import React, { useState, useEffect } from 'react';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSBadge, 
  MacOSInput, 
  MacOSSelect, 
  MacOSTab,
  MacOSStatCard,
  MacOSEmptyState,
  MacOSLoadingSkeleton
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
  Download,
  Filter,
  Eye,
  Zap
} from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../utils/api';

const WaitTimeAnalytics = () => {
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

  useEffect(() => {
    loadAnalytics();
    loadRealTimeEstimates();
    loadSummary();
    
    // Обновляем real-time данные каждые 30 секунд
    const interval = setInterval(loadRealTimeEstimates, 30000);
    return () => clearInterval(interval);
  }, [dateRange, filters]);

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
  }, [activeTab]);

  const loadAnalytics = async () => {
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
      console.error('Ошибка загрузки аналитики времени ожидания:', error);
      toast.error('Ошибка загрузки аналитики');
    } finally {
      setLoading(false);
    }
  };

  const loadRealTimeEstimates = async () => {
    try {
      const params = new URLSearchParams();
      if (filters.department) params.append('department', filters.department);

      const response = await api.get(`/analytics/wait-time/real-time-wait-estimates?${params}`);
      setRealTimeEstimates(response.data);
    } catch (error) {
      console.error('Ошибка загрузки real-time оценок:', error);
    }
  };

  const loadServiceAnalytics = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        start_date: dateRange.startDate,
        end_date: dateRange.endDate
      });

      const response = await api.get(`/analytics/wait-time/service-wait-analytics?${params}`);
      setServiceAnalytics(response.data);
    } catch (error) {
      console.error('Ошибка загрузки аналитики по услугам:', error);
      toast.error('Ошибка загрузки аналитики по услугам');
    } finally {
      setLoading(false);
    }
  };

  const loadSummary = async () => {
    try {
      const params = new URLSearchParams({ days: 7 });
      if (filters.department) params.append('department', filters.department);

      const response = await api.get(`/analytics/wait-time/wait-time-summary?${params}`);
      setSummary(response.data);
    } catch (error) {
      console.error('Ошибка загрузки сводки:', error);
    }
  };

  const loadHeatmap = async () => {
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
      console.error('Ошибка загрузки тепловой карты:', error);
      toast.error('Ошибка загрузки тепловой карты');
    } finally {
      setLoading(false);
    }
  };

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
      case 'Отлично': return 'var(--mac-success)';
      case 'Хорошо': return 'var(--mac-info)';
      case 'Удовлетворительно': return 'var(--mac-warning)';
      case 'Требует улучшения': return 'var(--mac-warning)';
      case 'Критично': return 'var(--mac-error)';
      default: return 'var(--mac-text-secondary)';
    }
  };

  const renderOverviewTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Сводка */}
      {summary && (
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
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <Activity style={{ width: '20px', height: '20px' }} />
              Сводка за последние {summary.period_days} дней
            </h3>
            <MacOSBadge 
              variant="secondary"
              style={{ 
                backgroundColor: getPerformanceColor(summary.performance_rating),
                color: 'white'
              }}
            >
              {summary.performance_rating}
            </MacOSBadge>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <MacOSStatCard
              title="Среднее время ожидания"
              value={formatTime(summary.average_wait_time_minutes)}
              icon={Clock}
              color="var(--mac-info)"
            />

            <MacOSStatCard
              title="Медианное время"
              value={formatTime(summary.median_wait_time_minutes)}
              icon={Activity}
              color="var(--mac-success)"
            />

            <MacOSStatCard
              title="Проанализировано записей"
              value={summary.total_analyzed_entries.toString()}
              icon={BarChart3}
              color="var(--mac-accent-purple)"
            />

            <MacOSStatCard
              title="Тренд"
              value={`${Math.abs(summary.trend_change_percent)}%`}
              icon={summary.trend_change_percent > 0 ? TrendingUp : TrendingDown}
              color={summary.trend_change_percent > 0 ? 'var(--mac-error)' : 'var(--mac-success)'}
            />
          </div>

          {summary.top_recommendations && summary.top_recommendations.length > 0 && (
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
                {summary.top_recommendations.map((recommendation, index) => (
                  <div
                    key={index}
                    style={{
                      padding: '8px',
                      backgroundColor: 'var(--mac-warning-bg)',
                      border: '1px solid var(--mac-warning-border)',
                      borderRadius: 'var(--mac-radius-sm)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                  >
                    <AlertTriangle style={{ width: '16px', height: '16px', color: 'var(--mac-warning)' }} />
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

      {/* Real-time оценки */}
      {realTimeEstimates && (
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
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <Zap style={{ width: '20px', height: '20px' }} />
              Текущие оценки времени ожидания
            </h3>
            <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)' }}>
              Обновлено: {new Date(realTimeEstimates.timestamp).toLocaleTimeString()}
            </div>
          </div>

          {Object.keys(realTimeEstimates.queues).length === 0 ? (
            <MacOSEmptyState
              icon={Clock}
              title="Нет активных очередей"
              description="В данный момент нет активных очередей для отображения"
            />
          ) : (
            <div style={{ display: 'grid', gap: '16px' }}>
              {Object.values(realTimeEstimates.queues).map((queue) => (
                <div
                  key={queue.queue_id}
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
                    <div style={{ 
                      fontWeight: 'var(--mac-font-weight-semibold)',
                      color: 'var(--mac-text-primary)',
                      marginBottom: '4px'
                    }}>
                      {queue.department} - {queue.doctor_name}
                    </div>
                    <div style={{ 
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-secondary)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '16px'
                    }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Users style={{ width: '14px', height: '14px' }} />
                        {queue.current_queue_length} в очереди
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Clock style={{ width: '14px', height: '14px' }} />
                        ~{formatTime(queue.average_service_time)} на пациента
                      </span>
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ 
                      fontSize: '20px', 
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
              ))}
            </div>
          )}

          {realTimeEstimates.summary && Object.keys(realTimeEstimates.queues).length > 0 && (
            <div style={{ 
              marginTop: '16px',
              padding: '16px',
              backgroundColor: 'var(--mac-bg-secondary)',
              borderRadius: 'var(--mac-radius-sm)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--mac-font-size-sm)' }}>
                <span style={{ color: 'var(--mac-text-primary)' }}>Минимальное ожидание: <strong>{formatTime(realTimeEstimates.summary.shortest_wait)}</strong></span>
                <span style={{ color: 'var(--mac-text-primary)' }}>Среднее ожидание: <strong>{formatTime(realTimeEstimates.summary.average_wait)}</strong></span>
                <span style={{ color: 'var(--mac-text-primary)' }}>Максимальное ожидание: <strong>{formatTime(realTimeEstimates.summary.longest_wait)}</strong></span>
              </div>
            </div>
          )}
        </MacOSCard>
      )}
    </div>
  );

  const renderDetailedTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {loading ? (
        <MacOSCard style={{ padding: '24px' }}>
          <MacOSLoadingSkeleton height="200px" />
        </MacOSCard>
      ) : analytics ? (
        <>
          {/* Общая статистика */}
          <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{ 
              margin: `0 0 16px 0`,
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <BarChart3 style={{ width: '20px', height: '20px' }} />
              Детальная статистика ({analytics.period.start_date} - {analytics.period.end_date})
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px' }}>
              <MacOSStatCard
                title="Среднее"
                value={formatTime(analytics.overall_stats.average_minutes)}
                icon={Clock}
                color="var(--mac-info)"
              />

              <MacOSStatCard
                title="Медиана"
                value={formatTime(analytics.overall_stats.median_minutes)}
                icon={Activity}
                color="var(--mac-success)"
              />

              <MacOSStatCard
                title="Минимум"
                value={formatTime(analytics.overall_stats.min_minutes)}
                icon={TrendingDown}
                color="var(--mac-warning)"
              />

              <MacOSStatCard
                title="Максимум"
                value={formatTime(analytics.overall_stats.max_minutes)}
                icon={TrendingUp}
                color="var(--mac-error)"
              />

              <MacOSStatCard
                title="90-й процентиль"
                value={formatTime(analytics.overall_stats.percentile_90)}
                icon={BarChart3}
                color="var(--mac-accent-purple)"
              />
            </div>
          </MacOSCard>

          {/* Разбивка по отделениям */}
          {Object.keys(analytics.department_breakdown).length > 0 && (
            <MacOSCard style={{ padding: '24px' }}>
              <h3 style={{ 
                margin: `0 0 16px 0`,
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-semibold)'
              }}>
                По отделениям
              </h3>
              <div style={{ display: 'grid', gap: '16px' }}>
                {Object.entries(analytics.department_breakdown).map(([dept, stats]) => (
                  <div
                    key={dept}
                    style={{
                      padding: '16px',
                      border: '1px solid var(--mac-border)',
                      borderRadius: 'var(--mac-radius-sm)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      backgroundColor: 'var(--mac-bg-secondary)'
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                        {dept}
                      </div>
                      <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                        {stats.count} записей
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '16px', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-info)' }}>
                        {formatTime(stats.average_minutes)}
                      </div>
                      <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)' }}>
                        медиана: {formatTime(stats.median_minutes)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </MacOSCard>
          )}

          {/* Рекомендации */}
          {analytics.recommendations && analytics.recommendations.length > 0 && (
            <MacOSCard style={{ padding: '24px' }}>
              <h3 style={{ 
                margin: `0 0 16px 0`,
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-semibold)'
              }}>
                Рекомендации по улучшению
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {analytics.recommendations.map((recommendation, index) => (
                  <div
                    key={index}
                    style={{
                      padding: '16px',
                      backgroundColor: 'var(--mac-info-bg)',
                      border: '1px solid var(--mac-info-border)',
                      borderRadius: 'var(--mac-radius-sm)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                  >
                    <CheckCircle style={{ width: '16px', height: '16px', color: 'var(--mac-info)' }} />
                    <span style={{ color: 'var(--mac-text-primary)' }}>
                      {recommendation}
                    </span>
                  </div>
                ))}
              </div>
            </MacOSCard>
          )}
        </>
      ) : (
        <MacOSEmptyState
          icon={BarChart3}
          title="Нет данных для детального анализа"
          description="Примените фильтры и загрузите данные для отображения детальной статистики"
        />
      )}
    </div>
  );

  const renderServicesTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ 
          margin: 0, 
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>
          Аналитика по услугам
        </h3>
        <MacOSButton 
          onClick={loadServiceAnalytics}
          disabled={loading}
          variant="outline"
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px'
          }}
        >
          {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <Eye style={{ width: '16px', height: '16px' }} />}
          Загрузить
        </MacOSButton>
      </div>

      {loading ? (
        <MacOSCard style={{ padding: '24px' }}>
          <MacOSLoadingSkeleton height="300px" />
        </MacOSCard>
      ) : serviceAnalytics && Object.keys(serviceAnalytics.service_analytics).length > 0 ? (
        <MacOSCard style={{ padding: '24px' }}>
          <div style={{ display: 'grid', gap: '16px' }}>
            {Object.entries(serviceAnalytics.service_analytics).map(([serviceCode, data]) => (
              <div
                key={serviceCode}
                style={{
                  padding: '16px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-md)',
                  backgroundColor: 'var(--mac-bg-secondary)'
                }}
              >
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  marginBottom: '8px'
                }}>
                  <div>
                    <div style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                      {data.service_name}
                    </div>
                    <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                      Код: {serviceCode} • {data.total_visits} визитов
                    </div>
                  </div>
                  {data.service_efficiency && (
                    <MacOSBadge 
                      variant={data.service_efficiency.efficiency_score > 80 ? "success" : "warning"}
                    >
                      {data.service_efficiency.efficiency_score}% эффективность
                    </MacOSBadge>
                  )}
                </div>
                
                {data.wait_time_stats && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: '8px' }}>
                    <MacOSStatCard
                      title="Среднее"
                      value={formatTime(data.wait_time_stats.average_minutes)}
                      icon={Clock}
                      color="var(--mac-info)"
                      size="small"
                    />

                    <MacOSStatCard
                      title="Медиана"
                      value={formatTime(data.wait_time_stats.median_minutes)}
                      icon={Activity}
                      color="var(--mac-success)"
                      size="small"
                    />

                    <MacOSStatCard
                      title="Анализ"
                      value={data.analyzed_visits.toString()}
                      icon={BarChart3}
                      color="var(--mac-accent-purple)"
                      size="small"
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        </MacOSCard>
      ) : (
        <MacOSEmptyState
          icon={Users}
          title="Нет данных по услугам"
          description="Нажмите 'Загрузить' или переключитесь на эту вкладку для автоматической загрузки данных по услугам"
        />
      )}
    </div>
  );

  const renderHeatmapTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ 
          margin: 0, 
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>
          Тепловая карта времени ожидания
        </h3>
        <MacOSButton 
          onClick={loadHeatmap}
          disabled={loading}
          variant="outline"
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px'
          }}
        >
          {loading ? <RefreshCw style={{ width: '16px', height: '16px' }} /> : <BarChart3 style={{ width: '16px', height: '16px' }} />}
          Загрузить
        </MacOSButton>
      </div>

      {loading ? (
        <MacOSCard style={{ padding: '24px' }}>
          <MacOSLoadingSkeleton height="400px" />
        </MacOSCard>
      ) : heatmapData ? (
        <MacOSCard style={{ padding: '24px' }}>
          <div style={{ marginBottom: '16px' }}>
            <h4 style={{ 
              margin: `0 0 8px 0`, 
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
              Время ожидания по часам дня
            </h4>
            <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
              Период: {heatmapData.period.start_date} - {heatmapData.period.end_date}
            </div>
          </div>

          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(80px, 1fr))', 
            gap: '8px',
            marginBottom: '16px'
          }}>
            {heatmapData.heatmap_data.map((hourData) => (
              <div
                key={hourData.hour}
                style={{
                  padding: '8px',
                  backgroundColor: `rgba(59, 130, 246, ${hourData.intensity})`,
                  color: hourData.intensity > 0.5 ? 'white' : 'var(--mac-text-primary)',
                  borderRadius: 'var(--mac-radius-sm)',
                  textAlign: 'center',
                  border: '1px solid var(--mac-border)'
                }}
              >
                <div style={{ fontSize: 'var(--mac-font-size-xs)', fontWeight: 'var(--mac-font-weight-semibold)' }}>
                  {hourData.hour_label}
                </div>
                <div style={{ fontSize: '10px' }}>
                  {formatTime(hourData.average_wait_minutes)}
                </div>
                <div style={{ fontSize: '9px', opacity: 0.8 }}>
                  {hourData.patient_count} пац.
                </div>
              </div>
            ))}
          </div>

          {heatmapData.summary && (
            <div style={{ 
              padding: '16px',
              backgroundColor: 'var(--mac-bg-secondary)',
              borderRadius: 'var(--mac-radius-sm)',
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 'var(--mac-font-size-sm)'
            }}>
              <span style={{ color: 'var(--mac-text-primary)' }}>Пиковый час: <strong>{heatmapData.summary.peak_hour}:00</strong></span>
              <span style={{ color: 'var(--mac-text-primary)' }}>Лучший час: <strong>{heatmapData.summary.best_hour}:00</strong></span>
              <span style={{ color: 'var(--mac-text-primary)' }}>Самый загруженный: <strong>{heatmapData.summary.busiest_hour}:00</strong></span>
            </div>
          )}
        </MacOSCard>
      ) : (
        <MacOSEmptyState
          icon={Calendar}
          title="Нет данных тепловой карты"
          description="Нажмите 'Загрузить' или переключитесь на эту вкладку для автоматической загрузки данных тепловой карты"
        />
      )}
    </div>
  );

  const tabs = [
    { id: 'overview', label: 'Обзор', icon: Activity },
    { id: 'detailed', label: 'Детально', icon: BarChart3 },
    { id: 'services', label: 'По услугам', icon: Users },
    { id: 'heatmap', label: 'Тепловая карта', icon: Calendar }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Заголовок */}
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '16px',
        marginBottom: '8px'
      }}>
        <Clock style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
        <div>
          <h1 style={{ 
            margin: 0, 
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-2xl)',
            fontWeight: 'var(--mac-font-weight-bold)'
          }}>
            Аналитика времени ожидания
          </h1>
          <p style={{ 
            margin: '4px 0 0 0',
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-base)'
          }}>
            Анализ времени ожидания пациентов и оптимизация очередей
          </p>
        </div>
      </div>

      {/* Фильтры */}
      <MacOSCard style={{ padding: '24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          <div>
            <label style={{ 
              display: 'block',
              marginBottom: '8px',
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)'
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
              marginBottom: '8px',
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)'
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
              marginBottom: '8px',
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)'
            }}>
              Отделение
            </label>
            <MacOSInput
              placeholder="Фильтр по отделению"
              value={filters.department}
              onChange={(e) => setFilters({...filters, department: e.target.value})}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'end' }}>
            <MacOSButton 
              onClick={loadAnalytics}
              disabled={loading}
              variant="primary"
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px'
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
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {/* Содержимое вкладок */}
      {activeTab === 'overview' && renderOverviewTab()}
      {activeTab === 'detailed' && renderDetailedTab()}
      {activeTab === 'services' && renderServicesTab()}
      {activeTab === 'heatmap' && renderHeatmapTab()}
    </div>
  );
};

export default WaitTimeAnalytics;

