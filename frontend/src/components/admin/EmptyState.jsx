import React from 'react';
import { 
  FileText, 
  Users, 
  Calendar, 
  CreditCard, 
  Settings, 
  Shield,
  AlertCircle,
  Search,
  Plus,
  RefreshCw
} from 'lucide-react';
import { Card, Button } from '../ui/native';

const EmptyState = ({ 
  type = 'default',
  title = 'Нет данных',
  description = 'Здесь пока ничего нет',
  action,
  icon: CustomIcon,
  className = '',
  ...props 
}) => {
  const getIcon = () => {
    if (CustomIcon) return <CustomIcon className="w-12 h-12" />;
    
    const iconMap = {
      default: FileText,
      users: Users,
      appointments: Calendar,
      finance: CreditCard,
      settings: Settings,
      security: Shield,
      error: AlertCircle,
      search: Search,
      add: Plus,
      refresh: RefreshCw
    };
    
    const Icon = iconMap[type] || iconMap.default;
    return <Icon className="w-12 h-12" />;
  };

  const getColor = () => {
    const colorMap = {
      default: 'var(--text-tertiary)',
      error: 'var(--danger-color)',
      warning: 'var(--warning-color)',
      success: 'var(--success-color)',
      info: 'var(--info-color)'
    };
    
    return colorMap[type] || colorMap.default;
  };

  return (
    <Card 
      className={`p-8 text-center ${className}`}
      style={{
        background: 'var(--bg-primary)',
        border: '1px solid var(--border-color)'
      }}
      {...props}
    >
      <div className="flex flex-col items-center justify-center">
        <div 
          className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
          style={{ 
            background: `${getColor()}20`,
            color: getColor()
          }}
        >
          {getIcon()}
        </div>
        
        <h3 
          className="text-lg font-semibold mb-2"
          style={{ color: 'var(--text-primary)' }}
        >
          {title}
        </h3>
        
        <p 
          className="text-sm mb-6 max-w-md"
          style={{ color: 'var(--text-secondary)' }}
        >
          {description}
        </p>
        
        {action && (
          <div className="flex gap-3 justify-center">
            {action}
          </div>
        )}
      </div>
    </Card>
  );
};

export default EmptyState;

