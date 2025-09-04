import React from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { TrendingUp, TrendingDown } from 'lucide-react';

const KPICard = ({ 
  title, 
  value, 
  icon: Icon, 
  trend, 
  trendType = 'neutral',
  color = 'blue',
  loading = false,
  className = '',
  ...props 
}) => {
  const { theme, getColor, getSpacing, getFontSize } = useTheme();

  // Цветовые схемы для разных типов карточек
  const colorSchemes = {
    blue: {
      gradient: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 50%, #1e40af 100%)',
      iconColor: '#60a5fa',
      bgOverlay: theme === 'light' ? 'rgba(59, 130, 246, 0.1)' : 'rgba(59, 130, 246, 0.2)'
    },
    green: {
      gradient: 'linear-gradient(135deg, #22c55e 0%, #16a34a 50%, #15803d 100%)',
      iconColor: '#4ade80',
      bgOverlay: theme === 'light' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(34, 197, 94, 0.2)'
    },
    purple: {
      gradient: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 50%, #6d28d9 100%)',
      iconColor: '#a78bfa',
      bgOverlay: theme === 'light' ? 'rgba(139, 92, 246, 0.1)' : 'rgba(139, 92, 246, 0.2)'
    },
    orange: {
      gradient: 'linear-gradient(135deg, #f59e0b 0%, #d97706 50%, #b45309 100%)',
      iconColor: '#fbbf24',
      bgOverlay: theme === 'light' ? 'rgba(245, 158, 11, 0.1)' : 'rgba(245, 158, 11, 0.2)'
    },
    red: {
      gradient: 'linear-gradient(135deg, #ef4444 0%, #dc2626 50%, #b91c1c 100%)',
      iconColor: '#f87171',
      bgOverlay: theme === 'light' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(239, 68, 68, 0.2)'
    }
  };

  const scheme = colorSchemes[color] || colorSchemes.blue;

  const cardStyle = {
    position: 'relative',
    background: theme === 'light' 
      ? 'rgba(255, 255, 255, 0.9)' 
      : 'rgba(15, 23, 42, 0.9)',
    backdropFilter: 'blur(20px)',
    border: `1px solid ${theme === 'light' ? 'rgba(255, 255, 255, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderRadius: '20px',
    padding: getSpacing('lg'),
    boxShadow: theme === 'light' 
      ? '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
      : '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    cursor: 'pointer',
    overflow: 'hidden',
    minHeight: '140px',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between'
  };

  const cardHoverStyle = {
    transform: 'translateY(-4px) scale(1.02)',
    boxShadow: theme === 'light' 
      ? '0 25px 35px -5px rgba(0, 0, 0, 0.15), 0 15px 15px -5px rgba(0, 0, 0, 0.08)'
      : '0 25px 35px -5px rgba(0, 0, 0, 0.4), 0 15px 15px -5px rgba(0, 0, 0, 0.2)'
  };

  const gradientOverlayStyle = {
    position: 'absolute',
    top: 0,
    right: 0,
    width: '100px',
    height: '100px',
    background: scheme.gradient,
    borderRadius: '50%',
    transform: 'translate(30px, -30px)',
    opacity: 0.1,
    pointerEvents: 'none'
  };

  const contentStyle = {
    position: 'relative',
    zIndex: 1,
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    flex: 1,
    gap: getSpacing('md')
  };

  const textContainerStyle = {
    flex: 1
  };

  const titleStyle = {
    fontSize: getFontSize('sm'),
    fontWeight: '500',
    color: 'var(--text-secondary)',
    marginBottom: getSpacing('xs'),
    lineHeight: 1.4
  };

  const valueStyle = {
    fontSize: getFontSize('2xl'),
    fontWeight: '700',
    color: 'var(--text-primary)',
    lineHeight: 1.2,
    marginBottom: trend ? getSpacing('xs') : 0,
    wordBreak: 'break-word'
  };

  const trendStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('xs'),
    fontSize: getFontSize('xs'),
    fontWeight: '500',
    color: trendType === 'positive' ? 'var(--success-color)' : 
           trendType === 'negative' ? 'var(--danger-color)' : 
           'var(--text-tertiary)'
  };

  const iconContainerStyle = {
    width: '48px',
    height: '48px',
    borderRadius: '12px',
    background: scheme.bgOverlay,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0
  };

  const skeletonStyle = {
    ...cardStyle,
    background: theme === 'light' 
      ? 'linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%)'
      : 'linear-gradient(90deg, #1e293b 25%, #334155 50%, #1e293b 75%)',
    backgroundSize: '200% 100%',
    animation: 'skeleton-loading 1.5s infinite'
  };

  if (loading) {
    return (
      <div style={skeletonStyle} className={className} {...props}>
        <div style={contentStyle}>
          <div style={textContainerStyle}>
            <div style={{ ...titleStyle, background: 'var(--bg-tertiary)', borderRadius: '4px', height: '16px', width: '80%', marginBottom: getSpacing('sm') }} />
            <div style={{ ...valueStyle, background: 'var(--bg-tertiary)', borderRadius: '4px', height: '32px', width: '60%' }} />
          </div>
          <div style={{ ...iconContainerStyle, background: 'var(--bg-tertiary)' }} />
        </div>
      </div>
    );
  }

  return (
    <div
      style={cardStyle}
      className={`kpi-card ${className}`}
      onMouseEnter={(e) => Object.assign(e.currentTarget.style, cardHoverStyle)}
      onMouseLeave={(e) => Object.assign(e.currentTarget.style, cardStyle)}
      {...props}
    >
      {/* Градиентный оверлей */}
      <div style={gradientOverlayStyle} />
      
      {/* Основной контент */}
      <div style={contentStyle}>
        <div style={textContainerStyle}>
          <p style={titleStyle}>{title}</p>
          <p style={valueStyle}>{typeof value === 'number' ? value.toLocaleString('ru-RU') : value}</p>
          {trend && (
            <div style={trendStyle}>
              {trendType === 'positive' && <TrendingUp size={12} />}
              {trendType === 'negative' && <TrendingDown size={12} />}
              <span>{trend}</span>
            </div>
          )}
        </div>
        
        {Icon && (
          <div style={iconContainerStyle}>
            <Icon size={28} style={{ color: scheme.iconColor }} />
          </div>
        )}
      </div>
    </div>
  );
};

export default KPICard;
