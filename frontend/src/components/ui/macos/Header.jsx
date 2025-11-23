import React from 'react';
import { useTheme } from '../../../contexts/ThemeContext';
import { Button } from './Button';
import { Icon } from './Icon';
import { Avatar } from './Avatar';

/**
 * macOS-style Header Component
 * Implements Apple's Human Interface Guidelines for window headers
 */
const Header = React.forwardRef(({
  title,
  subtitle,
  actions,
  navigation,
  user,
  onUserClick,
  onSettingsClick,
  variant = 'default',
  className = '',
  style = {},
  ...props
}, ref) => {
  const { theme } = useTheme();

  const headerStyles = {
    height: '44px',
    backgroundColor: 'var(--mac-bg-toolbar)',
    borderBottom: '1px solid var(--mac-separator)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 16px',
    backdropFilter: 'var(--mac-blur-light)',
    WebkitBackdropFilter: 'var(--mac-blur-light)',
    position: 'sticky',
    top: 0,
    zIndex: 100,
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    ...style
  };

  const titleSectionStyles = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    flex: 1,
    minWidth: 0
  };

  const titleStyles = {
    fontSize: '15px',
    fontWeight: '600',
    color: 'var(--mac-text-primary)',
    margin: 0,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis'
  };

  const subtitleStyles = {
    fontSize: '11px',
    color: 'var(--mac-text-secondary)',
    margin: 0,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis'
  };

  const controlsSectionStyles = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px'
  };

  const navigationStyles = {
    display: 'flex',
    alignItems: 'center',
    gap: '4px'
  };

  const actionsStyles = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px'
  };

  return (
    <header
      ref={ref}
      className={`mac-header ${className}`}
      style={headerStyles}
      {...props}
    >
      {/* Left Section - Navigation */}
      {(navigation || title) && (
        <div className="mac-header-left" style={titleSectionStyles}>
          {navigation && (
            <nav className="mac-header-navigation" style={navigationStyles}>
              {navigation}
            </nav>
          )}

          {title && (
            <div className="mac-header-title-section">
              <h1 className="mac-header-title" style={titleStyles}>
                {title}
              </h1>
              {subtitle && (
                <p className="mac-header-subtitle" style={subtitleStyles}>
                  {subtitle}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Center Section - Actions */}
      {actions && (
        <div className="mac-header-center" style={actionsStyles}>
          {actions}
        </div>
      )}

      {/* Right Section - User Controls */}
      <div className="mac-header-right" style={controlsSectionStyles}>
        {/* Settings Button */}
        {onSettingsClick && (
          <Button
            variant="ghost"
            size="small"
            onClick={onSettingsClick}
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
          <Icon name="gear" size="small" color="accent" />
          </Button>
        )}

        {/* User Avatar */}
        {user && (
          <Button
            variant="ghost"
            size="small"
            onClick={onUserClick}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '4px 8px',
              height: '32px'
            }}
          >
            <Avatar
              src={user.avatar}
              name={user.name}
              size="small"
              status={user.status}
            />
            <span style={{
              fontSize: '13px',
              fontWeight: '500',
              color: 'var(--mac-text-primary)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: '120px'
            }}>
              {user.name}
            </span>
          </Button>
        )}
      </div>

      <style jsx>{`
        .mac-header {
          box-shadow: 0 1px 0 rgba(0, 0, 0, 0.1);
        }

        .mac-header-title-section {
          display: 'flex';
          flex-direction: 'column';
          min-width: 0;
          flex: 1;
        }

        .mac-header-title {
          font-size: 15px;
          font-weight: 600;
          color: var(--mac-text-primary);
          margin: 0;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .mac-header-subtitle {
          font-size: 11px;
          color: var(--mac-text-secondary);
          margin: 0;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        /* Dark mode adjustments */
        @media (prefers-color-scheme: dark) {
          .mac-header {
            background-color: rgba(255, 255, 255, 0.05);
            border-color: var(--mac-separator);
          }
        }

        /* High contrast mode */
        @media (prefers-contrast: high) {
          .mac-header {
            border-width: 2px;
          }
        }
      `}</style>
    </header>
  );
});

Header.displayName = 'macOS Header';

/**
 * Header Navigation Item Component
 */
export const HeaderNavItem = React.forwardRef(({
  children,
  active = false,
  onClick,
  className = '',
  style = {},
  ...props
}, ref) => {
  return (
    <button
      ref={ref}
      className={`mac-header-nav-item ${active ? 'mac-header-nav-item--active' : ''} ${className}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '4px 8px',
        borderRadius: '4px',
        backgroundColor: active ? 'var(--mac-accent-blue)' : 'transparent',
        color: active ? 'white' : 'var(--mac-text-secondary)',
        fontSize: '13px',
        fontWeight: active ? '600' : '400',
        cursor: 'pointer',
        transition: 'all 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
        border: 'none',
        ...style
      }}
      onClick={onClick}
      {...props}
    >
      {children}
    </button>
  );
});

HeaderNavItem.displayName = 'macOS Header Navigation Item';

/**
 * Header Search Component
 */
export const HeaderSearch = React.forwardRef(({
  placeholder = 'Search...',
  value,
  onChange,
  onClear,
  className = '',
  style = {},
  ...props
}, ref) => {
  const [isFocused, setIsFocused] = React.useState(false);

  const searchStyles = {
    display: 'flex',
    alignItems: 'center',
    backgroundColor: isFocused ? 'var(--mac-bg-primary)' : 'var(--mac-bg-secondary)',
    border: `1px solid ${isFocused ? 'var(--mac-accent-blue)' : 'var(--mac-border)'}`,
    borderRadius: '6px',
    padding: '4px 8px',
    fontSize: '13px',
    color: 'var(--mac-text-primary)',
    transition: 'all 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
    minWidth: '200px',
    ...style
  };

  return (
    <div className={`mac-header-search ${className}`} style={{ position: 'relative' }}>
      <Icon
        name="magnifyingglass"
        size="small"
        style={{
          color: 'var(--mac-text-tertiary)',
          marginRight: '4px',
          flexShrink: 0
        }}
      />

      <input
        ref={ref}
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        style={{
          flex: 1,
          border: 'none',
          background: 'transparent',
          outline: 'none',
          fontSize: '13px',
          color: 'var(--mac-text-primary)',
          fontFamily: 'inherit'
        }}
        {...props}
      />

      {value && onClear && (
        <Button
          variant="ghost"
          size="small"
          onClick={onClear}
          style={{
            width: '16px',
            height: '16px',
            borderRadius: '3px',
            padding: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            marginLeft: '4px'
          }}
        >
          <Icon name="xmark" size="small" />
        </Button>
      )}

      <style jsx>{`
        .mac-header-search:focus-within {
          background-color: var(--mac-bg-primary) !important;
          border-color: var(--mac-accent-blue) !important;
          box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.1);
        }

        /* Dark mode adjustments */
        @media (prefers-color-scheme: dark) {
          .mac-header-search {
            background-color: rgba(255, 255, 255, 0.05) !important;
            border-color: rgba(255, 255, 255, 0.1) !important;
          }

          .mac-header-search:focus-within {
            background-color: rgba(255, 255, 255, 0.08) !important;
            border-color: var(--mac-accent-blue) !important;
            box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.2) !important;
          }
        }
      `}</style>
    </div>
  );
});

HeaderSearch.displayName = 'macOS Header Search';

/**
 * Header Breadcrumb Component
 */
export const HeaderBreadcrumb = React.forwardRef(({
  items = [],
  separator = '/',
  className = '',
  style = {},
  ...props
}, ref) => {
  const breadcrumbStyles = {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    fontSize: '11px',
    color: 'var(--mac-text-secondary)',
    ...style
  };

  const itemStyles = {
    color: 'var(--mac-text-secondary)',
    textDecoration: 'none',
    transition: 'color 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
    cursor: 'default'
  };

  const separatorStyles = {
    color: 'var(--mac-text-tertiary)',
    fontSize: '10px',
    margin: '0 2px',
    userSelect: 'none'
  };

  const lastItemStyles = {
    ...itemStyles,
    color: 'var(--mac-text-primary)',
    fontWeight: '500'
  };

  return (
    <nav
      ref={ref}
      className={`mac-header-breadcrumb ${className}`}
      style={breadcrumbStyles}
      aria-label="Breadcrumb"
      {...props}
    >
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        const itemStyle = isLast ? lastItemStyles : itemStyles;

        return (
          <React.Fragment key={item.id || index}>
            <span
              className={`mac-header-breadcrumb-item ${isLast ? 'mac-header-breadcrumb-item--current' : ''}`}
              style={itemStyle}
            >
              {item.label}
            </span>

            {!isLast && (
              <span
                className="mac-header-breadcrumb-separator"
                style={separatorStyles}
                aria-hidden="true"
              >
                {separator}
              </span>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
});

HeaderBreadcrumb.displayName = 'macOS Header Breadcrumb';

export default Header;
