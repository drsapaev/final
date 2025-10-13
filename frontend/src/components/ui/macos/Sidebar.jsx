import React, { useState } from 'react';
import { useTheme } from '../../../contexts/ThemeContext';
import { Button } from './Button';
import { Icon } from './Icon';

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
}, ref) => {
  const { theme } = useTheme();
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);

  const sidebarStyles = {
    width: isCollapsed ? '64px' : '240px',
    minHeight: '100vh',
    backgroundColor: 'var(--mac-bg-secondary)',
    borderRight: '1px solid var(--mac-separator)',
    display: 'flex',
    flexDirection: 'column',
    transition: 'width 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
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
      {...props}
    >
      {/* Header */}
      {header && (
        <div className="mac-sidebar-header" style={headerStyles}>
          {!isCollapsed && (
            <div className="mac-sidebar-header-content">
              {header}
            </div>
          )}

          {collapsible && (
            <Button
              variant="ghost"
              size="small"
              onClick={toggleCollapsed}
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <Icon
                name={isCollapsed ? 'chevron.right' : 'chevron.left'}
                size="small"
              />
            </Button>
          )}
        </div>
      )}

      {/* Navigation Items */}
      <nav className="mac-sidebar-nav" style={navStyles}>
        {items.map((item) => {
          const isActive = activeItem === item.id;
          const itemStyles = {
            display: 'flex',
            alignItems: 'center',
            padding: isCollapsed ? '12px' : '8px 12px',
            borderRadius: '6px',
            backgroundColor: isActive ? 'var(--mac-accent-blue)' : 'transparent',
            color: isActive ? 'white' : 'var(--mac-text-secondary)',
            textDecoration: 'none',
            fontSize: '13px',
            fontWeight: isActive ? '600' : '400',
            fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
            cursor: 'pointer',
            transition: 'all 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
            border: 'none',
            width: '100%',
            justifyContent: isCollapsed ? 'center' : 'flex-start',
            gap: isCollapsed ? '0' : '8px'
          };

          const handleItemClick = () => {
            if (onItemClick) {
              onItemClick(item);
            }
          };

          return (
            <button
              key={item.id}
              className={`mac-sidebar-item ${isActive ? 'mac-sidebar-item--active' : ''}`}
              style={itemStyles}
              onClick={handleItemClick}
              title={isCollapsed ? item.label : undefined}
            >
              {item.icon && (
                <Icon
                  name={item.icon}
                  size="default"
                  style={{
                    color: isActive ? 'white' : 'var(--mac-text-secondary)'
                  }}
                />
              )}

              {!isCollapsed && (
                <span style={{
                  flex: 1,
                  textAlign: 'left',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis'
                }}>
                  {item.label}
                </span>
              )}

              {!isCollapsed && item.badge && (
                <span style={{
                  backgroundColor: isActive ? 'rgba(255, 255, 255, 0.2)' : 'var(--mac-bg-tertiary)',
                  color: isActive ? 'white' : 'var(--mac-text-secondary)',
                  fontSize: '11px',
                  fontWeight: '600',
                  padding: '2px 6px',
                  borderRadius: '10px',
                  minWidth: '18px',
                  textAlign: 'center'
                }}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      {footer && (
        <div className="mac-sidebar-footer" style={footerStyles}>
          {!isCollapsed && footer}
        </div>
      )}

      <style jsx>{`
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
          background-color: ${isCollapsed ? 'transparent' : 'var(--mac-bg-tertiary)'} !important;
          color: var(--mac-text-primary) !important;
        }

        .mac-sidebar-item:hover .mac-icon {
          color: var(--mac-text-primary) !important;
        }

        .mac-sidebar-item--active:hover {
          background-color: var(--mac-accent-blue-hover) !important;
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
    </aside>
  );
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
      className={`mac-sidebar-item ${active ? 'mac-sidebar-item--active' : ''} ${className}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '8px 12px',
        borderRadius: '6px',
        backgroundColor: active ? 'var(--mac-accent-blue)' : 'transparent',
        color: active ? 'white' : 'var(--mac-text-secondary)',
        textDecoration: 'none',
        fontSize: '13px',
        fontWeight: active ? '600' : '400',
        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
        cursor: 'pointer',
        transition: 'all 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
        border: 'none',
        width: '100%',
        justifyContent: 'flex-start',
        gap: '8px',
        ...style
      }}
      onClick={onClick}
      {...props}
    >
      {icon && (
        <Icon
          name={icon}
          size="default"
          style={{
            color: active ? 'white' : 'var(--mac-text-secondary)'
          }}
        />
      )}

      <span style={{
        flex: 1,
        textAlign: 'left',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis'
      }}>
        {label}
      </span>

      {badge && (
        <span style={{
          backgroundColor: active ? 'rgba(255, 255, 255, 0.2)' : 'var(--mac-bg-tertiary)',
          color: active ? 'white' : 'var(--mac-text-secondary)',
          fontSize: '11px',
          fontWeight: '600',
          padding: '2px 6px',
          borderRadius: '10px',
          minWidth: '18px',
          textAlign: 'center'
        }}>
          {badge}
        </span>
      )}
    </button>
  );
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

  return (
    <div
      ref={ref}
      className={`mac-sidebar-section ${className}`}
      style={sectionStyles}
      {...props}
    >
      {title && (
        <div
          className="mac-sidebar-section-header"
          style={headerStyles}
          onClick={handleToggle}
        >
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

          {collapsible && (
            <Icon
              name={isCollapsed ? 'chevron.right' : 'chevron.down'}
              size="small"
              style={{
                color: 'var(--mac-text-tertiary)',
                transition: 'transform 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
                transform: isCollapsed ? 'rotate(0deg)' : 'rotate(0deg)'
              }}
            />
          )}
        </div>
      )}

      <div
        className="mac-sidebar-section-content"
        style={contentStyles}
      >
        {children}
      </div>
    </div>
  );
});

SidebarSection.displayName = 'macOS Sidebar Section';

export default Sidebar;
