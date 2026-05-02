import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { useTheme } from '../../../contexts/ThemeContext';
import Button from './Button';
import Icon from './Icon';

/**
 * macOS-style Sidebar Component
 * Implements Apple's Human Interface Guidelines for sidebar navigation
 */
const Sidebar = React.forwardRef(({
  items = [],
  activeItem,
  onItemClick,
  collapsible = true,
  defaultCollapsed = false,
  header,
  footer,
  variant = 'default',
  className = '',
  style = {},
  ...props
}, ref) => {void
  useTheme();
  void variant;
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);

  const sidebarStyles = {
    width: isCollapsed ? '72px' : '280px', // Стандартные размеры macOS
    minHeight: '100vh',
    background: 'var(--mac-gradient-sidebar)',
    borderRight: '1px solid var(--mac-separator)',
    borderRadius: 'var(--mac-radius-lg)',
    boxShadow: 'var(--mac-shadow-md)',
    display: 'flex',
    flexDirection: 'column',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    backdropFilter: 'var(--mac-blur-light)',
    WebkitBackdropFilter: 'var(--mac-blur-light)',
    position: 'relative',
    ...style
  };

  const headerStyles = {
    padding: isCollapsed ? '16px 8px' : '16px 20px',
    borderBottom: '1px solid var(--mac-separator)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: isCollapsed ? 'center' : 'space-between',
    minHeight: '60px'
  };

  const navStyles = {
    flex: 1,
    padding: isCollapsed ? '8px' : '16px 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    overflowY: 'auto'
  };

  const footerStyles = {
    padding: isCollapsed ? '8px' : '16px 12px',
    borderTop: '1px solid var(--mac-separator)',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px'
  };

  const toggleCollapsed = () => {
    if (collapsible) {
      setIsCollapsed(!isCollapsed);
    }
  };

  return (
    <aside
      ref={ref}
      className={`mac-sidebar ${isCollapsed ? 'mac-sidebar--collapsed' : ''} ${className}`}
      style={sidebarStyles}
      {...props}>

      {/* Header */}
      {header &&
      <div className="mac-sidebar-header" style={headerStyles}>
          {!isCollapsed &&
        <div className="mac-sidebar-header-content">
              {header}
            </div>
        }

          {collapsible &&
        <Button
          variant="ghost"
          size="small"
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          onClick={toggleCollapsed}
          style={{
            width: '32px',
            height: '32px',
            borderRadius: 'var(--mac-radius-sm)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--mac-text-primary)'
          }}>

              <Icon
            name={isCollapsed ? 'chevron.right' : 'chevron.left'}
            size="small"
            style={{ color: 'var(--mac-text-primary)' }} />

            </Button>
        }
        </div>
      }

      {/* Navigation Items */}
      <nav className="mac-sidebar-nav" style={navStyles}>
        {items.map((item) => {
          const isActive = activeItem === item.id;
          const itemStyles = {
            display: 'flex',
            alignItems: 'center',
            padding: isCollapsed ? '12px' : '8px 12px',
            borderRadius: '4px', // Все 4 угла скруглены 4px
            background: isActive ? 'var(--mac-nav-item-active)' : 'var(--mac-nav-item-bg)',
            color: isActive ? 'var(--mac-nav-item-active-text)' : 'var(--mac-text-primary)',
            textDecoration: 'none',
            fontSize: '13px',
            fontWeight: isActive ? '600' : '400',
            fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
            cursor: 'pointer',
            transition: 'all 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
            border: isActive ? '1px solid var(--mac-nav-item-active-border)' : '1px solid var(--mac-border)',
            width: '100%',
            justifyContent: isCollapsed ? 'center' : 'flex-start',
            gap: isCollapsed ? '0' : '8px',
            boxShadow: isActive ? '0 8px 18px rgba(0, 0, 0, 0.14)' : 'none',
          };

          const handleItemClick = () => {
            if (onItemClick) {
              onItemClick(item);
            }
          };

          return (
            <button
              key={item.id}
              aria-label={item.label}
              className={`mac-sidebar-item ${isActive ? 'mac-sidebar-item--active' : ''}`}
              style={itemStyles}
              onClick={handleItemClick}
              title={isCollapsed ? item.label : undefined}>

              {item.icon &&
              <Icon
                name={item.icon}
                size="default"
                style={{
                  color: isActive ? 'var(--mac-nav-item-active-text)' : 'var(--mac-text-primary)'
                }} />

              }

              {!isCollapsed &&
              <span style={{
                flex: 1,
                textAlign: 'left',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                color: isActive ? 'var(--mac-nav-item-active-text)' : 'var(--mac-text-primary)'
              }}>
                  {item.label}
                </span>
              }

              {!isCollapsed && item.badge &&
              <span style={{
                backgroundColor: isActive ? 'rgba(255, 255, 255, 0.16)' : 'var(--mac-bg-secondary)',
                color: isActive ? 'var(--mac-nav-item-active-text)' : 'var(--mac-text-primary)',
                fontSize: '11px',
                fontWeight: '600',
                padding: '2px 6px',
                borderRadius: '10px',
                minWidth: '18px',
                textAlign: 'center'
              }}>
                  {item.badge}
                </span>
              }
            </button>);

        })}
      </nav>

      {/* Footer */}
      {footer &&
      <div className="mac-sidebar-footer" style={footerStyles}>
          {!isCollapsed && footer}
        </div>
      }

      <style>{`
        .mac-sidebar::-webkit-scrollbar {
          width: 6px;
        }

        .mac-sidebar::-webkit-scrollbar-track {
          background: transparent;
        }

        .mac-sidebar::-webkit-scrollbar-thumb {
          background: var(--mac-border);
          border-radius: 3px;
        }

        .mac-sidebar::-webkit-scrollbar-thumb:hover {
          background: var(--mac-text-tertiary);
        }

        .mac-sidebar-item:hover {
          background: ${isCollapsed ? 'transparent' : 'var(--mac-nav-item-hover)'} !important;
          color: var(--mac-text-primary) !important;
        }

        .mac-sidebar-item:hover .mac-icon {
          color: var(--mac-text-primary) !important;
        }

        .mac-sidebar-item--active:hover {
          background: var(--mac-nav-item-active) !important;
          border-color: var(--mac-nav-item-active-border) !important;
        }

        /* Dark mode adjustments */
        @media (prefers-color-scheme: dark) {
          .mac-sidebar {
            background-color: var(--mac-bg-tertiary);
            border-color: var(--mac-separator);
          }
        }

        /* High contrast mode */
        @media (prefers-contrast: high) {
          .mac-sidebar {
            border-width: 2px;
          }

          .mac-sidebar-item {
            border: 1px solid transparent;
          }

          .mac-sidebar-item--active {
            border-color: var(--mac-accent-blue);
          }
        }

        /* Reduced motion */
        @media (prefers-reduced-motion: reduce) {
          .mac-sidebar,
          .mac-sidebar-item {
            transition: none !important;
          }
        }
      `}</style>
    </aside>);

});

Sidebar.displayName = 'macOS Sidebar';

/**
 * Sidebar Item Component
 */
export const SidebarItem = React.forwardRef(({
  icon,
  label,
  badge,
  active = false,
  onClick,
  className = '',
  style = {},
  ...props
}, ref) => {
  return (
    <button
      ref={ref}
      aria-label={label}
      className={`mac-sidebar-item ${active ? 'mac-sidebar-item--active' : ''} ${className}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '8px 12px',
        borderRadius: '4px', // Все 4 угла скруглены 4px
        background: active ? 'var(--mac-nav-item-active)' : 'var(--mac-nav-item-bg)',
        color: active ? 'var(--mac-nav-item-active-text)' : 'var(--mac-text-primary)',
        textDecoration: 'none',
        fontSize: '13px',
        fontWeight: active ? '600' : '400',
        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
        cursor: 'pointer',
        transition: 'all 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
        border: active ? '1px solid var(--mac-nav-item-active-border)' : '1px solid var(--mac-border)',
        width: '100%',
        justifyContent: 'flex-start',
        gap: '8px',
        ...style
      }}
      onClick={onClick}
      {...props}>

      {icon &&
      <Icon
        name={icon}
        size="default"
        style={{
          color: active ? 'var(--mac-nav-item-active-text)' : 'var(--mac-text-primary)'
        }} />

      }

      <span style={{
        flex: 1,
        textAlign: 'left',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis'
      }}>
        {label}
      </span>

      {badge &&
      <span style={{
        backgroundColor: active ? 'rgba(255, 255, 255, 0.16)' : 'var(--mac-bg-secondary)',
        color: active ? 'var(--mac-nav-item-active-text)' : 'var(--mac-text-primary)',
        fontSize: '11px',
        fontWeight: '600',
        padding: '2px 6px',
        borderRadius: '10px',
        minWidth: '18px',
        textAlign: 'center'
      }}>
          {badge}
        </span>
      }
    </button>);

});

SidebarItem.displayName = 'macOS Sidebar Item';

/**
 * Sidebar Section Component
 */
export const SidebarSection = React.forwardRef(({
  title,
  children,
  collapsible = false,
  defaultCollapsed = false,
  className = '',
  style = {},
  ...props
}, ref) => {
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);

  const sectionStyles = {
    marginBottom: '16px',
    ...style
  };

  const headerStyles = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 12px',
    marginBottom: '8px',
    cursor: collapsible ? 'pointer' : 'default'
  };

  const contentStyles = {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    overflow: 'hidden',
    transition: 'all 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
    maxHeight: isCollapsed ? '0' : 'none',
    opacity: isCollapsed ? 0 : 1
  };

  const handleToggle = () => {
    if (collapsible) {
      setIsCollapsed(!isCollapsed);
    }
  };
  const handleToggleKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleToggle();
    }
  };

  return (
    <div
      ref={ref}
      className={`mac-sidebar-section ${className}`}
      style={sectionStyles}
      {...props}>

      {title && collapsible &&
      <div
        className="mac-sidebar-section-header"
        style={headerStyles}
        onClick={handleToggle}
        onKeyDown={handleToggleKeyDown}
        role="button"
        tabIndex={0}>

          <span style={{
          fontSize: '11px',
          fontWeight: '600',
          color: 'var(--mac-text-tertiary)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif'
        }}>
            {title}
          </span>

          <Icon
          name={isCollapsed ? 'chevron.right' : 'chevron.down'}
          size="small"
          style={{
            color: 'var(--mac-text-tertiary)',
            transition: 'transform 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
            transform: isCollapsed ? 'rotate(0deg)' : 'rotate(0deg)'
          }} />
        </div>
      }
      {title && !collapsible &&
      <div
        className="mac-sidebar-section-header"
        style={headerStyles}>

          <span style={{
          fontSize: '11px',
          fontWeight: '600',
          color: 'var(--mac-text-tertiary)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif'
        }}>
            {title}
          </span>

        </div>
      }

      <div
        className="mac-sidebar-section-content"
        style={contentStyles}>

        {children}
      </div>
    </div>);

});

SidebarSection.displayName = 'macOS Sidebar Section';

Sidebar.propTypes = {
  items: PropTypes.array,
  activeItem: PropTypes.any,
  onItemClick: PropTypes.func,
  collapsible: PropTypes.bool,
  defaultCollapsed: PropTypes.bool,
  header: PropTypes.node,
  footer: PropTypes.node,
  variant: PropTypes.string,
  className: PropTypes.string,
  style: PropTypes.object
};

SidebarItem.propTypes = {
  icon: PropTypes.string,
  label: PropTypes.node,
  badge: PropTypes.node,
  active: PropTypes.bool,
  onClick: PropTypes.func,
  className: PropTypes.string,
  style: PropTypes.object
};

SidebarSection.propTypes = {
  title: PropTypes.node,
  children: PropTypes.node,
  collapsible: PropTypes.bool,
  defaultCollapsed: PropTypes.bool,
  className: PropTypes.string,
  style: PropTypes.object
};

export default Sidebar;
