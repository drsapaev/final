import React from 'react';
import { useTheme } from '../../contexts/ThemeContext';

/**
 * Базовая медицинская карточка в стиле MediLab
 */
const MedicalCard = ({ 
  children, 
  className = '', 
  hover = true, 
  padding = 'medium',
  shadow = 'medium',
  ...props 
}) => {
  const { isDark, getColor } = useTheme();

  const paddingClasses = {
    small: 'p-3',
    medium: 'p-6',
    large: 'p-8'
  };

  const shadowClasses = {
    none: '',
    small: 'shadow-sm',
    medium: 'shadow-md',
    large: 'shadow-lg'
  };

  const baseClasses = `
    bg-white rounded-2xl border border-gray-200 transition-all duration-300 ease-out
    ${hover ? 'hover:shadow-xl hover:-translate-y-2 hover:scale-[1.02] medical-card-hover card-wave' : ''}
    ${paddingClasses[padding]}
    ${shadowClasses[shadow]}
    ${className}
  `;

  const darkClasses = isDark ? 'bg-gray-800 border-gray-700' : '';

  return (
    <div 
      className={`${baseClasses} ${darkClasses}`}
      style={{
        backgroundColor: isDark ? '#1e293b' : '#ffffff',
        borderColor: isDark ? '#334155' : '#e2e8f0',
        backdropFilter: 'blur(10px)',
        boxShadow: isDark 
          ? '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)'
          : '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        ...props.style
      }}
      {...props}
    >
      {children}
    </div>
  );
};

export default MedicalCard;

