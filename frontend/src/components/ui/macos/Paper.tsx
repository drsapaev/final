import React, { type ReactNode, type CSSProperties } from 'react';
import { useTheme } from '../../../contexts/ThemeContext';
import PropTypes from 'prop-types';

type PaperVariant = 'elevation' | 'outlined' | 'filled';
type PaperElevation = 0 | 1 | 2 | 3 | 4 | 5;

interface PaperProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'children' | 'style'> {
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
  elevation?: PaperElevation;
  variant?: PaperVariant;
  square?: boolean;
}

interface ElevationStyle extends CSSProperties {
  boxShadow?: string;
}

/**
 * macOS-style Paper Component
 * Implements Apple's Human Interface Guidelines for paper surfaces
 */
const Paper = React.forwardRef<HTMLDivElement, PaperProps>(({
  children,
  className = '',
  style = {},
  elevation = 1,
  variant = 'elevation',
  square = false,
  ...props
}, ref) => {
  useTheme();

  const getElevationStyles = (e: PaperElevation): ElevationStyle => {
    const elevations: Record<PaperElevation, ElevationStyle> = {
      0: {
        boxShadow: 'none',
        border: '1px solid var(--mac-border)'
      },
      1: {
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.06)',
        border: '1px solid var(--mac-border)'
      },
      2: {
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06)',
        border: '1px solid var(--mac-border)'
      },
      3: {
        boxShadow: '0 10px 15px rgba(0, 0, 0, 0.1), 0 4px 6px rgba(0, 0, 0, 0.05)',
        border: '1px solid var(--mac-border)'
      },
      4: {
        boxShadow: '0 20px 25px rgba(0, 0, 0, 0.1), 0 10px 10px rgba(0, 0, 0, 0.04)',
        border: '1px solid var(--mac-border)'
      },
      5: {
        boxShadow: '0 25px 50px rgba(0, 0, 0, 0.15), 0 10px 10px rgba(0, 0, 0, 0.04)',
        border: '1px solid var(--mac-border)'
      }
    };

    return elevations[e] || elevations[1];
  };

  const paperStyles: CSSProperties = {
    backgroundColor: 'var(--mac-bg-primary)',
    borderRadius: square ? '0' : '8px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    ...getElevationStyles(elevation),
    ...style
  };

  return (
    <div
      ref={ref}
      className={`mac-paper mac-paper--${variant} mac-paper--elevation-${elevation} ${square ? 'mac-paper--square' : ''} ${className}`}
      style={paperStyles}
      {...props}>

      {children}
    </div>);

});


Paper.propTypes = {
  ...(Paper.propTypes || {}),
  children: PropTypes.any,
  className: PropTypes.any,
  elevation: PropTypes.any,
  square: PropTypes.any,
  style: PropTypes.any,
  variant: PropTypes.any,
};

Paper.displayName = 'Paper';

export default Paper;
