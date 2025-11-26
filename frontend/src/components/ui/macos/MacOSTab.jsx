import React from 'react';

const MacOSTab = ({ 
  tabs, 
  activeTab, 
  onTabChange,
  size = 'md',
  variant = 'default',
  orientation = 'horizontal',
  className,
  style
}) => {
  const sizeStyles = {
    sm: {
      padding: '6px 12px',
      fontSize: 'var(--mac-font-size-xs)',
      gap: '16px'
    },
    md: {
      padding: '8px 16px',
      fontSize: 'var(--mac-font-size-sm)',
      gap: '24px'
    },
    lg: {
      padding: '12px 20px',
      fontSize: 'var(--mac-font-size-base)',
      gap: '32px'
    }
  };

  const variantStyles = {
    default: {
      borderBottom: '1px solid var(--mac-separator)',
      background: 'transparent'
    },
    filled: {
      borderBottom: 'none',
      background: 'var(--mac-bg-secondary)',
      borderRadius: 'var(--mac-radius-md)',
      padding: '4px'
    },
    pills: {
      borderBottom: 'none',
      background: 'transparent',
      gap: '8px'
    }
  };

  const currentSize = sizeStyles[size];
  const currentVariant = variantStyles[variant];

  const containerStyle = {
    display: 'flex',
    flexDirection: 'column',
    marginBottom: variant === 'default' ? '24px' : '0',
    ...currentVariant,
    ...style
  };

  const tabButtonStyle = (isActive) => ({
    padding: currentSize.padding,
    border: 'none',
    borderRadius: variant === 'filled' ? 'var(--mac-radius-sm)' : variant === 'pills' ? 'var(--mac-radius-lg)' : '0',
    fontSize: currentSize.fontSize,
    fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
    color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)',
    background: variant === 'filled' ? (isActive ? 'var(--mac-bg-primary)' : 'transparent') : 'transparent',
    cursor: 'pointer',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    display: 'flex',
    alignItems: 'center',
    outline: 'none !important',
    outlineOffset: '0',
    position: 'relative',
    whiteSpace: 'nowrap',
    minHeight: '40px',
    boxSizing: 'border-box',
    boxShadow: 'none'
  });

  const handleTabClick = (tabId) => {
    onTabChange(tabId);
  };

  const handleKeyDown = (e, tabId) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onTabChange(tabId);
    }
  };

  const handleMouseEnter = (e, isActive) => {
    if (!isActive) {
      e.target.style.color = 'var(--mac-text-primary)';
      if (variant === 'filled') {
        e.target.style.background = 'var(--mac-bg-tertiary)';
      }
    }
  };

  const handleMouseLeave = (e, isActive) => {
    if (!isActive) {
      e.target.style.color = 'var(--mac-text-secondary)';
      if (variant === 'filled') {
        e.target.style.background = 'transparent';
      }
    }
  };

  const handleFocus = (e) => {
    // Ничего не делаем - убираем все эффекты фокуса
  };

  const handleBlur = (e) => {
    // Ничего не делаем - убираем все эффекты фокуса
  };

  return (
    <div className={className} style={containerStyle}>
      <div style={{ display: 'flex', gap: currentVariant.gap || currentSize.gap }}>
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          const IconComponent = tab.icon;
          
          return (
            <button
              key={tab.id}
              className="mac-tab-button"
              onClick={() => handleTabClick(tab.id)}
              onKeyDown={(e) => handleKeyDown(e, tab.id)}
              onMouseEnter={(e) => handleMouseEnter(e, isActive)}
              onMouseLeave={(e) => handleMouseLeave(e, isActive)}
              onFocus={handleFocus}
              onBlur={handleBlur}
              style={tabButtonStyle(isActive)}
              role="tab"
              aria-selected={isActive}
              tabIndex={isActive ? 0 : -1}
            >
              {IconComponent && (
                <IconComponent 
                  style={{ 
                    width: size === 'sm' ? '14px' : size === 'md' ? '16px' : '18px', 
                    height: size === 'sm' ? '14px' : size === 'md' ? '16px' : '18px', 
                    marginRight: '8px',
                    color: 'inherit'
                  }} 
                />
              )}
              {tab.label}
              {tab.badge && (
                <span style={{
                  marginLeft: '8px',
                  padding: '2px 6px',
                  borderRadius: 'var(--mac-radius-sm)',
                  fontSize: 'var(--mac-font-size-xs)',
                  fontWeight: 'var(--mac-font-weight-medium)',
                  background: 'var(--mac-accent-blue)',
                  color: 'white',
                  minWidth: '18px',
                  textAlign: 'center'
                }}>
                  {tab.badge}
                </span>
              )}
              {isActive && variant === 'default' && (
                <div style={{
                  position: 'absolute',
                  bottom: '0',
                  left: '0',
                  right: '0',
                  height: '3px',
                  backgroundColor: 'var(--mac-accent-blue)',
                  borderRadius: '2px 2px 0 0'
                }} />
              )}
            </button>
          );
        })}
      </div>
      {variant === 'default' && (
        <div style={{ 
          borderBottom: '1px solid var(--mac-border)',
          marginTop: '0px'
        }} />
      )}
    </div>
  );
};

export default MacOSTab;