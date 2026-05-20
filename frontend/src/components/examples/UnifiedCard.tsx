/**
 * Unified Card Component
 * Example of a macOS-native card pattern using existing clinic tokens.
 *
 * This example is intentionally MUI-free. Clinic runtime UI should prefer
 * frontend/src/components/ui/macos before copying example code.
 */

import React from 'react';

type CardVariant = 'elevated' | 'outlined' | 'filled' | 'soft' | 'glass' | 'interactive';
type UnifiedCardSize = 'sm' | 'md' | 'lg';

interface UnifiedCardProps {
  variant?: CardVariant;
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
  onClick?: () => void;
  interactive?: boolean;
  size?: UnifiedCardSize;
  className?: string;
  style?: React.CSSProperties;
}

const sizePadding: Record<UnifiedCardSize, string> = {
  sm: '12px',
  md: '16px',
  lg: '24px',
};

const baseCardStyle: React.CSSProperties = {
  position: 'relative',
  overflow: 'hidden',
  borderRadius: 'var(--mac-radius-lg)',
  color: 'var(--mac-text-primary)',
  fontFamily: 'var(--mac-font-family, -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif)',
  transition: 'box-shadow var(--mac-duration-normal) var(--mac-ease), border-color var(--mac-duration-normal) var(--mac-ease), background-color var(--mac-duration-normal) var(--mac-ease), transform var(--mac-duration-fast) var(--mac-ease)',
  outlineOffset: 2,
};

const variantStyles: Record<CardVariant, React.CSSProperties> = {
  elevated: {
    background: 'var(--mac-card-bg, var(--mac-bg-primary))',
    border: '1px solid var(--mac-border-secondary)',
    boxShadow: 'var(--mac-shadow-md)',
  },
  outlined: {
    background: 'var(--mac-card-bg, var(--mac-bg-primary))',
    border: '1px solid var(--mac-card-border, var(--mac-border))',
    boxShadow: 'none',
  },
  filled: {
    background: 'var(--mac-bg-tertiary)',
    border: '1px solid var(--mac-border-secondary)',
    boxShadow: 'none',
  },
  soft: {
    background: 'var(--mac-accent-bg, rgba(0, 122, 255, 0.08))',
    border: '1px solid var(--mac-accent-border, rgba(0, 122, 255, 0.22))',
    boxShadow: 'none',
  },
  glass: {
    background: 'var(--mac-glass-bg, rgba(255, 255, 255, 0.72))',
    border: '1px solid var(--mac-glass-border, rgba(255, 255, 255, 0.58))',
    boxShadow: 'var(--mac-shadow-sm)',
    backdropFilter: 'var(--mac-blur-light)',
    WebkitBackdropFilter: 'var(--mac-blur-light)',
  },
  interactive: {
    background: 'var(--mac-card-bg, var(--mac-bg-primary))',
    border: '1px solid var(--mac-card-border, var(--mac-border))',
    boxShadow: 'var(--mac-shadow-sm)',
  },
};

const titleStyle: React.CSSProperties = {
  margin: 0,
  color: 'var(--mac-text-primary)',
  fontSize: 'var(--mac-font-size-lg)',
  fontWeight: 'var(--mac-font-weight-semibold)',
  lineHeight: 1.25,
};

const subtitleStyle: React.CSSProperties = {
  margin: '4px 0 0',
  color: 'var(--mac-text-secondary)',
  fontSize: 'var(--mac-font-size-sm)',
  lineHeight: 1.4,
};

const bodyTextStyle: React.CSSProperties = {
  margin: 0,
  color: 'var(--mac-text-secondary)',
  fontSize: 'var(--mac-font-size-base)',
  lineHeight: 1.55,
};

const actionButtonStyle: React.CSSProperties = {
  minHeight: 32,
  borderRadius: 'var(--mac-radius-md)',
  border: '1px solid var(--mac-border)',
  background: 'var(--mac-bg-secondary)',
  color: 'var(--mac-text-primary)',
  padding: '8px 14px',
  font: 'inherit',
  cursor: 'pointer',
};

export const UnifiedCard = React.forwardRef<HTMLDivElement, UnifiedCardProps>(
  (
    {
      variant = 'outlined',
      title,
      subtitle,
      children,
      actions,
      onClick,
      interactive = false,
      size = 'md',
      className = '',
      style,
    },
    ref
  ) => {
    const isInteractive = Boolean(interactive || onClick || variant === 'interactive');

    const cardStyle: React.CSSProperties = {
      ...baseCardStyle,
      ...variantStyles[variant],
      padding: sizePadding[size],
      cursor: isInteractive ? 'pointer' : 'default',
      ...style,
    };

    const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (!isInteractive || !onClick) return;

      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        onClick();
      }
    };

    const content = (
      <>
        {(title || subtitle) && (
          <header
            style={{
              paddingBottom: children ? '12px' : 0,
              borderBottom: children ? '1px solid var(--mac-separator)' : undefined,
              marginBottom: children ? '14px' : 0,
            }}
          >
            {title && <h3 style={titleStyle}>{title}</h3>}
            {subtitle && <p style={subtitleStyle}>{subtitle}</p>}
          </header>
        )}

        <section>{children}</section>

        {actions && (
          <footer
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '8px',
              flexWrap: 'wrap',
              marginTop: '16px',
              paddingTop: '12px',
              borderTop: '1px solid var(--mac-separator)',
            }}
          >
            {actions}
          </footer>
        )}
      </>
    );

    if (isInteractive) {
      return (
        <div
          ref={ref}
          className={className}
          role="button"
          tabIndex={0}
          onClick={onClick}
          onKeyDown={handleKeyDown}
          style={cardStyle}
        >
          {content}
        </div>
      );
    }

    return (
      <div
        ref={ref}
        className={className}
        style={cardStyle}
      >
        {content}
      </div>
    );
  }
);

UnifiedCard.displayName = 'UnifiedCard';

export const UnifiedCardShowcase = () => {
  return (
    <div
      style={{
        display: 'grid',
        gap: '24px',
        padding: '24px',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
      }}
    >
      <UnifiedCard variant="elevated" title="Elevated Card" subtitle="With shadow">
        <p style={bodyTextStyle}>This card has a quiet shadow for high-level summaries.</p>
      </UnifiedCard>

      <UnifiedCard variant="outlined" title="Outlined Card" subtitle="Minimal style">
        <p style={bodyTextStyle}>This card uses a border for definition without extra visual weight.</p>
      </UnifiedCard>

      <UnifiedCard variant="filled" title="Filled Card" subtitle="Background colored">
        <p style={bodyTextStyle}>This card uses a filled surface for secondary grouped content.</p>
      </UnifiedCard>

      <UnifiedCard variant="soft" title="Soft Card" subtitle="Subtle accent">
        <p style={bodyTextStyle}>This card uses the accent background for low-risk informational emphasis.</p>
      </UnifiedCard>

      <UnifiedCard variant="glass" title="Glass Card" subtitle="Blurred surface">
        <p style={bodyTextStyle}>This card demonstrates a restrained glass surface for demo contexts.</p>
      </UnifiedCard>

      <UnifiedCard
        variant="interactive"
        title="Interactive Card"
        subtitle="Keyboard reachable"
        onClick={() => undefined}
      >
        <p style={bodyTextStyle}>This card exposes button semantics and handles Enter or Space.</p>
      </UnifiedCard>

      <UnifiedCard
        variant="outlined"
        title="Card with Actions"
        subtitle="Contains buttons"
        actions={
          <>
            <button type="button" style={actionButtonStyle}>Cancel</button>
            <button
              type="button"
              style={{
                ...actionButtonStyle,
                background: 'var(--mac-accent-blue)',
                borderColor: 'var(--mac-accent-blue)',
                color: 'var(--mac-text-on-accent)',
              }}
            >
              Save
            </button>
          </>
        }
      >
        <p style={bodyTextStyle}>This card demonstrates an accessible footer action row.</p>
      </UnifiedCard>

      <UnifiedCard variant="elevated" title="Large Card" size="lg">
        <h4
          style={{
            margin: '0 0 8px',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-base)',
            fontWeight: 'var(--mac-font-weight-semibold)',
          }}
        >
          Medical Department Card
        </h4>
        <p style={bodyTextStyle}>
          This larger card can describe patient records, diagnostic summaries, or department details
          without relying on MUI.
        </p>
      </UnifiedCard>
    </div>
  );
};
