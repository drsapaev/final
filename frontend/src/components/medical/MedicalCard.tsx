import type { ReactNode, CSSProperties } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { useTranslation } from '../../i18n/useTranslation';

type PaddingSize = 'small' | 'medium' | 'large';
type ShadowSize = 'none' | 'small' | 'medium' | 'large';

interface MedicalCardProps {
  children?: ReactNode;
  className?: string;
  hover?: boolean;
  padding?: PaddingSize;
  shadow?: ShadowSize;
  style?: CSSProperties;
  [key: string]: unknown;
}

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
}: MedicalCardProps) => {
  const { isDark } = useTheme();

  const paddingClasses: Record<PaddingSize, string> = {
    small: 'p-3',
    medium: 'p-6',
    large: 'p-8'
  };

  const shadowClasses: Record<ShadowSize, string> = {
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
        boxShadow: isDark ?
        '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)' :
        'var(--mac-shadow-md)',
        ...(props.style as CSSProperties)
      }}
      {...props}>

      {children}
    </div>);

};

export default MedicalCard;
