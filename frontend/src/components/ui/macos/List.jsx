import React from 'react';
import { useTheme } from '../../../contexts/ThemeContext';

/**
 * macOS-style List Component
 * Implements Apple's Human Interface Guidelines for lists
 */
const List = React.forwardRef(({
  children,
  className = '',
  style = {},
  variant = 'default',
  dense = false,
  ...props
}, ref) => {
  const { theme } = useTheme();

  const listStyles = {
    backgroundColor: 'var(--mac-bg-primary)',
    borderRadius: '8px',
    border: '1px solid var(--mac-border)',
    overflow: 'hidden',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    ...style
  };

  return (
    <ul
      ref={ref}
      className={`mac-list mac-list--${variant} ${dense ? 'mac-list--dense' : ''} ${className}`}
      style={listStyles}
      {...props}
    >
      {children}
    </ul>
  );
});

/**
 * macOS-style ListItem Component
 */
const ListItem = React.forwardRef(({
  children,
  className = '',
  style = {},
  button = false,
  selected = false,
  disabled = false,
  onClick,
  ...props
}, ref) => {
  const itemStyles = {
    display: 'flex',
    alignItems: 'center',
    padding: '12px 16px',
    borderBottom: '1px solid var(--mac-separator)',
    transition: 'background-color 0.2s ease',
    cursor: button && !disabled ? 'pointer' : 'default',
    backgroundColor: selected ? 'var(--mac-accent-blue)' : 'transparent',
    color: selected ? 'white' : disabled ? 'var(--mac-text-disabled)' : 'var(--mac-text-primary)',
    opacity: disabled ? 0.6 : 1,
    ...style
  };

  const handleMouseEnter = (e) => {
    if (button && !disabled && !selected) {
      e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
    }
  };

  const handleMouseLeave = (e) => {
    if (button && !disabled && !selected) {
      e.target.style.backgroundColor = 'transparent';
    }
  };

  const Component = button ? 'button' : 'li';

  return (
    <Component
      ref={ref}
      className={`mac-list-item ${button ? 'mac-list-item--button' : ''} ${selected ? 'mac-list-item--selected' : ''} ${disabled ? 'mac-list-item--disabled' : ''} ${className}`}
      style={itemStyles}
      onClick={disabled ? undefined : onClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      disabled={disabled}
      {...props}
    >
      {children}
    </Component>
  );
});

/**
 * macOS-style ListItemText Component
 */
const ListItemText = React.forwardRef(({
  primary,
  secondary,
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const textStyles = {
    flex: 1,
    minWidth: 0,
    ...style
  };

  return (
    <div
      ref={ref}
      className={`mac-list-item-text ${className}`}
      style={textStyles}
      {...props}
    >
      {primary && (
        <div style={{
          fontSize: '14px',
          fontWeight: '500',
          color: 'var(--mac-text-primary)',
          marginBottom: secondary ? '2px' : '0'
        }}>
          {primary}
        </div>
      )}
      {secondary && (
        <div style={{
          fontSize: '12px',
          color: 'var(--mac-text-secondary)',
          lineHeight: '1.3'
        }}>
          {secondary}
        </div>
      )}
      {children}
    </div>
  );
});

/**
 * macOS-style ListItemIcon Component
 */
const ListItemIcon = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const iconStyles = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: '12px',
    color: 'var(--mac-text-secondary)',
    ...style
  };

  return (
    <div
      ref={ref}
      className={`mac-list-item-icon ${className}`}
      style={iconStyles}
      {...props}
    >
      {children}
    </div>
  );
});

/**
 * macOS-style ListItemSecondaryAction Component
 */
const ListItemSecondaryAction = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const actionStyles = {
    display: 'flex',
    alignItems: 'center',
    marginLeft: '12px',
    ...style
  };

  return (
    <div
      ref={ref}
      className={`mac-list-item-secondary-action ${className}`}
      style={actionStyles}
      {...props}
    >
      {children}
    </div>
  );
});

/**
 * macOS-style Divider Component
 */
const Divider = React.forwardRef(({
  className = '',
  style = {},
  variant = 'fullWidth',
  orientation = 'horizontal',
  ...props
}, ref) => {
  const dividerStyles = {
    border: 'none',
    backgroundColor: 'var(--mac-separator)',
    ...(orientation === 'horizontal' ? {
      height: '1px',
      width: variant === 'fullWidth' ? '100%' : 'auto',
      margin: variant === 'inset' ? '8px 16px' : '0'
    } : {
      width: '1px',
      height: variant === 'fullWidth' ? '100%' : 'auto',
      margin: variant === 'inset' ? '16px 8px' : '0'
    }),
    ...style
  };

  return (
    <hr
      ref={ref}
      className={`mac-divider mac-divider--${orientation} mac-divider--${variant} ${className}`}
      style={dividerStyles}
      {...props}
    />
  );
});

List.displayName = 'List';
ListItem.displayName = 'ListItem';
ListItemText.displayName = 'ListItemText';
ListItemIcon.displayName = 'ListItemIcon';
ListItemSecondaryAction.displayName = 'ListItemSecondaryAction';
Divider.displayName = 'Divider';

export default List;
export { ListItem, ListItemText, ListItemIcon, ListItemSecondaryAction, Divider };
