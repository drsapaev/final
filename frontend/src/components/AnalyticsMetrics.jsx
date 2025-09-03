import React from 'react';

function AnalyticsMetrics({ metrics, columns = 4 }) {
  const getMetricColor = (type) => {
    switch (type) {
      case 'revenue': return '#10b981'; // green
      case 'visits': return '#3b82f6'; // blue
      case 'patients': return '#8b5cf6'; // purple
      case 'conversion': return '#f59e0b'; // amber
      case 'error': return '#ef4444'; // red
      default: return '#6b7280'; // gray
    }
  };

  const formatValue = (value, type) => {
    if (type === 'revenue') {
      return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'UZS',
        minimumFractionDigits: 0
      }).format(value);
    }
    if (type === 'percentage') {
      return `${value.toFixed(1)}%`;
    }
    return new Intl.NumberFormat('ru-RU').format(value);
  };

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${columns}, 1fr)`,
      gap: '16px',
      marginBottom: '24px'
    }}>
      {metrics.map((metric, index) => (
        <div
          key={index}
          style={{
            background: 'var(--bg-primary)',
            border: '1px solid var(--border-color)',
            borderRadius: '12px',
            padding: '20px',
            transition: 'all 0.2s ease',
            cursor: 'pointer'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-2px)';
            e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = 'none';
          }}
        >
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '12px'
          }}>
            <div style={{
              fontSize: '14px',
              color: 'var(--text-secondary)',
              fontWeight: '500'
            }}>
              {metric.label}
            </div>
            {metric.icon && (
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: `${getMetricColor(metric.type)}20`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: getMetricColor(metric.type)
              }}>
                {metric.icon}
              </div>
            )}
          </div>
          
          <div style={{
            fontSize: '24px',
            fontWeight: '700',
            color: 'var(--text-primary)',
            marginBottom: '4px'
          }}>
            {formatValue(metric.value, metric.format || 'number')}
          </div>
          
          {metric.change !== undefined && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '12px',
              color: metric.change >= 0 ? '#10b981' : '#ef4444'
            }}>
              <span>
                {metric.change >= 0 ? '↗' : '↘'} {Math.abs(metric.change).toFixed(1)}%
              </span>
              <span style={{ color: 'var(--text-secondary)' }}>
                vs предыдущий период
              </span>
            </div>
          )}
          
          {metric.description && (
            <div style={{
              fontSize: '12px',
              color: 'var(--text-secondary)',
              marginTop: '8px',
              lineHeight: '1.4'
            }}>
              {metric.description}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default AnalyticsMetrics;

