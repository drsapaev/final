/**
 * Улучшенная система компонентов с единым дизайном
 * Основана на принципах атомарного дизайна и медицинских стандартах UX
 */

import React from 'react';
import { cn } from '../../utils/cn';
import { 
  getColor, 
  getSpacing, 
  getFontSize, 
  getFontWeight, 
  getBorderRadius, 
  getShadow,
  getToken 
} from '../tokens/design-tokens';

// ===== ATOMS =====

/**
 * Улучшенная кнопка с медицинскими стандартами
 */
export const Button = React.forwardRef(({ 
  children, 
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  fullWidth = false,
  className = '',
  ...props 
}, ref) => {
  const baseClasses = 'inline-flex items-center justify-center font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';
  
  const variants = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
    secondary: 'bg-gray-200 text-gray-900 hover:bg-gray-300 focus:ring-gray-500',
    success: 'bg-green-600 text-white hover:bg-green-700 focus:ring-green-500',
    warning: 'bg-yellow-600 text-white hover:bg-yellow-700 focus:ring-yellow-500',
    danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500',
    outline: 'border-2 border-gray-300 text-gray-700 hover:bg-gray-50 focus:ring-gray-500',
    ghost: 'text-gray-700 hover:bg-gray-100 focus:ring-gray-500',
    medical: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500 shadow-lg'
  };
  
  const sizes = {
    xs: 'px-2 py-1 text-xs rounded',
    sm: 'px-3 py-2 text-sm rounded-md',
    md: 'px-4 py-2 text-sm rounded-md',
    lg: 'px-6 py-3 text-base rounded-lg',
    xl: 'px-8 py-4 text-lg rounded-lg'
  };
  
  return (
    <button
      ref={ref}
      className={cn(
        baseClasses,
        variants[variant],
        sizes[size],
        fullWidth && 'w-full',
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      )}
      {children}
    </button>
  );
});

Button.displayName = 'Button';

/**
 * Улучшенная карточка с медицинскими стандартами
 */
export const Card = React.forwardRef(({ 
  children, 
  variant = 'default',
  padding = 'md',
  shadow = 'md',
  className = '',
  ...props 
}, ref) => {
  const baseClasses = 'rounded-lg border bg-white text-gray-900';
  
  const variants = {
    default: 'border-gray-200',
    elevated: 'border-gray-200 shadow-lg',
    outlined: 'border-2 border-gray-300',
    ghost: 'border-transparent bg-transparent',
    medical: 'border-blue-200 bg-blue-50',
    success: 'border-green-200 bg-green-50',
    warning: 'border-yellow-200 bg-yellow-50',
    danger: 'border-red-200 bg-red-50'
  };
  
  const paddings = {
    none: '',
    sm: 'p-3',
    md: 'p-4',
    lg: 'p-6',
    xl: 'p-8'
  };
  
  const shadows = {
    none: '',
    sm: 'shadow-sm',
    md: 'shadow-md',
    lg: 'shadow-lg',
    xl: 'shadow-xl'
  };
  
  return (
    <div
      ref={ref}
      className={cn(
        baseClasses,
        variants[variant],
        paddings[padding],
        shadows[shadow],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
});

Card.displayName = 'Card';

/**
 * Улучшенный инпут с медицинскими стандартами
 */
export const Input = React.forwardRef(({ 
  type = 'text',
  variant = 'default',
  size = 'md',
  error = false,
  disabled = false,
  className = '',
  ...props 
}, ref) => {
  const baseClasses = 'w-full border rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1';
  
  const variants = {
    default: 'border-gray-300 focus:ring-blue-500 focus:border-blue-500',
    error: 'border-red-300 focus:ring-red-500 focus:border-red-500',
    success: 'border-green-300 focus:ring-green-500 focus:border-green-500'
  };
  
  const sizes = {
    sm: 'px-3 py-2 text-sm',
    md: 'px-4 py-2 text-base',
    lg: 'px-6 py-3 text-lg'
  };
  
  return (
    <input
      ref={ref}
      type={type}
      className={cn(
        baseClasses,
        variants[error ? 'error' : variant],
        sizes[size],
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
      disabled={disabled}
      {...props}
    />
  );
});

Input.displayName = 'Input';

/**
 * Улучшенный бейдж с медицинскими стандартами
 */
export const Badge = React.forwardRef(({ 
  children, 
  variant = 'default',
  size = 'md',
  className = '',
  ...props 
}, ref) => {
  const baseClasses = 'inline-flex items-center font-medium rounded-full';
  
  const variants = {
    default: 'bg-gray-100 text-gray-800',
    primary: 'bg-blue-100 text-blue-800',
    success: 'bg-green-100 text-green-800',
    warning: 'bg-yellow-100 text-yellow-800',
    danger: 'bg-red-100 text-red-800',
    medical: 'bg-blue-100 text-blue-800',
    pending: 'bg-purple-100 text-purple-800',
    completed: 'bg-green-100 text-green-800'
  };
  
  const sizes = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-2.5 py-0.5 text-xs',
    lg: 'px-3 py-1 text-sm'
  };
  
  return (
    <span
      ref={ref}
      className={cn(
        baseClasses,
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
});

Badge.displayName = 'Badge';

// ===== MOLECULES =====

/**
 * Улучшенная форма с медицинскими стандартами
 */
export const FormField = ({ 
  label, 
  error, 
  required = false,
  children,
  className = '',
  ...props 
}) => {
  return (
    <div className={cn('space-y-2', className)} {...props}>
      {label && (
        <label className="block text-sm font-medium text-gray-700">
          {label}
          {required && <span className="text-red-500 ml-1">*</span>}
        </label>
      )}
      {children}
      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}
    </div>
  );
};

/**
 * Улучшенная навигационная вкладка
 */
export const Tab = ({ 
  children, 
  active = false,
  disabled = false,
  onClick,
  className = '',
  ...props 
}) => {
  return (
    <button
      className={cn(
        'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
        active 
          ? 'border-blue-500 text-blue-600' 
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
      onClick={onClick}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
};

/**
 * Улучшенная группа вкладок
 */
export const Tabs = ({ 
  children, 
  value,
  onChange,
  className = '',
  ...props 
}) => {
  return (
    <div className={cn('border-b border-gray-200', className)} {...props}>
      <nav className="-mb-px flex space-x-8">
        {React.Children.map(children, (child, index) => {
          if (React.isValidElement(child)) {
            return React.cloneElement(child, {
              active: value === index,
              onClick: () => onChange?.(index)
            });
          }
          return child;
        })}
      </nav>
    </div>
  );
};

// ===== ORGANISMS =====

/**
 * Улучшенная таблица с медицинскими стандартами
 */
export const Table = ({ 
  children, 
  striped = false,
  hoverable = false,
  className = '',
  ...props 
}) => {
  return (
    <div className="overflow-x-auto">
      <table className={cn(
        'min-w-full divide-y divide-gray-200',
        striped && 'bg-white',
        className
      )} {...props}>
        {children}
      </table>
    </div>
  );
};

export const TableHeader = ({ children, className = '', ...props }) => (
  <thead className={cn('bg-gray-50', className)} {...props}>
    {children}
  </thead>
);

export const TableBody = ({ children, className = '', ...props }) => (
  <tbody className={cn('bg-white divide-y divide-gray-200', className)} {...props}>
    {children}
  </tbody>
);

export const TableRow = ({ 
  children, 
  hoverable = false,
  className = '',
  ...props 
}) => (
  <tr className={cn(
    hoverable && 'hover:bg-gray-50',
    className
  )} {...props}>
    {children}
  </tr>
);

export const TableCell = ({ 
  children, 
  header = false,
  className = '',
  ...props 
}) => {
  const Component = header ? 'th' : 'td';
  return (
    <Component className={cn(
      'px-6 py-4 whitespace-nowrap text-sm',
      header ? 'text-left font-medium text-gray-500 uppercase tracking-wider' : 'text-gray-900',
      className
    )} {...props}>
      {children}
    </Component>
  );
};

// ===== TEMPLATES =====

/**
 * Улучшенная страница с медицинскими стандартами
 */
export const Page = ({ 
  children, 
  title,
  subtitle,
  actions,
  className = '',
  ...props 
}) => {
  return (
    <div className={cn('min-h-screen bg-gray-50', className)} {...props}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {(title || subtitle || actions) && (
          <div className="mb-8">
            <div className="flex items-center justify-between">
              <div>
                {title && (
                  <h1 className="text-3xl font-bold text-gray-900">{title}</h1>
                )}
                {subtitle && (
                  <p className="mt-2 text-lg text-gray-600">{subtitle}</p>
                )}
              </div>
              {actions && (
                <div className="flex space-x-3">
                  {actions}
                </div>
              )}
            </div>
          </div>
        )}
        {children}
      </div>
    </div>
  );
};

/**
 * Улучшенная сетка с медицинскими стандартами
 */
export const Grid = ({ 
  children, 
  cols = 1,
  gap = 'md',
  className = '',
  ...props 
}) => {
  const gridCols = {
    1: 'grid-cols-1',
    2: 'grid-cols-2',
    3: 'grid-cols-3',
    4: 'grid-cols-4',
    6: 'grid-cols-6',
    12: 'grid-cols-12'
  };
  
  const gaps = {
    sm: 'gap-2',
    md: 'gap-4',
    lg: 'gap-6',
    xl: 'gap-8'
  };
  
  return (
    <div className={cn(
      'grid',
      gridCols[cols],
      gaps[gap],
      className
    )} {...props}>
      {children}
    </div>
  );
};

export default {
  Button,
  Card,
  Input,
  Badge,
  FormField,
  Tab,
  Tabs,
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableCell,
  Page,
  Grid
};
