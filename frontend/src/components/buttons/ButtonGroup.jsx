import React from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import './ButtonGroup.css';

const ButtonGroup = ({
  children,
  size = 'medium',
  variant = 'primary',
  orientation = 'horizontal',
  spacing = 'none',
  className = '',
  ...props
}) => {
  const { theme, getColor } = useTheme();

  // Клонирование дочерних кнопок с передачей общих пропсов
  const cloneChildren = () => {
    return React.Children.map(children, (child, index) => {
      if (!React.isValidElement(child)) return child;

      const isFirst = index === 0;
      const isLast = index === React.Children.count(children) - 1;
      const isMiddle = !isFirst && !isLast;

      return React.cloneElement(child, {
        size: child.props.size || size,
        variant: child.props.variant || variant,
        className: `${child.props.className || ''} button-group-item ${
          isFirst ? 'first' : ''
        } ${isLast ? 'last' : ''} ${isMiddle ? 'middle' : ''}`.trim(),
        ...child.props
      });
    });
  };

  return (
    <div
      className={`button-group ${orientation} spacing-${spacing} ${className}`}
      role="group"
      style={{
        backgroundColor: spacing === 'none' ? getColor('cardBg') : 'transparent'
      }}
      {...props}
    >
      {cloneChildren()}
    </div>
  );
};

export default ButtonGroup;


