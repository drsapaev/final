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

import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { unifiedTheme } from '@/theme/unifiedTheme';

const { colors, spacing, borderRadius, shadows, typography, transitions } = unifiedTheme;

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
}) => {
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
      style={cardStyles}
      onMouseEnter={() => hoverable && setIsHovered(true)}
      onMouseLeave={() => hoverable && setIsHovered(false)}
      onClick={clickable ? onClick : undefined}
      role={clickable ? 'button' : 'region'}
      {...props}
    >
      {/* Header section */}
      {(header || title) && (
        <div style={headerStyles}>
          {title && <h2 style={titleStyles}>{title}</h2>}
          {description && <p style={descriptionStyles}>{description}</p>}
          {header && header}
        </div>
      )}

      {/* Main content */}
      {children && (
        <div style={bodyStyles}>
          {children}
        </div>
      )}

      {/* Footer section */}
      {footer && (
        <div style={footerStyles}>
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

export default RefactoredCard;

// ═══════════════════════════════════════════════════════════════════════════════
// USAGE EXAMPLES
// ═══════════════════════════════════════════════════════════════════════════════

export function CardExamples() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing[6] }}>
      {/* Example 1: Simple card with title */}
      <RefactoredCard
        title="Welcome"
        description="This is a simple card with a title and description"
      >
        <p>Card content goes here. Uses unified spacing, colors, and typography.</p>
      </RefactoredCard>

      {/* Example 2: Hoverable card */}
      <RefactoredCard
        variant="elevated"
        hoverable
        title="Interactive Card"
        description="This card responds to hover"
      >
        <p>Hover over this card to see the elevation effect and smooth transition.</p>
      </RefactoredCard>

      {/* Example 3: Clickable card */}
      <RefactoredCard
        variant="outlined"
        clickable
        title="Clickable Card"
      >
        <p>This card is clickable. Click to trigger an action.</p>
      </RefactoredCard>

      {/* Example 4: Status card (Success) */}
      <RefactoredCard
        variant="success"
        title="✓ Success"
        description="Operation completed successfully"
      >
        <p>This card uses a success variant with green border.</p>
      </RefactoredCard>

      {/* Example 5: Card with footer */}
      <RefactoredCard
        title="Card with Actions"
        footer={
          <div style={{ display: 'flex', gap: spacing[3], width: '100%' }}>
            <button style={{ flex: 1, padding: spacing[3] }}>Cancel</button>
            <button style={{ flex: 1, padding: spacing[3], background: colors.primary[500], color: '#fff' }}>
              Save
            </button>
          </div>
        }
      >
        <p>This card has action buttons in the footer.</p>
      </RefactoredCard>

      {/* Example 6: Medical department card (Cardiology) */}
      <RefactoredCard
        style={{
          borderColor: colors.medical.cardiology,
          borderWidth: '2px',
        }}
        title="Cardiology Appointment"
        description="Scheduled for Feb 28, 2026 at 2:00 PM"
      >
        <div style={{
          padding: spacing[4],
          background: `rgba(${hexToRgb(colors.medical.cardiology)}, 0.1)`,
          borderRadius: borderRadius.md,
        }}>
          <p style={{ margin: 0 }}>Patient: John Doe</p>
          <p style={{ margin: 0 }}>Doctor: Dr. Smith</p>
        </div>
      </RefactoredCard>
    </div>
  );
}

// Helper function for example
function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}` : '0, 0, 0';
}
