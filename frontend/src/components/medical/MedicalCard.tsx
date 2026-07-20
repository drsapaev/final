
import { useTheme } from '../../contexts/ThemeContext';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';

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
  const { isDark } = useTheme();

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
        backgroundColor: isDark ? 'var(--mac-text-primary)' : 'var(--mac-bg-primary)',
        borderColor: isDark ? 'var(--mac-text-primary)' : 'var(--mac-border)',
        backdropFilter: 'blur(10px)',
        boxShadow: isDark ?
        '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)' :
        'var(--mac-shadow-md)',
        ...props.style
      }}
      {...props}>
      
      {children}
    </div>);

};


MedicalCard.propTypes = {
  ...(MedicalCard.propTypes || {}),
  children: PropTypes.any,
  className: PropTypes.any,
  hover: PropTypes.any,
  padding: PropTypes.any,
  shadow: PropTypes.any,
  style: PropTypes.any,
};

export default MedicalCard;