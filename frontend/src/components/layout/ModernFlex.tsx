import type { CSSProperties, ReactNode } from 'react';

import { useTheme } from '../../contexts/ThemeContext';
import './ModernFlex.css';
import { useTranslation } from '../../i18n/useTranslation';

const ModernFlex = ({
  children,
  direction = 'row',
  wrap = 'nowrap',
  justify = 'flex-start',
  align = 'stretch',
  gap = 'medium',
  responsive = true,
  className = '',
  ...props
}: {
  children?: ReactNode;
  direction?: string;
  wrap?: string;
  justify?: string;
  align?: string;
  gap?: string | number;
  responsive?: boolean;
  className?: string;
  [key: string]: unknown;
}) => {
  useTheme();

  const gapValues = {
    none: '0',
    small: '8px',
    medium: '16px',
    large: '24px',
    xl: '32px'
  };

  const flexStyles = {
    display: 'flex',
    flexDirection: direction,
    flexWrap: wrap,
    justifyContent: justify,
    alignItems: align,
    gap: (gapValues as Record<string, string>)[gap as string] || gap as string
  };

  return (
    <div
      className={`modern-flex ${responsive ? 'responsive' : ''} ${className}`}
      style={flexStyles as CSSProperties}
      {...props}>
      
      {children}
    </div>);

};

// Компонент элемента flex
export const FlexItem = ({
  children,
  flex = 'auto',
  alignSelf = 'auto',
  order = 'auto',
  className = '',
  ...props
}: {
  children?: ReactNode;
  flex?: string | number;
  alignSelf?: string;
  order?: string | number;
  className?: string;
  [key: string]: unknown;
}) => {
  const itemStyles = {
    flex,
    alignSelf,
    order: order !== 'auto' ? order : undefined
  };

  return (
    <div
      className={`flex-item ${className}`}
      style={itemStyles as CSSProperties}
      {...props}>
      
      {children}
    </div>);

};



export default ModernFlex;
