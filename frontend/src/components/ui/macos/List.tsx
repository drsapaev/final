import React, { type ReactNode, type CSSProperties, type MouseEvent } from 'react';
import PropTypes from 'prop-types';
import { useTheme } from '../../../contexts/ThemeContext';

type ListVariant = 'default' | 'compact' | 'inset';
type DividerVariant = 'fullWidth' | 'inset' | 'middle';
type DividerOrientation = 'horizontal' | 'vertical';

interface ListProps extends Omit<React.HTMLAttributes<HTMLUListElement>, 'children' | 'style'> {
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
  variant?: ListVariant;
  dense?: boolean;
}

interface ListItemProps extends Omit<React.HTMLAttributes<HTMLLIElement>, 'children' | 'style' | 'onClick'> {
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
  button?: boolean;
  selected?: boolean;
  disabled?: boolean;
  onClick?: (e: MouseEvent<HTMLLIElement>) => void;
}

interface ListItemTextProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'children' | 'style'> {
  primary?: ReactNode;
  secondary?: ReactNode;
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

interface ListItemIconProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'children' | 'style'> {
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

interface ListItemSecondaryActionProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'children' | 'style'> {
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

interface DividerProps extends Omit<React.HTMLAttributes<HTMLHRElement>, 'style'> {
  className?: string;
  style?: CSSProperties;
  variant?: DividerVariant;
  orientation?: DividerOrientation;
}

interface ListItemStyle extends CSSProperties {
  transition?: string;
}

/**
 * macOS-style List Component
 * Implements Apple's Human Interface Guidelines for lists
 */
const List = React.forwardRef<HTMLUListElement, ListProps>(({
  children,
  className = '',
  style = {},
  variant = 'default',
  dense = false,
  ...props
}, ref) => {
  useTheme();

  const listStyles: CSSProperties = {
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
      {...props}>

      {children}
    </ul>);

});

/**
 * macOS-style ListItem Component
 */
const ListItem = React.forwardRef<HTMLLIElement, ListItemProps>(({
  children,
  className = '',
  style = {},
  button = false,
  selected = false,
  disabled = false,
  onClick,
  ...props
}, ref) => {
  const itemStyles: ListItemStyle = {
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

  const handleMouseEnter = (e: MouseEvent<HTMLLIElement>) => {
    if (button && !disabled && !selected) {
      e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
    }
  };

  const handleMouseLeave = (e: MouseEvent<HTMLLIElement>) => {
    if (button && !disabled && !selected) {
      e.currentTarget.style.backgroundColor = 'transparent';
    }
  };

  // When `button` is true the original code rendered a <button>, but
  // <button> cannot be a direct child of <ul> (invalid HTML). The
  // forwardRef typing is also for HTMLLIElement, so we keep <li>
  // always and let the cursor/onClick props carry the button affordance.
  return (
    <li
      ref={ref}
      className={`mac-list-item ${button ? 'mac-list-item--button' : ''} ${selected ? 'mac-list-item--selected' : ''} ${disabled ? 'mac-list-item--disabled' : ''} ${className}`}
      style={itemStyles}
      onClick={disabled ? undefined : onClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      aria-disabled={disabled || undefined}
      {...props}>

      {children}
    </li>);

});

/**
 * macOS-style ListItemText Component
 */
const ListItemText = React.forwardRef<HTMLDivElement, ListItemTextProps>(({
  primary,
  secondary,
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const textStyles: CSSProperties = {
    flex: 1,
    minWidth: 0,
    ...style
  };

  return (
    <div
      ref={ref}
      className={`mac-list-item-text ${className}`}
      style={textStyles}
      {...props}>

      {primary &&
      <div style={{
        fontSize: '14px',
        fontWeight: '500',
        color: 'var(--mac-text-primary)',
        marginBottom: secondary ? '2px' : '0'
      }}>
          {primary}
        </div>
      }
      {secondary &&
      <div style={{
        fontSize: '12px',
        color: 'var(--mac-text-secondary)',
        lineHeight: '1.3'
      }}>
          {secondary}
        </div>
      }
      {children}
    </div>);

});

/**
 * macOS-style ListItemIcon Component
 */
const ListItemIcon = React.forwardRef<HTMLDivElement, ListItemIconProps>(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const iconStyles: CSSProperties = {
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
      {...props}>

      {children}
    </div>);

});

/**
 * macOS-style ListItemSecondaryAction Component
 */
const ListItemSecondaryAction = React.forwardRef<HTMLDivElement, ListItemSecondaryActionProps>(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  const actionStyles: CSSProperties = {
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
      {...props}>

      {children}
    </div>);

});

/**
 * macOS-style Divider Component
 */
const Divider = React.forwardRef<HTMLHRElement, DividerProps>(({
  className = '',
  style = {},
  variant = 'fullWidth',
  orientation = 'horizontal',
  ...props
}, ref) => {
  const dividerStyles: CSSProperties = {
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
      {...props} />);


});

List.displayName = 'List';
ListItem.displayName = 'ListItem';
ListItemText.displayName = 'ListItemText';
ListItemIcon.displayName = 'ListItemIcon';
ListItemSecondaryAction.displayName = 'ListItemSecondaryAction';
Divider.displayName = 'Divider';

List.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object,
  variant: PropTypes.string,
  dense: PropTypes.bool
};

ListItem.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object,
  button: PropTypes.bool,
  selected: PropTypes.bool,
  disabled: PropTypes.bool,
  onClick: PropTypes.func
};

ListItemText.propTypes = {
  primary: PropTypes.node,
  secondary: PropTypes.node,
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object
};

ListItemIcon.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object
};

ListItemSecondaryAction.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string,
  style: PropTypes.object
};

Divider.propTypes = {
  className: PropTypes.string,
  style: PropTypes.object,
  variant: PropTypes.string,
  orientation: PropTypes.string
};

export default List;
export { ListItem, ListItemText, ListItemIcon, ListItemSecondaryAction, Divider };
