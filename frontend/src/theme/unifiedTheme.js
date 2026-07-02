/**
 * ═══════════════════════════════════════════════════════════════════════════════
 * UNIFIED DESIGN SYSTEM v2.0
 * ═══════════════════════════════════════════════════════════════════════════════
 * Single source of truth for all design tokens across the medical system.
 * Supports light/dark modes, medical semantics, and premium modern aesthetic.
 * 
 * Architecture:
 * 1. Color System (Base + Medical + Semantic)
 * 2. Typography (Scale, weights, line-heights)
 * 3. Spacing Grid (4px base)
 * 4. Border Radius (Consistent scale)
 * 5. Shadows/Elevation (Soft modern shadows)
 * 6. Transitions/Motion (Consistent timing)
 * 7. Component Overrides (Typography, button, card, input, etc.)
 */

export const unifiedTheme = {
  // ═══════════════════════════════════════════════════════════════════
  // 1. COLOR SYSTEM (Premium + Medical + Semantic)
  // ═══════════════════════════════════════════════════════════════════
  
  colors: {
    // PRIMARY BRAND (Modern Blue - Premium SaaS aesthetic)
    primary: {
      50: '#eff6ff',
      100: '#dbeafe',
      200: '#bfdbfe',
      300: '#93c5fd',
      400: '#60a5fa',
      500: '#3b82f6', // ★ Main brand color
      600: '#2563eb',
      700: '#1d4ed8',
      800: '#1e40af',
      900: '#1e3a8a',
    },

    // SECONDARY (Sophisticated Gray - Modern UI)
    secondary: {
      50: '#f9fafb',
      100: '#f3f4f6',
      200: '#e5e7eb',
      300: '#d1d5db',
      400: '#9ca3af',
      500: '#6b7280',
      600: '#4b5563',
      700: '#374151',
      800: '#1f2937',
      900: '#111827',
    },

    // STATUS COLORS (Semantic medical)
    status: {
      success: '#10b981',   // Soft green - Treatment success, completed
      warning: '#f59e0b',   // Amber - Pending, needs attention
      danger: '#ef4444',    // Red - Emergency, critical
      info: '#06b6d4',      // Cyan - Informational
      neutral: '#6b7280',   // Gray - Neutral state
    },

    // MEDICAL DEPARTMENT COLORS (Specialty-specific)
    medical: {
      cardiology: '#dc2626',     // Vibrant red → Heart ♥
      dermatology: '#8b5cf6',    // Purple → Skin
      dentistry: '#059669',      // Forest green → Teeth
      laboratory: '#0891b2',     // Teal → Science/Labs
      neurology: '#a855f7',      // Magenta → Brain
      gynecology: '#ec4899',     // Pink → Reproductive
      pediatrics: '#f59e0b',     // Warm amber → Children
      surgery: '#7c2d12',        // Dark red → Surgical
      psychiatry: '#7c3aed',     // Indigo → Mind
      radiology: '#64748b',      // Gray-blue → Imaging
      ophthalmology: '#06b6d4',  // Cyan → Eyes
      general: '#3b82f6',        // Primary blue → General medicine
    },

    // SEMANTIC COLORS (Context-aware)
    semantic: {
      text: {
        primary: '#111827',     // Light mode: Dark text
        secondary: '#374151',   // Light mode: Medium text
        tertiary: '#6b7280',    // Light mode: Muted text
        inverse: '#ffffff',     // For dark backgrounds
        disabled: '#9ca3af',    // Disabled state
      },
      background: {
        primary: '#ffffff',     // Page/primary background
        secondary: '#f9fafb',   // Secondary/surface
        tertiary: '#f3f4f6',    // Tertiary/hover
        elevated: '#ffffff',    // Cards/dialogs
        overlay: 'rgba(0, 0, 0, 0.5)',
        disabled: '#f3f4f6',
      },
      border: {
        light: '#e5e7eb',
        medium: '#d1d5db',
        dark: '#9ca3af',
        focus: '#3b82f6',
        error: '#ef4444',
      },
      surface: {
        card: '#ffffff',
        input: '#ffffff',
        hover: '#f9fafb',
        active: '#f3f4f6',
        selected: '#eff6ff',
      },
    },

    // DARK MODE OVERRIDES
    dark: {
      text: {
        primary: '#f9fafb',
        secondary: '#d1d5db',
        tertiary: '#9ca3af',
        inverse: '#111827',
        disabled: '#6b7280',
      },
      background: {
        primary: '#0f172a',
        secondary: '#1e293b',
        tertiary: '#334155',
        elevated: '#1e293b',
        overlay: 'rgba(0, 0, 0, 0.8)',
        disabled: '#1f2937',
      },
      border: {
        light: '#475569',
        medium: '#334155',
        dark: '#1e293b',
        focus: '#60a5fa',
        error: '#fca5a5',
      },
      surface: {
        card: '#1e293b',
        input: '#334155',
        hover: '#334155',
        active: '#475569',
        selected: '#1e40af',
      },
    },
  },

  // ═══════════════════════════════════════════════════════════════════
  // 2. TYPOGRAPHY (Modern, Readable, Accessible)
  // ═══════════════════════════════════════════════════════════════════

  typography: {
    // Font families (System fonts for performance)
    fontFamily: {
      sans: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      mono: '"SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace',
      display: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    },

    // Type scale (8-point based, readable hierarchy)
    fontSize: {
      xs: '12px',      // Captions, tags, badges
      sm: '14px',      // Secondary text, labels
      base: '16px',    // Body text, default
      lg: '18px',      // Body emphasis
      xl: '20px',      // Subheadings
      '2xl': '24px',   // Section headings
      '3xl': '30px',   // Page headings
      '4xl': '36px',   // Major headings
      '5xl': '48px',   // Display text
    },

    // Font weights
    fontWeight: {
      normal: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
      extrabold: 800,
    },

    // Line heights (for optimal readability)
    lineHeight: {
      tight: 1.25,
      normal: 1.5,
      relaxed: 1.75,
      loose: 2,
    },

    // Letter spacing (subtle refinement)
    letterSpacing: {
      tight: '-0.02em',
      normal: '0em',
      wide: '0.02em',
    },

    // Preset styles (semantic text styles)
    styles: {
      h1: {
        fontSize: '36px',
        fontWeight: 700,
        lineHeight: 1.2,
        letterSpacing: '-0.02em',
      },
      h2: {
        fontSize: '30px',
        fontWeight: 600,
        lineHeight: 1.3,
        letterSpacing: '-0.01em',
      },
      h3: {
        fontSize: '24px',
        fontWeight: 600,
        lineHeight: 1.4,
        letterSpacing: '0em',
      },
      h4: {
        fontSize: '20px',
        fontWeight: 600,
        lineHeight: 1.4,
      },
      h5: {
        fontSize: '18px',
        fontWeight: 600,
        lineHeight: 1.5,
      },
      h6: {
        fontSize: '16px',
        fontWeight: 600,
        lineHeight: 1.5,
      },
      body: {
        fontSize: '16px',
        fontWeight: 400,
        lineHeight: 1.5,
      },
      bodySmall: {
        fontSize: '14px',
        fontWeight: 400,
        lineHeight: 1.5,
      },
      label: {
        fontSize: '14px',
        fontWeight: 500,
        lineHeight: 1.4,
      },
      caption: {
        fontSize: '12px',
        fontWeight: 400,
        lineHeight: 1.4,
      },
    },
  },

  // ═══════════════════════════════════════════════════════════════════
  // 3. SPACING GRID (4px base = 0.25rem)
  // ═══════════════════════════════════════════════════════════════════

  spacing: {
    0: '0px',
    1: '4px',
    2: '8px',
    3: '12px',
    4: '16px',
    5: '20px',
    6: '24px',
    7: '28px',
    8: '32px',
    9: '36px',
    10: '40px',
    12: '48px',
    14: '56px',
    16: '64px',
    20: '80px',
    24: '96px',
    28: '112px',
    32: '128px',
    36: '144px',
    40: '160px',
    44: '176px',
    48: '192px',
    52: '208px',
    56: '224px',
    60: '240px',
    64: '256px',
  },

  // ═══════════════════════════════════════════════════════════════════
  // 4. BORDER RADIUS (Modern, consistent scale)
  // ═══════════════════════════════════════════════════════════════════

  borderRadius: {
    none: '0px',
    sm: '4px',
    base: '6px',     // ★ Default for small elements
    md: '8px',       // ★ Default for medium elements
    lg: '12px',      // Cards, larger components
    xl: '16px',      // Modals, large cards
    '2xl': '20px',   // Special emphasis
    '3xl': '24px',   // Largest containers
    full: '9999px',  // Fully rounded (pills, circles)
  },

  // ═══════════════════════════════════════════════════════════════════
  // 5. SHADOWS / ELEVATION (Soft, modern, layered)
  // ═══════════════════════════════════════════════════════════════════

  shadows: {
    none: 'none',
    xs: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    sm: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)',
    base: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
    md: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)',
    lg: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
    xl: '0 25px 50px -12px rgba(0, 0, 0, 0.15)',
    '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
    inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.05)',
    // Special: Dark mode shadows (darker overlay)
    darkSm: '0 1px 3px 0 rgba(0, 0, 0, 0.3)',
    darkMd: '0 10px 15px -3px rgba(0, 0, 0, 0.4)',
    darkLg: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
  },

  // ═══════════════════════════════════════════════════════════════════
  // 6. TRANSITIONS & MOTION (Consistent, accessible)
  // ═══════════════════════════════════════════════════════════════════

  transitions: {
    duration: {
      fast: '100ms',
      base: '150ms',
      slow: '200ms',
      slower: '300ms',
      slowest: '500ms',
    },
    easing: {
      in: 'cubic-bezier(0.4, 0, 1, 1)',
      out: 'cubic-bezier(0, 0, 0.2, 1)',
      inOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
      linear: 'linear',
      // Bounce
      bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
      // Smooth (design system favorite)
      smooth: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
    },
  },

  // ═══════════════════════════════════════════════════════════════════
  // 7. RESPONSIVE BREAKPOINTS
  // ═══════════════════════════════════════════════════════════════════

  breakpoints: {
    xs: '320px',
    sm: '640px',
    md: '768px',
    lg: '1024px',
    xl: '1280px',
    '2xl': '1536px',
  },

  // ═══════════════════════════════════════════════════════════════════
  // 8. Z-INDEX SCALE
  // ═══════════════════════════════════════════════════════════════════

  zIndex: {
    hide: -1,
    base: 0,
    dropdown: 1000,
    sticky: 1020,
    fixed: 1030,
    backdrop: 1040,
    modal: 1050,
    popover: 1060,
    tooltip: 1070,
  },

  // ═══════════════════════════════════════════════════════════════════
  // 9. COMPONENT PRESETS (Ready-to-use combinations)
  // ═══════════════════════════════════════════════════════════════════

  components: {
    // BUTTON PRESETS
    button: {
      primary: {
        bg: '#3b82f6',
        text: '#ffffff',
        hover: '#2563eb',
        active: '#1d4ed8',
        disabled: '#d1d5db',
        disabledText: '#9ca3af',
        border: 'transparent',
        shadow: '0 4px 6px -1px rgba(59, 130, 246, 0.3)',
      },
      secondary: {
        bg: '#f3f4f6',
        text: '#111827',
        hover: '#e5e7eb',
        active: '#d1d5db',
        disabled: '#f3f4f6',
        disabledText: '#9ca3af',
        border: '#d1d5db',
        shadow: 'none',
      },
      danger: {
        bg: '#ef4444',
        text: '#ffffff',
        hover: '#dc2626',
        active: '#b91c1c',
        disabled: '#fecaca',
        disabledText: '#9ca3af',
        border: 'transparent',
        shadow: '0 4px 6px -1px rgba(239, 68, 68, 0.3)',
      },
      success: {
        bg: '#10b981',
        text: '#ffffff',
        hover: '#059669',
        active: '#047857',
        disabled: '#bbf7d0',
        disabledText: '#9ca3af',
        border: 'transparent',
        shadow: '0 4px 6px -1px rgba(16, 185, 129, 0.3)',
      },
      ghost: {
        bg: 'transparent',
        text: '#3b82f6',
        hover: '#eff6ff',
        active: '#dbeafe',
        disabled: 'transparent',
        disabledText: '#9ca3af',
        border: 'transparent',
        shadow: 'none',
      },
      outline: {
        bg: 'transparent',
        text: '#3b82f6',
        hover: '#eff6ff',
        active: '#dbeafe',
        disabled: 'transparent',
        disabledText: '#9ca3af',
        border: '#3b82f6',
        shadow: 'none',
      },
    },

    // CARD PRESETS
    card: {
      default: {
        bg: '#ffffff',
        border: '#e5e7eb',
        shadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
        hover: 'translateY(-2px)',
        hoverShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
      },
      elevated: {
        bg: '#ffffff',
        border: 'transparent',
        shadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        hover: 'translateY(-4px)',
        hoverShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.15)',
      },
      outlined: {
        bg: 'transparent',
        border: '#d1d5db',
        shadow: 'none',
        hover: 'translateY(-1px)',
        hoverShadow: 'none',
      },
    },

    // INPUT PRESETS
    input: {
      default: {
        bg: '#ffffff',
        text: '#111827',
        border: '#d1d5db',
        placeholder: '#9ca3af',
        focus: '#3b82f6',
        focusBorder: '#3b82f6',
        focusShadow: '0 0 0 3px rgba(59, 130, 246, 0.1)',
      },
      disabled: {
        bg: '#f3f4f6',
        text: '#9ca3af',
        border: '#e5e7eb',
        placeholder: '#d1d5db',
      },
    },
  },
};

export default unifiedTheme;
