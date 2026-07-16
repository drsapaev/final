import { TrendingUp, TrendingDown } from 'lucide-react';
import MedicalCard from './MedicalCard';
import Icon from '../Icon';
import { useTheme } from '../../contexts/ThemeContext';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';

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

  // PR-63: replaced hardcoded hex colors with CSS custom properties
  const colorClasses = {
    blue: {
      bg: isDark ? 'var(--mac-accent-blue-active)' : 'var(--mac-accent-bg)',
      text: isDark ? 'var(--mac-accent-blue-light, color-mix(in srgb, var(--mac-accent-blue), white 60%))' : 'var(--mac-accent-blue-hover)',
      icon: isDark ? 'var(--mac-accent-blue-light, color-mix(in srgb, var(--mac-accent-blue), white 40%))' : 'var(--mac-accent-blue)'
    },
    green: {
      bg: isDark ? 'var(--mac-success-bg, color-mix(in srgb, var(--mac-success), transparent 80%))' : 'var(--mac-success-bg)',
      text: isDark ? 'var(--mac-success-light, color-mix(in srgb, var(--mac-success), white 40%))' : 'var(--mac-success)',
      icon: isDark ? 'var(--mac-success-light, color-mix(in srgb, var(--mac-success), white 20%))' : 'var(--mac-success)'
    },
    purple: {
      bg: isDark ? 'var(--mac-accent-purple-bg, color-mix(in srgb, var(--mac-accent-purple), transparent 80%))' : 'var(--mac-accent-purple-bg, color-mix(in srgb, var(--mac-accent-purple), transparent 90%))',
      text: isDark ? 'var(--mac-accent-purple-light, color-mix(in srgb, var(--mac-accent-purple), white 40%))' : 'var(--mac-accent-purple)',
      icon: isDark ? 'var(--mac-accent-purple-light, color-mix(in srgb, var(--mac-accent-purple), white 20%))' : 'var(--mac-accent-purple)'
    },
    orange: {
      bg: isDark ? 'var(--mac-warning-bg, color-mix(in srgb, var(--mac-warning), transparent 80%))' : 'var(--mac-error-border, color-mix(in srgb, var(--mac-warning), transparent 50%))',
      text: isDark ? 'var(--mac-warning-light, color-mix(in srgb, var(--mac-warning), white 40%))' : 'var(--mac-warning)',
      icon: isDark ? 'var(--mac-warning-light, color-mix(in srgb, var(--mac-warning), white 20%))' : 'var(--mac-warning)'
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

