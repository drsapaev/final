import React, { useEffect, useRef, useState } from 'react';
import Card from './ui/Card';
import Button from './ui/Button';
import { Download, RefreshCw, BarChart3, PieChart, TrendingUp, Activity } from 'lucide-react';
import { Chart, registerables } from 'chart.js';

// Регистрируем все компоненты Chart.js
Chart.register(...registerables);

const AnalyticsCharts = ({ 
  data, 
  loading = false, 
  onRefresh,
  onExport,
  title = "Аналитические графики"
}) => {
  const chartRefs = useRef({});
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    if (data?.charts) {
      renderCharts();
    }
  }, [data, activeTab]);

  const renderCharts = () => {
    if (!data?.charts) return;

    // Уничтожаем существующие графики
    Object.values(chartRefs.current).forEach(chart => {
      if (chart) chart.destroy();
    });
    chartRefs.current = {};

    // Рендерим новые графики
    for (const [chartName, chartConfig] of Object.entries(data.charts)) {
      const canvasId = `chart-${chartName}`;
      const canvas = document.getElementById(canvasId);
      
      if (canvas) {
        const ctx = canvas.getContext('2d');
        chartRefs.current[chartName] = new Chart(ctx, chartConfig);
      }
    }
  };

  const getChartIcon = (chartType) => {
    const iconStyle = { width: '16px', height: '16px' };
    switch (chartType) {
      case 'line': return <TrendingUp style={iconStyle} />;
      case 'bar': return <BarChart3 style={iconStyle} />;
      case 'doughnut': return <PieChart style={iconStyle} />;
      case 'radar': return <Activity style={iconStyle} />;
      default: return <BarChart3 style={iconStyle} />;
    }
  };

  const renderChartCard = (chartName, chartConfig) => {
    const canvasId = `chart-${chartName}`;
    
    return (
      <Card key={chartName} style={{ width: '100%' }}>
        <Card.Header style={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingBottom: '8px'
        }}>
          <div style={{
            fontSize: '14px',
            fontWeight: '500',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            {getChartIcon(chartConfig.type)}
            {chartConfig.options?.plugins?.title?.text || chartName}
          </div>
        </Card.Header>
        <Card.Content>
          <div style={{ height: '256px', width: '100%' }}>
            <canvas id={canvasId}></canvas>
          </div>
        </Card.Content>
      </Card>
    );
  };

  const renderTabContent = (tabData, tabName) => {
    if (!tabData || !tabData.charts) return null;

    const charts = Object.entries(tabData.charts);
    
    return (
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: '16px'
      }}>
        {charts.map(([chartName, chartConfig]) => 
          renderChartCard(chartName, chartConfig)
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <Card style={{ width: '100%' }}>
        <Card.Content style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '256px'
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <RefreshCw style={{ width: '16px', height: '16px' }} className="animate-spin" />
            <span>Загрузка графиков...</span>
          </div>
        </Card.Content>
      </Card>
    );
  }

  if (!data || !data.charts) {
    return (
      <Card style={{ width: '100%' }}>
        <Card.Content style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '256px'
        }}>
          <div style={{ textAlign: 'center' }}>
            <BarChart3 style={{ 
              width: '48px', 
              height: '48px', 
              margin: '0 auto 16px auto',
              color: 'var(--text-secondary)'
            }} />
            <p style={{ color: 'var(--text-secondary)' }}>Нет данных для отображения</p>
          </div>
        </Card.Content>
      </Card>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <h2 style={{
          fontSize: '24px',
          fontWeight: '700',
          color: 'var(--text-primary)'
        }}>{title}</h2>
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button
            onClick={onRefresh}
            disabled={loading}
            style={{
              padding: '8px 16px',
              background: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <RefreshCw style={{ width: '16px', height: '16px' }} className={loading ? 'animate-spin' : ''} />
            Обновить
          </Button>
          <Button
            onClick={onExport}
            style={{
              padding: '8px 16px',
              background: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <Download style={{ width: '16px', height: '16px' }} />
            Экспорт
          </Button>
        </div>
      </div>

      {data.summary && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px'
        }}>
          <Card>
            <Card.Content style={{ padding: '16px' }}>
              <div style={{
                fontSize: '24px',
                fontWeight: '700',
                color: 'var(--text-primary)'
              }}>{data.summary.total_charts}</div>
              <p style={{
                fontSize: '14px',
                color: 'var(--text-secondary)',
                margin: '4px 0 0 0'
              }}>Всего графиков</p>
            </Card.Content>
          </Card>
          <Card>
            <Card.Content style={{ padding: '16px' }}>
              <div style={{
                fontSize: '24px',
                fontWeight: '700',
                color: 'var(--text-primary)'
              }}>{data.summary.chart_types?.length || 0}</div>
              <p style={{
                fontSize: '14px',
                color: 'var(--text-secondary)',
                margin: '4px 0 0 0'
              }}>Типов графиков</p>
            </Card.Content>
          </Card>
          <Card>
            <Card.Content style={{ padding: '16px' }}>
              <div style={{
                fontSize: '24px',
                fontWeight: '700',
                color: 'var(--text-primary)'
              }}>
                {data.period ? 
                  `${new Date(data.period.start_date).toLocaleDateString()} - ${new Date(data.period.end_date).toLocaleDateString()}` 
                  : 'N/A'
                }
              </div>
              <p style={{
                fontSize: '14px',
                color: 'var(--text-secondary)',
                margin: '4px 0 0 0'
              }}>Период анализа</p>
            </Card.Content>
          </Card>
        </div>
      )}

      {Object.keys(data.charts).length > 1 ? (
        <div>
          <div style={{
            display: 'flex',
            gap: '8px',
            marginBottom: '24px',
            borderBottom: '1px solid var(--border-color)'
          }}>
            {[
              { id: 'overview', label: 'Обзор' },
              { id: 'kpi', label: 'KPI' },
              { id: 'doctors', label: 'Врачи' },
              { id: 'revenue', label: 'Доходы' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: '12px 20px',
                  background: activeTab === tab.id ? 'var(--accent-color)' : 'transparent',
                  color: activeTab === tab.id ? 'white' : 'var(--text-primary)',
                  border: 'none',
                  borderRadius: '8px 8px 0 0',
                  cursor: 'pointer',
                  fontWeight: '500',
                  transition: 'all 0.2s ease'
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>
          
          {activeTab === 'overview' && renderTabContent(data.charts.overview || data, 'overview')}
          {activeTab === 'kpi' && renderTabContent(data.charts.kpi, 'kpi')}
          {activeTab === 'doctors' && renderTabContent(data.charts.doctors, 'doctors')}
          {activeTab === 'revenue' && renderTabContent(data.charts.revenue, 'revenue')}
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '16px'
        }}>
          {Object.entries(data.charts).map(([chartName, chartConfig]) => 
            renderChartCard(chartName, chartConfig)
          )}
        </div>
      )}
    </div>
  );
};

export default AnalyticsCharts;
