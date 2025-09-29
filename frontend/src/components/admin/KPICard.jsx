import React from 'react';
import { Card, useFade, useScale } from '../ui/native';

const KPICard = ({ 
  title, 
  value, 
  icon: Icon, 
  color = 'blue', 
  trend, 
  trendType = 'neutral',
  loading = false,
  className = '',
  ...props 
}) => {
  const { isVisible: fadeIn, fadeIn: startFadeIn } = useFade(false);
  const { isVisible: scaleIn, scaleIn: startScaleIn } = useScale(false);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      startFadeIn(200);
      startScaleIn(300);
    }, 100);
    return () => clearTimeout(timer);
  }, [startFadeIn, startScaleIn]);

  const colorClasses = {
    blue: {
      bg: 'bg-blue-50',
      icon: 'text-blue-500',
      text: 'text-blue-600',
      value: 'text-blue-900'
    },
    green: {
      bg: 'bg-green-50',
      icon: 'text-green-500',
      text: 'text-green-600',
      value: 'text-green-900'
    },
    purple: {
      bg: 'bg-purple-50',
      icon: 'text-purple-500',
      text: 'text-purple-600',
      value: 'text-purple-900'
    },
    orange: {
      bg: 'bg-orange-50',
      icon: 'text-orange-500',
      text: 'text-orange-600',
      value: 'text-orange-900'
    },
    red: {
      bg: 'bg-red-50',
      icon: 'text-red-500',
      text: 'text-red-600',
      value: 'text-red-900'
    }
  };

  const trendColors = {
    positive: 'text-green-600',
    negative: 'text-red-600',
    neutral: 'text-gray-600'
  };

  const colors = colorClasses[color] || colorClasses.blue;

  if (loading) {
    return (
      <Card className={`p-4 ${className}`} {...props}>
        <div className="animate-pulse">
          <div className="flex items-center justify-between mb-2">
            <div className="h-4 bg-gray-200 rounded w-24"></div>
            <div className="w-8 h-8 bg-gray-200 rounded"></div>
          </div>
          <div className="h-8 bg-gray-200 rounded w-16 mb-1"></div>
          <div className="h-3 bg-gray-200 rounded w-12"></div>
        </div>
      </Card>
    );
  }

  return (
    <Card 
      className={`p-4 transition-all duration-300 hover:shadow-lg ${colors.bg} ${className}`}
      style={{
        opacity: fadeIn ? 1 : 0,
        transform: scaleIn ? 'scale(1)' : 'scale(0.95)'
      }}
      {...props}
    >
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className={`text-sm font-medium ${colors.text} mb-1`}>
            {title}
          </p>
          <p className={`text-2xl font-bold ${colors.value} mb-1`}>
            {typeof value === 'number' ? value.toLocaleString() : value}
          </p>
          {trend && (
            <p className={`text-xs ${trendColors[trendType] || trendColors.neutral}`}>
              {trend}
            </p>
          )}
        </div>
        {Icon && (
          <div className={`w-8 h-8 ${colors.icon} flex items-center justify-center`}>
            <Icon className="w-6 h-6" />
          </div>
        )}
      </div>
    </Card>
  );
};

export default KPICard;

