import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import MedicalCard from './MedicalCard';
import Icon from '../Icon';
import { useTheme } from '../../contexts/ThemeContext';

/**
 * Карточка метрики для дашборда в стиле MediLab
 */
const MetricCard = ({ 
  title,
  value,
  change,
  iconName,
  color = 'blue',
  className = '',
  compact = false,
  ...props 
}) => {
  const { isDark } = useTheme();

  const colorClasses = {
    blue: {
      bg: isDark ? '#1e3a8a' : '#dbeafe',
      text: isDark ? '#93c5fd' : '#1d4ed8',
      icon: isDark ? '#60a5fa' : '#3b82f6'
    },
    green: {
      bg: isDark ? '#14532d' : '#dcfce7',
      text: isDark ? '#86efac' : '#16a34a',
      icon: isDark ? '#4ade80' : '#22c55e'
    },
    purple: {
      bg: isDark ? '#581c87' : '#f3e8ff',
      text: isDark ? '#c084fc' : '#9333ea',
      icon: isDark ? '#a855f7' : '#8b5cf6'
    },
    orange: {
      bg: isDark ? '#9a3412' : '#fed7aa',
      text: isDark ? '#fdba74' : '#ea580c',
      icon: isDark ? '#fb923c' : '#f97316'
    },
    red: {
      bg: isDark ? '#7f1d1d' : '#fecaca',
      text: isDark ? '#fca5a5' : '#dc2626',
      icon: isDark ? '#f87171' : '#ef4444'
    }
  };

  const colors = colorClasses[color] || colorClasses.blue;

  return (
    <MedicalCard 
      className={`metric-card interactive-element hover-lift ripple-effect magnetic-hover focus-ring ${className}`}
      hover={true}
      padding={compact ? 'small' : 'medium'}
      {...props}
    >
      <div className={`flex items-center ${compact ? 'justify-between' : 'justify-between'}`}>
        <div className="flex-1">
          <p 
            className={`font-medium mb-1 ${compact ? 'text-xs' : 'text-sm'}`}
            style={{ color: isDark ? '#94a3b8' : '#64748b' }}
          >
            {title}
          </p>
          <p 
            className={`font-bold ${compact ? 'text-lg' : 'text-2xl'}`}
            style={{ color: isDark ? '#f8fafc' : '#1e293b' }}
          >
            {value}
          </p>
          {change !== undefined && (
            <div 
              className={`flex items-center ${compact ? 'mt-0.5' : 'mt-1'} ${
                change > 0 ? 'text-green-600' : 'text-red-600'
              }`}
            >
              {change > 0 ? (
                <TrendingUp className={`mr-1 ${compact ? 'h-3 w-3' : 'h-4 w-4'}`} />
              ) : (
                <TrendingDown className={`mr-1 ${compact ? 'h-3 w-3' : 'h-4 w-4'}`} />
              )}
              <span className={`font-medium ${compact ? 'text-xs' : 'text-sm'}`}>
                {Math.abs(change)}%
              </span>
            </div>
          )}
        </div>
        
        {Icon && (
          <div 
            className={`rounded-lg flex items-center justify-center ${compact ? 'w-8 h-8' : 'w-12 h-12'}`}
            style={{
              backgroundColor: colors.bg,
              color: colors.icon
            }}
          >
            <Icon name={iconName} size={compact ? 16 : 24} />
          </div>
        )}
      </div>
    </MedicalCard>
  );
};

export default MetricCard;

