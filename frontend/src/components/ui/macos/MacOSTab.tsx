import PropTypes from 'prop-types';
import { useTranslation } from '../../../i18n/useTranslation';
import type { CSSProperties, ReactNode, ComponentType, KeyboardEvent, MouseEvent as ReactMouseEvent, FocusEvent } from 'react';

type TabSize = 'sm' | 'md' | 'lg';
type TabVariant = 'default' | 'filled' | 'pills';
type TabOrientation = 'horizontal' | 'vertical';
type TabId = string | number;

interface TabIconProps {
  style?: CSSProperties;
}

interface TabDefinition {
  id: TabId;
  label: ReactNode;
  icon?: ComponentType<TabIconProps> | string;
  badge?: ReactNode;
  disabled?: boolean;
}

interface MacOSTabProps {
  tabs: TabDefinition[];
  activeTab: TabId;
  onTabChange: (id: TabId) => void;
  size?: TabSize | string;
  variant?: TabVariant | string;
  orientation?: TabOrientation;
  className?: string;
  style?: CSSProperties;
  id?: string;
  labelledby?: string;
  role?: string;
}

interface TabSizeStyle extends CSSProperties {
  gap?: string;
}

interface TabVariantStyle extends CSSProperties {
  gap?: string;
}

interface TabButtonStyle extends CSSProperties {
  transition?: string;
}

const MacOSTab = ({
  tabs,
  activeTab,
  onTabChange,
  size = 'md',
  variant = 'default',
  orientation = 'horizontal',
  className,
  style
}: MacOSTabProps) => {
  const { t } = useTranslation();
  void t;
  void orientation;
  const sizeStyles: Record<TabSize, TabSizeStyle> = {
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

  const variantStyles: Record<TabVariant, TabVariantStyle> = {
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

  const containerStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    marginBottom: variant === 'default' ? '24px' : '0',
    ...currentVariant,
    ...style
  };

  const tabButtonStyle = (isActive: boolean): TabButtonStyle => ({
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

  const handleTabClick = (tabId: TabId) => {
    onTabChange(tabId);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>, tabId: TabId) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onTabChange(tabId);
    }
  };

  const handleMouseEnter = (e: ReactMouseEvent<HTMLButtonElement>, isActive: boolean) => {
    if (!isActive) {
      e.currentTarget.style.color = 'var(--mac-text-primary)';
      if (variant === 'filled') {
        e.currentTarget.style.background = 'var(--mac-bg-tertiary)';
      }
    }
  };

  const handleMouseLeave = (e: ReactMouseEvent<HTMLButtonElement>, isActive: boolean) => {
    if (!isActive) {
      e.currentTarget.style.color = 'var(--mac-text-secondary)';
      if (variant === 'filled') {
        e.currentTarget.style.background = 'transparent';
      }
    }
  };

  const handleFocus = (_e: FocusEvent<HTMLButtonElement>) => {
    // Ничего не делаем - убираем все эффекты фокуса
  };
  const handleBlur = (_e: FocusEvent<HTMLButtonElement>) => {
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
              tabIndex={isActive ? 0 : -1}>

              {IconComponent &&
              <IconComponent
                style={{
                  width: size === 'sm' ? '14px' : size === 'md' ? '16px' : '18px',
                  height: size === 'sm' ? '14px' : size === 'md' ? '16px' : '18px',
                  marginRight: '8px',
                  color: 'inherit'
                }} />

              }
              {tab.label}
              {tab.badge &&
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
              }
              {isActive && variant === 'default' &&
              <div style={{
                position: 'absolute',
                bottom: '0',
                left: '0',
                right: '0',
                height: '3px',
                backgroundColor: 'var(--mac-accent-blue)',
                borderRadius: '2px 2px 0 0'
              }} />
              }
            </button>);

        })}
      </div>
      {variant === 'default' &&
      <div style={{
        borderBottom: '1px solid var(--mac-border)',
        marginTop: '0px'
      }} />
      }
    </div>);

};


MacOSTab.propTypes = {
  ...(MacOSTab.propTypes || {}),
  activeTab: PropTypes.any,
  className: PropTypes.any,
  map: PropTypes.any,
  onTabChange: PropTypes.any,
  orientation: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
  tabs: PropTypes.any,
  variant: PropTypes.any,
};

export default MacOSTab;
