import React, { type CSSProperties, type ReactNode } from 'react';
import PropTypes from 'prop-types';

interface TypographyProps {
  children?: ReactNode;
  variant?: string;
  color?: string;
  gutterBottom?: boolean;
  style?: CSSProperties;
  paragraph?: boolean;
  component?: string | React.ComponentType<any>;
  className?: string;
  fontWeight?: number | string;
  align?: string;
  display?: string;
  sx?: Record<string, unknown>;
}
// Minimal macOS-style Typography supporting common MUI variants
const variantMap = {
  h1: { fontSize: '28px', fontWeight: 700 },
  h2: { fontSize: '22px', fontWeight: 700 },
  h3: { fontSize: '17px', fontWeight: 600 },
  h4: { fontSize: '17px', fontWeight: 600 },
  h5: { fontSize: '15px', fontWeight: 600 },
  h6: { fontSize: '15px', fontWeight: 600 },
  body1: { fontSize: '15px', fontWeight: 400 },
  body2: { fontSize: '13px', fontWeight: 400 },
  subtitle1: { fontSize: '15px', fontWeight: 500 },
  subtitle2: { fontSize: '13px', fontWeight: 500 },
  caption: { fontSize: '11px', fontWeight: 400 }
};

const colorMap = {
  primary: 'var(--mac-text-primary)',
  secondary: 'var(--mac-text-secondary)',
  textSecondary: 'var(--mac-text-secondary)',
  success: 'var(--mac-success)',
  warning: 'var(--mac-warning)',
  danger: 'var(--mac-danger)'
};

const Typography = ({
  children,
  variant = 'body1',
  color,
  gutterBottom = false,
  style = {},
  paragraph,
  component,
  ...props
}: TypographyProps) => {
  const styles = {
    margin: 0,
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    color: color ? (colorMap[color] || color) : 'var(--mac-text-primary)',
    ...(variantMap[variant] || variantMap.body1),
    ...(gutterBottom ? { marginBottom: '8px' } : {}),
    ...(paragraph ? { marginBottom: '16px' } : {}),
    ...style
  };
  const Tag = component || (variant.startsWith('h') ? 'h' + variant.replace('h', '') : 'p');
  return <Tag style={styles} {...props}>{children}</Tag>;
};


Typography.propTypes = {
  ...(Typography.propTypes || {}),
  children: PropTypes.any,
  color: PropTypes.any,
  component: PropTypes.elementType,
  gutterBottom: PropTypes.any,
  paragraph: PropTypes.any,
  style: PropTypes.any,
  variant: PropTypes.any,
};

export default Typography;


