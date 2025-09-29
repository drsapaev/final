import React, { useState, useEffect } from 'react';
import { Card, Button, Badge, Input, Label, Select } from '../ui/native';
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
import { useTheme } from '../../contexts/ThemeContext';
import { toast } from 'react-toastify';
import api from '../../utils/api';

const WaitTimeAnalytics = () => {
  const { theme, getColor, getSpacing } = useTheme();
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
      case 'Отлично': return getColor('green', 600);
      case 'Хорошо': return getColor('blue', 600);
      case 'Удовлетворительно': return getColor('yellow', 600);
      case 'Требует улучшения': return getColor('orange', 600);
      case 'Критично': return getColor('red', 600);
      default: return getColor('gray', 600);
    }
  };

  const renderOverviewTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('lg') }}>
      {/* Сводка */}
      {summary && (
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
              Сводка за последние {summary.period_days} дней
            </h3>
            <Badge style={{ 
              backgroundColor: getPerformanceColor(summary.performance_rating),
              color: 'white'
            }}>
              {summary.performance_rating}
            </Badge>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: getSpacing('md') }}>
            <div style={{ 
              padding: getSpacing('md'),
              backgroundColor: getColor('blue', 50),
              borderRadius: '8px',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('blue', 600) }}>
                {formatTime(summary.average_wait_time_minutes)}
              </div>
              <div style={{ color: getColor('text', 600) }}>Среднее время ожидания</div>
            </div>

            <div style={{ 
              padding: getSpacing('md'),
              backgroundColor: getColor('green', 50),
              borderRadius: '8px',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('green', 600) }}>
                {formatTime(summary.median_wait_time_minutes)}
              </div>
              <div style={{ color: getColor('text', 600) }}>Медианное время</div>
            </div>

            <div style={{ 
              padding: getSpacing('md'),
              backgroundColor: getColor('purple', 50),
              borderRadius: '8px',
              textAlign: 'center'
            }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('purple', 600) }}>
                {summary.total_analyzed_entries}
              </div>
              <div style={{ color: getColor('text', 600) }}>Проанализировано записей</div>
            </div>

            <div style={{ 
              padding: getSpacing('md'),
              backgroundColor: summary.trend_change_percent > 0 ? getColor('red', 50) : getColor('green', 50),
              borderRadius: '8px',
              textAlign: 'center'
            }}>
              <div style={{ 
                fontSize: '24px', 
                fontWeight: 'bold', 
                color: summary.trend_change_percent > 0 ? getColor('red', 600) : getColor('green', 600),
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: getSpacing('xs')
              }}>
                {summary.trend_change_percent > 0 ? <TrendingUp size={20} /> : <TrendingDown size={20} />}
                {Math.abs(summary.trend_change_percent)}%
              </div>
              <div style={{ color: getColor('text', 600) }}>Тренд</div>
            </div>
          </div>

          {summary.top_recommendations && summary.top_recommendations.length > 0 && (
            <div style={{ marginTop: getSpacing('md') }}>
              <h4 style={{ 
                margin: `0 0 ${getSpacing('sm')} 0`,
                color: getColor('text', 900)
              }}>
                Рекомендации
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('xs') }}>
                {summary.top_recommendations.map((recommendation, index) => (
                  <div
                    key={index}
                    style={{
                      padding: getSpacing('sm'),
                      backgroundColor: getColor('yellow', 50),
                      border: `1px solid ${getColor('yellow', 200)}`,
                      borderRadius: '6px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: getSpacing('sm')
                    }}
                  >
                    <AlertTriangle size={16} color={getColor('yellow', 600)} />
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

      {/* Real-time оценки */}
      {realTimeEstimates && (
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
              <Zap size={20} />
              Текущие оценки времени ожидания
            </h3>
            <div style={{ fontSize: '12px', color: getColor('text', 500) }}>
              Обновлено: {new Date(realTimeEstimates.timestamp).toLocaleTimeString()}
            </div>
          </div>

          {Object.keys(realTimeEstimates.queues).length === 0 ? (
            <div style={{ 
              textAlign: 'center', 
              padding: getSpacing('xl'),
              color: getColor('text', 500)
            }}>
              Нет активных очередей
            </div>
          ) : (
            <div style={{ display: 'grid', gap: getSpacing('md') }}>
              {Object.values(realTimeEstimates.queues).map((queue) => (
                <div
                  key={queue.queue_id}
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
                    <div style={{ 
                      fontWeight: 'bold',
                      color: getColor('text', 900),
                      marginBottom: getSpacing('xs')
                    }}>
                      {queue.department} - {queue.doctor_name}
                    </div>
                    <div style={{ 
                      fontSize: '14px',
                      color: getColor('text', 600),
                      display: 'flex',
                      alignItems: 'center',
                      gap: getSpacing('md')
                    }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: getSpacing('xs') }}>
                        <Users size={14} />
                        {queue.current_queue_length} в очереди
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: getSpacing('xs') }}>
                        <Clock size={14} />
                        ~{formatTime(queue.average_service_time)} на пациента
                      </span>
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ 
                      fontSize: '20px', 
                      fontWeight: 'bold', 
                      color: queue.estimated_wait_time_minutes > 30 ? getColor('red', 600) : getColor('green', 600)
                    }}>
                      {formatTime(queue.estimated_wait_time_minutes)}
                    </div>
                    <div style={{ 
                      fontSize: '12px', 
                      color: getColor('text', 500)
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
              marginTop: getSpacing('md'),
              padding: getSpacing('md'),
              backgroundColor: getColor('gray', 50),
              borderRadius: '6px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px' }}>
                <span>Минимальное ожидание: <strong>{formatTime(realTimeEstimates.summary.shortest_wait)}</strong></span>
                <span>Среднее ожидание: <strong>{formatTime(realTimeEstimates.summary.average_wait)}</strong></span>
                <span>Максимальное ожидание: <strong>{formatTime(realTimeEstimates.summary.longest_wait)}</strong></span>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );

  const renderDetailedTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('lg') }}>
      {analytics && (
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
              Детальная статистика ({analytics.period.start_date} - {analytics.period.end_date})
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: getSpacing('md') }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: getColor('blue', 600) }}>
                  {formatTime(analytics.overall_stats.average_minutes)}
                </div>
                <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Среднее</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: getColor('green', 600) }}>
                  {formatTime(analytics.overall_stats.median_minutes)}
                </div>
                <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Медиана</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: getColor('orange', 600) }}>
                  {formatTime(analytics.overall_stats.min_minutes)}
                </div>
                <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Минимум</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: getColor('red', 600) }}>
                  {formatTime(analytics.overall_stats.max_minutes)}
                </div>
                <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Максимум</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: getColor('purple', 600) }}>
                  {formatTime(analytics.overall_stats.percentile_90)}
                </div>
                <div style={{ fontSize: '12px', color: getColor('text', 600) }}>90-й процентиль</div>
              </div>
            </div>
          </Card>

          {/* Разбивка по отделениям */}
          {Object.keys(analytics.department_breakdown).length > 0 && (
            <Card style={{ padding: getSpacing('lg') }}>
              <h3 style={{ 
                margin: `0 0 ${getSpacing('md')} 0`,
                color: getColor('text', 900)
              }}>
                По отделениям
              </h3>
              <div style={{ display: 'grid', gap: getSpacing('md') }}>
                {Object.entries(analytics.department_breakdown).map(([dept, stats]) => (
                  <div
                    key={dept}
                    style={{
                      padding: getSpacing('md'),
                      border: `1px solid ${getColor('gray', 200)}`,
                      borderRadius: '6px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 'bold', color: getColor('text', 900) }}>
                        {dept}
                      </div>
                      <div style={{ fontSize: '14px', color: getColor('text', 600) }}>
                        {stats.count} записей
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '16px', fontWeight: 'bold', color: getColor('blue', 600) }}>
                        {formatTime(stats.average_minutes)}
                      </div>
                      <div style={{ fontSize: '12px', color: getColor('text', 500) }}>
                        медиана: {formatTime(stats.median_minutes)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Рекомендации */}
          {analytics.recommendations && analytics.recommendations.length > 0 && (
            <Card style={{ padding: getSpacing('lg') }}>
              <h3 style={{ 
                margin: `0 0 ${getSpacing('md')} 0`,
                color: getColor('text', 900)
              }}>
                Рекомендации по улучшению
              </h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('sm') }}>
                {analytics.recommendations.map((recommendation, index) => (
                  <div
                    key={index}
                    style={{
                      padding: getSpacing('md'),
                      backgroundColor: getColor('blue', 50),
                      border: `1px solid ${getColor('blue', 200)}`,
                      borderRadius: '6px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: getSpacing('sm')
                    }}
                  >
                    <CheckCircle size={16} color={getColor('blue', 600)} />
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

  const renderServicesTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('lg') }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, color: getColor('text', 900) }}>
          Аналитика по услугам
        </h3>
        <Button 
          onClick={loadServiceAnalytics}
          disabled={loading}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: getSpacing('sm')
          }}
        >
          {loading ? <RefreshCw size={16} className="animate-spin" /> : <Eye size={16} />}
          Загрузить
        </Button>
      </div>

      {serviceAnalytics && Object.keys(serviceAnalytics.service_analytics).length > 0 && (
        <Card style={{ padding: getSpacing('lg') }}>
          <div style={{ display: 'grid', gap: getSpacing('md') }}>
            {Object.entries(serviceAnalytics.service_analytics).map(([serviceCode, data]) => (
              <div
                key={serviceCode}
                style={{
                  padding: getSpacing('md'),
                  border: `1px solid ${getColor('gray', 200)}`,
                  borderRadius: '8px'
                }}
              >
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  marginBottom: getSpacing('sm')
                }}>
                  <div>
                    <div style={{ fontWeight: 'bold', color: getColor('text', 900) }}>
                      {data.service_name}
                    </div>
                    <div style={{ fontSize: '14px', color: getColor('text', 600) }}>
                      Код: {serviceCode} • {data.total_visits} визитов
                    </div>
                  </div>
                  {data.service_efficiency && (
                    <Badge style={{ 
                      backgroundColor: data.service_efficiency.efficiency_score > 80 ? getColor('green', 100) : getColor('orange', 100),
                      color: data.service_efficiency.efficiency_score > 80 ? getColor('green', 800) : getColor('orange', 800)
                    }}>
                      {data.service_efficiency.efficiency_score}% эффективность
                    </Badge>
                  )}
                </div>
                
                {data.wait_time_stats && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: getSpacing('sm') }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '14px', fontWeight: 'bold', color: getColor('blue', 600) }}>
                        {formatTime(data.wait_time_stats.average_minutes)}
                      </div>
                      <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Среднее</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '14px', fontWeight: 'bold', color: getColor('green', 600) }}>
                        {formatTime(data.wait_time_stats.median_minutes)}
                      </div>
                      <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Медиана</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: '14px', fontWeight: 'bold', color: getColor('purple', 600) }}>
                        {data.analyzed_visits}
                      </div>
                      <div style={{ fontSize: '12px', color: getColor('text', 600) }}>Анализ</div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );

  const renderHeatmapTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('lg') }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, color: getColor('text', 900) }}>
          Тепловая карта времени ожидания
        </h3>
        <Button 
          onClick={loadHeatmap}
          disabled={loading}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: getSpacing('sm')
          }}
        >
          {loading ? <RefreshCw size={16} className="animate-spin" /> : <BarChart3 size={16} />}
          Загрузить
        </Button>
      </div>

      {heatmapData && (
        <Card style={{ padding: getSpacing('lg') }}>
          <div style={{ marginBottom: getSpacing('md') }}>
            <h4 style={{ margin: `0 0 ${getSpacing('sm')} 0`, color: getColor('text', 900) }}>
              Время ожидания по часам дня
            </h4>
            <div style={{ fontSize: '14px', color: getColor('text', 600) }}>
              Период: {heatmapData.period.start_date} - {heatmapData.period.end_date}
            </div>
          </div>

          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(80px, 1fr))', 
            gap: getSpacing('sm'),
            marginBottom: getSpacing('md')
          }}>
            {heatmapData.heatmap_data.map((hourData) => (
              <div
                key={hourData.hour}
                style={{
                  padding: getSpacing('sm'),
                  backgroundColor: `rgba(59, 130, 246, ${hourData.intensity})`,
                  color: hourData.intensity > 0.5 ? 'white' : getColor('text', 900),
                  borderRadius: '6px',
                  textAlign: 'center',
                  border: `1px solid ${getColor('gray', 200)}`
                }}
              >
                <div style={{ fontSize: '12px', fontWeight: 'bold' }}>
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
              padding: getSpacing('md'),
              backgroundColor: getColor('gray', 50),
              borderRadius: '6px',
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '14px'
            }}>
              <span>Пиковый час: <strong>{heatmapData.summary.peak_hour}:00</strong></span>
              <span>Лучший час: <strong>{heatmapData.summary.best_hour}:00</strong></span>
              <span>Самый загруженный: <strong>{heatmapData.summary.busiest_hour}:00</strong></span>
            </div>
          )}
        </Card>
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
    <div style={{ padding: getSpacing('lg') }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: getSpacing('md'),
        marginBottom: getSpacing('lg')
      }}>
        <Clock size={24} color={getColor('primary', 600)} />
        <h2 style={{ 
          margin: 0, 
          color: getColor('text', 900),
          fontSize: '24px',
          fontWeight: 'bold'
        }}>
          Аналитика времени ожидания
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
            <Label>Отделение</Label>
            <Input
              placeholder="Фильтр по отделению"
              value={filters.department}
              onChange={(e) => setFilters({...filters, department: e.target.value})}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'end' }}>
            <Button 
              onClick={loadAnalytics}
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
      {activeTab === 'detailed' && renderDetailedTab()}
      {activeTab === 'services' && renderServicesTab()}
      {activeTab === 'heatmap' && renderHeatmapTab()}
    </div>
  );
};

export default WaitTimeAnalytics;

