import type { CSSProperties, ReactNode } from 'react';

import { useTheme } from '../../contexts/ThemeContext';
import './ModernGrid.css';
import { useTranslation } from '../../i18n/useTranslation';

const ModernGrid = ({
  children,
  columns = 'auto',
  gap = 'medium',
  alignItems = 'stretch',
  justifyContent = 'start',
  responsive = true,
  minColumnWidth = '250px',
  className = '',
  ...props
}: {
  children?: ReactNode;
  columns?: number | string;
  gap?: string | number;
  alignItems?: string;
  justifyContent?: string;
  responsive?: boolean;
  minColumnWidth?: string;
  className?: string;
  [key: string]: unknown;
}) => {
  useTheme();

  const getGridColumns = () => {
    if (typeof columns === 'number') {
      return `repeat(${columns}, 1fr)`;
    }
    if (columns === 'auto') {
      return `repeat(auto-fit, minmax(${minColumnWidth}, 1fr))`;
    }
    return columns;
  };

  const gapValues = {
    none: '0',
    small: '8px',
    medium: '16px',
    large: '24px',
    xl: '32px'
  };

  const gridStyles: CSSProperties = {
    display: 'grid',
    gridTemplateColumns: getGridColumns(),
    gap: (gapValues as Record<string, string>)[gap as string] || gap,
    alignItems,
    justifyContent
  };

  return (
    <div
      className={`modern-grid ${responsive ? 'responsive' : ''} ${className}`}
      style={gridStyles}
      {...props}>
      
      {children}
    </div>);

};

// Компонент элемента сетки
export const GridItem = ({
  children,
  colSpan = 1,
  rowSpan = 1,
  alignSelf = 'auto',
  justifySelf = 'auto',
  className = '',
  ...props
}: {
  children?: ReactNode;
  colSpan?: number;
  rowSpan?: number;
  alignSelf?: string;
  justifySelf?: string;
  className?: string;
  [key: string]: unknown;
}) => {
  const itemStyles = {
    gridColumn: colSpan > 1 ? `span ${colSpan}` : 'auto',
    gridRow: rowSpan > 1 ? `span ${rowSpan}` : 'auto',
    alignSelf,
    justifySelf
  };

  return (
    <div
      className={`grid-item ${className}`}
      style={itemStyles}
      {...props}>
      
      {children}
    </div>);

};



export default ModernGrid;
