import React, { useState, useEffect, type ReactNode, type CSSProperties, type MouseEvent, type KeyboardEvent } from 'react';
import PropTypes from 'prop-types';
import { useTheme } from '../../../contexts/ThemeContext';
import Button from './Button';
import Icon from './Icon';
import { useTranslation } from '../../../i18n/useTranslation';

type SidebarVariant = 'default' | 'compact' | 'inset';

interface SidebarItemData {
  id: string;
  label: ReactNode;
  icon?: string;
  badge?: ReactNode;
  tooltip?: string;
  title?: string;
  ariaLabel?: string;
  [key: string]: unknown;
}

interface SidebarSectionData {
  title?: string;
  items?: SidebarItemData[];
}

interface SidebarProps extends Omit<React.HTMLAttributes<HTMLElement>, 'children' | 'style'> {
  items?: SidebarItemData[];
  sections?: SidebarSectionData[] | null;
  activeItem?: string;
  onItemClick?: (item: SidebarItemData) => void;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
  collapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
  header?: ReactNode;
  footer?: ReactNode;
  variant?: SidebarVariant;
  className?: string;
  style?: CSSProperties;
}

interface SidebarItemProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'children' | 'style' | 'onClick'> {
  icon?: string;
  label: ReactNode;
  badge?: ReactNode;
  active?: boolean;
  onClick?: (e: MouseEvent<HTMLButtonElement>) => void;
  className?: string;
  style?: CSSProperties;
}

interface SidebarSectionProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'children' | 'style' | 'title'> {
  title?: ReactNode;
  children?: ReactNode;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
  className?: string;
  style?: CSSProperties;
}

interface SidebarStyle extends CSSProperties {
  transition?: string;
  WebkitBackdropFilter?: string;
}

/**
 * macOS-style Sidebar Component
 * Implements Apple's Human Interface Guidelines for sidebar navigation
 */
const Sidebar = React.forwardRef<HTMLElement, SidebarProps>(({
  items = [],
  sections = null,
  activeItem,
  onItemClick,
  collapsible = true,
  defaultCollapsed = false,
  collapsed,
  onCollapsedChange,
  header,
  footer,
  variant = 'default',
  className = '',
  style = {},
  ...props
}, ref) => {
  useTheme();
  const { t } = useTranslation();
  void t;
  void variant;
  // PR-49: persist collapse state in localStorage (was reset on every refresh)
  const STORAGE_KEY = 'mac-sidebar-collapsed';
  const [internalCollapsed, setInternalCollapsed] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved === 'true';
    } catch {
      return defaultCollapsed;
    }
  });
  const isControlled = typeof collapsed === 'boolean';
  const isCollapsed = isControlled ? (collapsed as boolean) : internalCollapsed;

  // PR-49: persist collapse state when it changes
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(internalCollapsed));
    } catch {
      // localStorage may be unavailable (private mode) — ignore
    }
  }, [internalCollapsed]);

  const setCollapsed = (nextCollapsed: boolean) => {
    if (!isControlled) {
      setInternalCollapsed(nextCollapsed);
    }
    onCollapsedChange?.(nextCollapsed);
  };

  const sidebarStyles: SidebarStyle = {
    width: isCollapsed ? '72px' : '280px',
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

  const headerStyles: CSSProperties = {
    padding: isCollapsed ? '16px 8px' : '16px 20px',
    borderBottom: '1px solid var(--mac-separator)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: isCollapsed ? 'center' : 'space-between',
    minHeight: '60px'
  };

  const navStyles: CSSProperties = {
    flex: 1,
    padding: isCollapsed ? '8px' : '16px 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    overflowY: 'auto'
  };

  const footerStyles: CSSProperties = {
    padding: isCollapsed ? '8px' : '16px 12px',
    borderTop: '1px solid var(--mac-separator)',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px'
  };

  const toggleCollapsed = () => {
    if (collapsible) {
      setCollapsed(!isCollapsed);
    }
  };

  return (
    <aside
      ref={ref}
      className={`mac-sidebar ${isCollapsed ? 'mac-sidebar--collapsed' : ''} ${className}`}
      style={sidebarStyles}
      {...props}>

      {/* Header */}
      {header ?
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
          aria-label={isCollapsed ? 'Развернуть боковую панель' : 'Свернуть боковую панель'}
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
       :
      collapsible &&
      <div className="mac-sidebar-header" style={headerStyles}>
        <Button
          variant="ghost"
          size="small"
          aria-label={isCollapsed ? 'Развернуть боковую панель' : 'Свернуть боковую панель'}
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
      </div>
      }

      {/* Navigation Items */}
      <nav className="mac-sidebar-nav" style={navStyles}>
        {(() => {
          // P-010 fix: helper to render a single sidebar item button.
          const renderItem = (item: SidebarItemData) => {
            const isActive = activeItem === item.id;
            const itemAriaLabel = (item.ariaLabel || item.tooltip || item.label) as string;
            const itemTitle = (item.tooltip || item.title || (isCollapsed ? (item.label as string) : undefined)) as string | undefined;
            const itemStyles: CSSProperties = {
              display: 'flex',
              alignItems: 'center',
              padding: isCollapsed ? '10px' : '7px 10px',
              borderRadius: 'var(--mac-radius-md, 6px)',
              // Sprint 8: macOS Finder-style active state — accent bg, no border, subtle
              background: isActive ? 'var(--mac-accent-bg)' : 'transparent',
              color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-primary)',
              textDecoration: 'none',
              fontSize: 'var(--mac-font-size-base, 13px)',
              fontWeight: isActive ? 'var(--mac-font-weight-semibold, 600)' : 'var(--mac-font-weight-normal, 400)',
              fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
              cursor: 'pointer',
              transition: 'background-color var(--mac-duration-fast, 0.15s) var(--mac-ease, ease), color var(--mac-duration-fast, 0.15s) var(--mac-ease, ease)',
              border: 'none',
              width: '100%',
              justifyContent: isCollapsed ? 'center' : 'flex-start',
              gap: isCollapsed ? '0' : '8px',
              boxShadow: 'none',
              margin: '1px 0',
            };

            const handleItemClick = () => {
              if (onItemClick) {
                onItemClick(item);
              }
            };

            return (
              <button
                key={item.id}
                aria-label={itemAriaLabel}
                className={`mac-sidebar-item ${isActive ? 'mac-sidebar-item--active' : ''}`}
                style={itemStyles}
                onClick={handleItemClick}
                title={itemTitle}>

                {item.icon &&
                <Icon
                  name={item.icon}
                  size="default"
                  style={{
                    // Sprint 8: active icon = accent color, inactive = secondary
                    color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
                    opacity: isActive ? 1 : 0.85,
                  }} />

                }

                {!isCollapsed &&
                <span style={{
                  flex: 1,
                  textAlign: 'left',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-primary)'
                }}>
                    {item.label}
                  </span>
                }

                {!isCollapsed && item.badge &&
                <span style={{
                  backgroundColor: isActive ? 'var(--mac-accent-bg)' : 'var(--mac-bg-tertiary)',
                  color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
                  fontSize: 'var(--mac-font-size-xs, 11px)',
                  fontWeight: 'var(--mac-font-weight-semibold, 600)',
                  padding: '2px 7px',
                  borderRadius: 'var(--mac-radius-sm, 4px)',
                  minWidth: '18px',
                  textAlign: 'center'
                }}>
                    {item.badge}
                  </span>
                }
              </button>);
          };

          // Sprint 8: Section header base style — macOS native: uppercase, muted
          const sectionHeaderBaseStyle: CSSProperties = {
            padding: '16px 12px 6px 12px',
            fontSize: 'var(--mac-font-size-xs, 11px)',
            fontWeight: 'var(--mac-font-weight-semibold, 600)',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            color: 'var(--mac-text-tertiary, var(--mac-text-secondary))',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          };

          // If sections provided AND sidebar is expanded (not collapsed),
          // render grouped with macOS-native visual separators between sections.
          if (Array.isArray(sections) && sections.length > 0 && !isCollapsed) {
            return sections.map((section, sectionIdx) => (
              <div key={`section-${sectionIdx}-${section.title || ''}`} style={{ marginBottom: '2px' }}>
                {section.title && (
                  <div
                    style={{
                      ...sectionHeaderBaseStyle,
                      borderTop: sectionIdx > 0 ? '1px solid var(--mac-separator, var(--mac-border))' : 'none',
                      marginTop: sectionIdx > 0 ? '8px' : '0',
                    }}
                    role="heading"
                    aria-level={3}
                    className="mac-sidebar-section-header">
                    {section.title}
                  </div>
                )}
                {(section.items || []).map(renderItem)}
              </div>
            ));
          }

          // Flat fallback (original behavior)
          return items.map(renderItem);
        })()}

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

        /* PR-49: Firefox scrollbar styling (was webkit-only) */
        .mac-sidebar {
          scrollbar-width: thin;
          scrollbar-color: var(--mac-border) transparent;
        }

        .mac-sidebar::-webkit-scrollbar-thumb:hover {
          background: var(--mac-text-tertiary);
        }

        .mac-sidebar-item:hover {
          background: ${isCollapsed ? 'transparent' : 'var(--mac-bg-secondary)'} !important;
        }

        .mac-sidebar-item:hover .mac-icon {
          color: var(--mac-text-primary) !important;
        }

        .mac-sidebar-item--active:hover {
          background: var(--mac-accent-bg) !important;
        }

        /* PR-49: fixed orphan CSS — was missing selector, browser silently discarded */
        .mac-sidebar-item--active {
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
export const SidebarItem = React.forwardRef<HTMLButtonElement, SidebarItemProps>(({
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
      aria-label={typeof label === 'string' ? label : undefined}
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
export const SidebarSection = React.forwardRef<HTMLDivElement, SidebarSectionProps>(({
  title,
  children,
  collapsible = false,
  defaultCollapsed = false,
  className = '',
  style = {},
  ...props
}, ref) => {
  const [isCollapsed, setIsCollapsed] = useState<boolean>(defaultCollapsed);

  const sectionStyles: CSSProperties = {
    marginBottom: '16px',
    ...style
  };

  const headerStyles: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 12px',
    marginBottom: '8px',
    cursor: collapsible ? 'pointer' : 'default'
  };

  const contentStyles: SidebarStyle = {
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
  const handleToggleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
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
  collapsed: PropTypes.bool,
  defaultCollapsed: PropTypes.bool,
  header: PropTypes.node,
  footer: PropTypes.node,
  onCollapsedChange: PropTypes.func,
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
