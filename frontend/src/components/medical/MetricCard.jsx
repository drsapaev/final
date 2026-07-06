import { TrendingUp, TrendingDown } from 'lucide-react';
import MedicalCard from './MedicalCard';
import Icon from '../Icon';
import { useTheme } from '../../contexts/ThemeContext';
import PropTypes from 'prop-types';

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
      bg: isDark ? 'var(--mac-accent-blue-active)' : 'var(--mac-accent-bg)',
      text: isDark ? 'var(--mac-accent-blue-light, color-mix(in srgb, var(--mac-accent-blue), white 60%))' : 'var(--mac-accent-blue-hover)',
      icon: isDark ? '#60a5fa' : 'var(--mac-accent-blue)'
    },
    green: {
      bg: isDark ? '#14532d' : 'var(--mac-success-bg)',
      text: isDark ? '#86efac' : 'var(--mac-success)',
      icon: isDark ? '#4ade80' : 'var(--mac-success)'
    },
    purple: {
      bg: isDark ? '#581c87' : '#f3e8ff',
      text: isDark ? '#c084fc' : '#9333ea',
      icon: isDark ? '#a855f7' : 'var(--mac-accent-purple)'
    },
    orange: {
      bg: isDark ? '#9a3412' : 'var(--mac-error-border, color-mix(in srgb, var(--mac-warning), transparent 50%))',
      text: isDark ? '#fdba74' : 'var(--mac-warning)',
      icon: isDark ? '#fb923c' : '#f97316'
    },
    red: {
      bg: isDark ? 'var(--mac-error)' : 'var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))',
      text: isDark ? 'var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))' : 'var(--mac-error)',
      icon: isDark ? 'var(--mac-error)' : 'var(--mac-error)'
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
            style={{ color: isDark ? 'var(--mac-text-tertiary)' : 'var(--mac-text-secondary)' }}
          >
            {title}
          </p>
          <p 
            className={`font-bold ${compact ? 'text-lg' : 'text-2xl'}`}
            style={{ color: isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-text-primary)' }}
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


MetricCard.propTypes = {
  ...(MetricCard.propTypes || {}),
  change: PropTypes.any,
  className: PropTypes.any,
  color: PropTypes.any,
  compact: PropTypes.any,
  iconName: PropTypes.any,
  title: PropTypes.any,
  value: PropTypes.any,
};

export default MetricCard;

