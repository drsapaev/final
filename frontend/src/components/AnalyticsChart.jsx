import React from 'react';

// Простой компонент для отображения графиков без внешних библиотек
function AnalyticsChart({ 
  title, 
  data, 
  type = 'bar', 
  height = 200, 
  color = '#3b82f6',
  showValues = true 
}) {
  const maxValue = Math.max(...data.map(item => item.value || 0));
  
  const renderBarChart = () => (
    <div style={{ 
      display: 'flex', 
      alignItems: 'end', 
      height: height, 
      gap: '4px',
      padding: '16px',
      background: 'var(--bg-primary)',
      borderRadius: '8px',
      border: '1px solid var(--border-color)'
    }}>
      {data.map((item, index) => {
        const heightPercent = maxValue > 0 ? (item.value / maxValue) * 100 : 0;
        return (
          <div key={index} style={{ 
            display: 'flex', 
            flexDirection: 'column', 
            alignItems: 'center',
            flex: 1,
            minWidth: '40px'
          }}>
            <div style={{
              width: '100%',
              height: `${heightPercent}%`,
              minHeight: '4px',
              background: color,
              borderRadius: '4px 4px 0 0',
              transition: 'all 0.3s ease',
              position: 'relative'
            }}>
              {showValues && item.value > 0 && (
                <div style={{
                  position: 'absolute',
                  top: '-20px',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  fontSize: '12px',
                  fontWeight: '600',
                  color: 'var(--text-primary)',
                  background: 'var(--bg-primary)',
                  padding: '2px 4px',
                  borderRadius: '4px',
                  border: '1px solid var(--border-color)'
                }}>
                  {item.value}
                </div>
              )}
            </div>
            <div style={{
              fontSize: '12px',
              color: 'var(--text-secondary)',
              marginTop: '8px',
              textAlign: 'center',
              wordBreak: 'break-word'
            }}>
              {item.label}
            </div>
          </div>
        );
      })}
    </div>
  );
  
  const renderLineChart = () => (
    <div style={{ 
      height: height, 
      padding: '16px',
      background: 'var(--bg-primary)',
      borderRadius: '8px',
      border: '1px solid var(--border-color)',
      position: 'relative'
    }}>
      <svg width="100%" height="100%" style={{ position: 'absolute', top: 0, left: 0 }}>
        {data.map((item, index) => {
          if (index === 0) return null;
          const prevItem = data[index - 1];
          const x1 = (index - 1) * (100 / (data.length - 1));
          const y1 = 100 - (prevItem.value / maxValue) * 100;
          const x2 = index * (100 / (data.length - 1));
          const y2 = 100 - (item.value / maxValue) * 100;
          
          return (
            <line
              key={index}
              x1={`${x1}%`}
              y1={`${y1}%`}
              x2={`${x2}%`}
              y2={`${y2}%`}
              stroke={color}
              strokeWidth="2"
              fill="none"
            />
          );
        })}
        {data.map((item, index) => {
          const x = index * (100 / (data.length - 1));
          const y = 100 - (item.value / maxValue) * 100;
          
          return (
            <circle
              key={index}
              cx={`${x}%`}
              cy={`${y}%`}
              r="4"
              fill={color}
            />
          );
        })}
      </svg>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between',
        position: 'absolute',
        bottom: '0',
        left: '16px',
        right: '16px'
      }}>
        {data.map((item, index) => (
          <div key={index} style={{
            fontSize: '12px',
            color: 'var(--text-secondary)',
            textAlign: 'center'
          }}>
            {item.label}
          </div>
        ))}
      </div>
    </div>
  );
  
  const renderPieChart = () => {
    const total = data.reduce((sum, item) => sum + item.value, 0);
    let currentAngle = 0;
    
    return (
      <div style={{ 
        height: height, 
        padding: '16px',
        background: 'var(--bg-primary)',
        borderRadius: '8px',
        border: '1px solid var(--border-color)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <svg width="120" height="120" style={{ transform: 'rotate(-90deg)' }}>
          {data.map((item, index) => {
            const percentage = (item.value / total) * 100;
            const angle = (percentage / 100) * 360;
            const radius = 50;
            const circumference = 2 * Math.PI * radius;
            const strokeDasharray = circumference;
            const strokeDashoffset = circumference - (percentage / 100) * circumference;
            
            const segment = (
              <circle
                key={index}
                cx="60"
                cy="60"
                r={radius}
                fill="none"
                stroke={`hsl(${index * 60}, 70%, 50%)`}
                strokeWidth="20"
                strokeDasharray={strokeDasharray}
                strokeDashoffset={strokeDashoffset}
                style={{
                  transition: 'stroke-dashoffset 0.3s ease'
                }}
              />
            );
            
            currentAngle += angle;
            return segment;
          })}
        </svg>
        <div style={{ 
          position: 'absolute',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '4px'
        }}>
          {data.map((item, index) => (
            <div key={index} style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px'
            }}>
              <div style={{
                width: '12px',
                height: '12px',
                borderRadius: '2px',
                background: `hsl(${index * 60}, 70%, 50%)`
              }} />
              <span style={{ color: 'var(--text-primary)' }}>
                {item.label}: {item.value}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  };
  
  return (
    <div style={{ marginBottom: '24px' }}>
      <h3 style={{ 
        margin: '0 0 16px 0', 
        fontSize: '16px', 
        fontWeight: '600',
        color: 'var(--text-primary)'
      }}>
        {title}
      </h3>
      {type === 'bar' && renderBarChart()}
      {type === 'line' && renderLineChart()}
      {type === 'pie' && renderPieChart()}
    </div>
  );
}

export default AnalyticsChart;

