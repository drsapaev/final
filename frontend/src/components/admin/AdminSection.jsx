import React from 'react';
import { Card } from '../ui/native';
import { useTheme } from '../../contexts/ThemeContext';

/**
 * Базовый компонент для разделов админ панели
 * Устраняет дублирование в render функциях AdminPanel
 */
const AdminSection = ({ 
  title, 
  description, 
  children, 
  actions = null,
  loading = false,
  error = null,
  className = "",
  ...props 
}) => {
  const { isDark } = useTheme();

  if (loading) {
    return (
      <div className="space-y-6">
        <Card className="p-6">
          <div className="animate-pulse">
            <div className="h-8 bg-gray-200 rounded w-1/4 mb-4"></div>
            <div className="h-4 bg-gray-200 rounded w-1/2 mb-6"></div>
            <div className="space-y-3">
              <div className="h-4 bg-gray-200 rounded"></div>
              <div className="h-4 bg-gray-200 rounded w-5/6"></div>
              <div className="h-4 bg-gray-200 rounded w-4/6"></div>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <Card className="p-6">
          <div className="text-center py-8">
            <div className="text-red-500 text-lg font-semibold mb-2">
              Ошибка загрузки данных
            </div>
            <div className="text-gray-600 mb-4">
              {error.message || 'Произошла неизвестная ошибка'}
            </div>
            <button 
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
            >
              Обновить страницу
            </button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className={`space-y-6 ${className}`} {...props}>
      <Card className="p-6">
        {/* Заголовок секции */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-2xl font-bold mb-2" style={{ 
              color: isDark ? '#f8fafc' : '#1e293b' 
            }}>
              {title}
            </h2>
            {description && (
              <p className="text-gray-600" style={{ 
                color: isDark ? '#94a3b8' : '#64748b' 
              }}>
                {description}
              </p>
            )}
          </div>
          
          {/* Действия в заголовке */}
          {actions && (
            <div className="flex gap-2">
              {actions}
            </div>
          )}
        </div>

        {/* Содержимое секции */}
        {children}
      </Card>
    </div>
  );
};

export default AdminSection;


