import React, { type CSSProperties } from 'react';

/**
 * ═══════════════════════════════════════════════════════════════════════════════
 * REFACTORED CARD COMPONENT
 * ═══════════════════════════════════════════════════════════════════════════════
 * 
 * Example of migrating a card component to use the unified design system.
 * 
 * Key improvements:
 * 1. Semantic colors that auto-adapt to light/dark mode
 * 2. Unified shadow scale (no custom box-shadow strings)
 * 3. Consistent spacing from the 4px grid
 * 4. Proper border radius from the scale
 * 5. Smooth transitions with system timing
 * 6. Accessibility-first approach
 */

import { useState } from 'react';
import PropTypes from 'prop-types';
const unifiedTheme = { colors: { primary: '#007aff', text: '#000', background: '#fff', secondary: '#f5f5f7' }, spacing: { xs: '4px', sm: '8px', md: '16px', lg: '24px' }, borderRadius: { sm: '4px', md: '8px', lg: '12px' }, shadows: { sm: '0 1px 2px rgba(0,0,0,0.05)', md: '0 4px 6px rgba(0,0,0,0.1)' } } as Record<string, any>;

const { colors, spacing, borderRadius, shadows, typography, transitions } = unifiedTheme;

interface RefactoredCardProps {
  children?: React.ReactNode;
  variant?: 'default' | 'elevated' | 'outlined' | 'filled' | string;
  hoverable?: boolean;
  clickable?: boolean;
  onClick?: (e: React.MouseEvent<HTMLDivElement> | React.KeyboardEvent<HTMLDivElement>) => void;
  header?: React.ReactNode;
  footer?: React.ReactNode;
  title?: React.ReactNode;
  description?: React.ReactNode;
  className?: string;
  style?: CSSProperties;
  [key: string]: unknown;
}

const RefactoredCard = ({
  children,
  variant = 'default',
  hoverable = false,
  clickable = false,
  onClick,
  header,
  footer,
  title,
  description,
  className = '',
  style = {},
  ...props
}: RefactoredCardProps) => {
  const [isHovered, setIsHovered] = useState(false);

  // ═══════════════════════════════════════════════════════════════════
  // VARIANT STYLES (from unified theme)
  // ═══════════════════════════════════════════════════════════════════
  const getVariantStyles = () => {
    const variantMap = {
      // Default card (most common)
      default: {
        bg: colors.semantic.surface.card,
        border: `1px solid ${colors.semantic.border.light}`,
        shadow: shadows.sm,
        hoverShadow: shadows.md,
        hoverTransform: 'translateY(-2px)',
      },

      // Elevated card (more emphasis)
      elevated: {
        bg: colors.semantic.surface.card,
        border: 'none',
        shadow: shadows.md,
        hoverShadow: shadows.lg,
        hoverTransform: 'translateY(-4px)',
      },

      // Outlined card (subtle)
      outlined: {
        bg: 'transparent',
        border: `1px solid ${colors.semantic.border.medium}`,
        shadow: 'none',
        hoverShadow: shadows.sm,
        hoverTransform: 'translateY(-1px)',
      },

      // Success card (positive action/status)
      success: {
        bg: colors.semantic.surface.card,
        border: `2px solid ${colors.status.success}`,
        shadow: shadows.sm,
        hoverShadow: shadows.md,
        hoverTransform: 'translateY(-2px)',
      },

      // Warning card (attention needed)
      warning: {
        bg: colors.semantic.surface.card,
        border: `2px solid ${colors.status.warning}`,
        shadow: shadows.sm,
        hoverShadow: shadows.md,
        hoverTransform: 'translateY(-2px)',
      },

      // Danger card (critical)
      danger: {
        bg: colors.semantic.surface.card,
        border: `2px solid ${colors.status.danger}`,
        shadow: shadows.sm,
        hoverShadow: shadows.md,
        hoverTransform: 'translateY(-2px)',
      },
    };

    return variantMap[variant] || variantMap.default;
  };

  const variantStyles = getVariantStyles();

  // ═══════════════════════════════════════════════════════════════════
  // CARD BASE STYLES (using unified design tokens)
  // ═══════════════════════════════════════════════════════════════════
  const cardStyles = {
    position: 'relative',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: variantStyles.bg,
    border: variantStyles.border,
    borderRadius: borderRadius.lg,  // Cards always use .lg (12px)
    padding: spacing[6],  // Cards always use spacing[6] (24px)
    boxShadow: isHovered && hoverable ? variantStyles.hoverShadow : variantStyles.shadow,
    transition: `all ${transitions.duration.base} ${transitions.easing.smooth}`,
    transform: isHovered && hoverable ? variantStyles.hoverTransform : 'translateY(0)',
    cursor: clickable ? 'pointer' : 'default',
    userSelect: clickable ? 'none' : 'auto',
    overflow: 'hidden',
    ...style,
  };

  const handleCardKeyDown = (event) => {
    if (!clickable) {
      return;
    }

    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onClick?.(event);
    }
  };

  // ═══════════════════════════════════════════════════════════════════
  // HEADER STYLES (if card has header)
  // ═══════════════════════════════════════════════════════════════════
  const headerStyles = {
    display: 'flex',
    flexDirection: 'column',
    gap: spacing[1],  // Small gap between title and description
    marginBottom: spacing[4],  // Spacing between header and content
    paddingBottom: spacing[4],
    borderBottom: `1px solid ${colors.semantic.border.light}`,
  };

  // ═══════════════════════════════════════════════════════════════════
  // BODY STYLES
  // ═══════════════════════════════════════════════════════════════════
  const bodyStyles = {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: spacing[3],  // Gap between elements in card body
  };

  // ═══════════════════════════════════════════════════════════════════
  // FOOTER STYLES (if card has footer)
  // ═══════════════════════════════════════════════════════════════════
  const footerStyles = {
    display: 'flex',
    gap: spacing[3],
    marginTop: spacing[4],
    paddingTop: spacing[4],
    borderTop: `1px solid ${colors.semantic.border.light}`,
  };

  // ═══════════════════════════════════════════════════════════════════
  // TITLE STYLES
  // ═══════════════════════════════════════════════════════════════════
  const titleStyles = {
    margin: 0,
    fontSize: typography.fontSize['2xl'],
    fontWeight: typography.fontWeight.semibold,
    lineHeight: typography.lineHeight.tight,
    color: colors.semantic.text.primary,
    letterSpacing: typography.letterSpacing.normal,
  };

  // ═══════════════════════════════════════════════════════════════════
  // DESCRIPTION STYLES
  // ═══════════════════════════════════════════════════════════════════
  const descriptionStyles = {
    margin: 0,
    fontSize: typography.fontSize.sm,
    lineHeight: typography.lineHeight.normal,
    color: colors.semantic.text.secondary,
  };

  return (
    <article
      className={className}
      style={cardStyles as unknown as CSSProperties}
      onMouseEnter={() => hoverable && setIsHovered(true)}
      onMouseLeave={() => hoverable && setIsHovered(false)}
      onClick={clickable ? (onClick as React.MouseEventHandler<HTMLDivElement>) : undefined}
      onKeyDown={clickable ? handleCardKeyDown : undefined}
      role={clickable ? 'button' : 'region'}
      tabIndex={clickable ? 0 : undefined}
      {...props}
    >
      {/* Header section */}
      {(header || title) && (
        <div style={headerStyles as unknown as CSSProperties}>
          {title && <h2 style={titleStyles as unknown as CSSProperties}>{title}</h2>}
          {description && <p style={descriptionStyles as unknown as CSSProperties}>{description}</p>}
          {header && header}
        </div>
      )}

      {/* Main content */}
      {children && (
        <div style={bodyStyles as unknown as CSSProperties}>
          {children}
        </div>
      )}

      {/* Footer section */}
      {footer && (
        <div style={footerStyles as unknown as CSSProperties}>
          {footer}
        </div>
      )}
    </article>
  );
};

RefactoredCard.propTypes = {
  children: PropTypes.node,
  variant: PropTypes.oneOf(['default', 'elevated', 'outlined', 'success', 'warning', 'danger']),
  hoverable: PropTypes.bool,
  clickable: PropTypes.bool,
  onClick: PropTypes.func,
  header: PropTypes.node,
  footer: PropTypes.node,
  title: PropTypes.string,
  description: PropTypes.string,
  className: PropTypes.string,
  style: PropTypes.object,
};

const RefactoredCardAny = RefactoredCard;

export default RefactoredCard;

// ═══════════════════════════════════════════════════════════════════════════════
// USAGE EXAMPLES
// ═══════════════════════════════════════════════════════════════════════════════

export function CardExamples() {
  const [lastClickedCard, setLastClickedCard] = useState('');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing[6] } as React.CSSProperties}>
      {/* Example 1: Simple card with title */}
      <RefactoredCardAny
        title="Welcome"
        description="This is a simple card with a title and description"
      >
        <p>Card content goes here. Uses unified spacing, colors, and typography.</p>
      </RefactoredCardAny>

      {/* Example 2: Hoverable card */}
      <RefactoredCardAny
        variant="elevated"
        hoverable
        title="Interactive Card"
        description="This card responds to hover"
      >
        <p>Hover over this card to see the elevation effect and smooth transition.</p>
      </RefactoredCardAny>

      {/* Example 3: Clickable card */}
      <RefactoredCardAny
        variant="outlined"
        clickable
        onClick={() => setLastClickedCard('Clickable Card')}
        title="Clickable Card"
      >
        <p>This card is clickable. Click to trigger an action.</p>
      </RefactoredCardAny>

      {lastClickedCard && (
        <p style={{ color: colors.semantic.text.secondary, fontSize: typography.sizes.sm } as React.CSSProperties}>
          Last clicked: {lastClickedCard}
        </p>
      )}

      {/* Example 4: Status card (Success) */}
      <RefactoredCardAny
        variant="success"
        title="✓ Success"
        description="Operation completed successfully"
      >
        <p>This card uses a success variant with green border.</p>
      </RefactoredCardAny>

      {/* Example 5: Card with footer */}
      <RefactoredCardAny
        title="Card with Actions"
        footer={
          <div style={{ display: 'flex', gap: spacing[3], width: '100%' } as React.CSSProperties}>
            <button style={{ flex: 1, padding: spacing[3] } as React.CSSProperties}>Cancel</button>
            <button style={{ flex: 1, padding: spacing[3], background: colors.primary[500], color: 'var(--mac-bg-primary)' } as React.CSSProperties}>
              Save
            </button>
          </div>
        }
      >
        <p>This card has action buttons in the footer.</p>
      </RefactoredCardAny>

      {/* Example 6: Medical department card (Cardiology) */}
      <RefactoredCardAny
        style={{
          borderColor: colors.medical.cardiology,
          borderWidth: '2px',
        } as React.CSSProperties}
        title="Cardiology Appointment"
        description="Scheduled for Feb 28, 2026 at 2:00 PM"
      >
        <div style={{
          padding: spacing[4],
          background: `rgba(${hexToRgb(colors.medical.cardiology)}, 0.1)`,
          borderRadius: borderRadius.md,
        } as React.CSSProperties}>
          <p style={{ margin: 0 } as React.CSSProperties}>Patient: John Doe</p>
          <p style={{ margin: 0 } as React.CSSProperties}>Doctor: Dr. Smith</p>
        </div>
      </RefactoredCardAny>
    </div>
  );
}

// Helper function for example
function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}` : '0, 0, 0';
}
