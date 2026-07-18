import type { CSSProperties, ReactNode } from 'react';

import { useTheme } from '../../contexts/ThemeContext';
import './ModernContainer.css';
import PropTypes from 'prop-types';

type MaxWidth = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'full';
type PaddingSize = 'none' | 'small' | 'medium' | 'large' | 'xl';

interface ModernContainerProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'children' | 'style'> {
  children?: ReactNode;
  maxWidth?: MaxWidth;
  padding?: PaddingSize;
  margin?: string;
  fluid?: boolean;
  centered?: boolean;
  className?: string;
  style?: CSSProperties;
}

const maxWidthValues: Record<string, string> = {
  xs: '480px',
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px',
  full: '100%'
};

const paddingValues: Record<string, string> = {
  none: '0',
  small: '12px',
  medium: '20px',
  large: '32px',
  xl: '48px'
};

const ModernContainer = ({
  children,
  maxWidth = 'xl',
  padding = 'medium',
  margin = 'auto',
  fluid = false,
  centered = false,
  className = '',
  ...props
}: ModernContainerProps) => {
  useTheme();

  const containerStyles: CSSProperties = {
    maxWidth: fluid ? '100%' : (maxWidthValues[maxWidth] || maxWidthValues.xl),
    padding: paddingValues[padding] || paddingValues.medium,
    margin: margin === 'auto' ? '0 auto' : margin,
    ...(centered && {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center'
    })
  };

  return (
    <div
      className={`modern-container ${fluid ? 'fluid' : ''} ${centered ? 'centered' : ''} ${className}`}
      style={containerStyles}
      {...props}>
      
      {children}
    </div>);

};


ModernContainer.propTypes = {
  ...(ModernContainer.propTypes || {}),
  centered: PropTypes.any,
  children: PropTypes.any,
  className: PropTypes.any,
  fluid: PropTypes.any,
  margin: PropTypes.any,
  maxWidth: PropTypes.any,
  padding: PropTypes.any,
};

export default ModernContainer;
