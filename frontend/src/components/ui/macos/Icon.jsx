import React from 'react';
import { useTheme } from '../../../contexts/ThemeContext';

/**
 * macOS-style Icon Component
 * Implements SF Symbols-like icons with consistent styling
 */

// SF Symbols-like icon definitions (simplified SVG paths)
const ICONS = {
  // Navigation & UI
  'house': (
    <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/>
  ),
  'house.fill': (
    <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/>
  ),
  'magnifyingglass': (
    <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
  ),
  'plus': (
    <path d="M12 4v16m8-8H4"/>
  ),
  'minus': (
    <path d="M4 12h16"/>
  ),
  'xmark': (
    <path d="M18 6L6 18M6 6l12 12"/>
  ),
  'checkmark': (
    <path d="M20 6L9 17l-5-5"/>
  ),
  'chevron.left': (
    <path d="M15 18l-6-6 6-6"/>
  ),
  'chevron.right': (
    <path d="M9 18l6-6-6-6"/>
  ),
  'chevron.up': (
    <path d="M18 15l-6-6-6 6"/>
  ),
  'chevron.down': (
    <path d="M6 9l6 6 6-6"/>
  ),

  // User & People
  'person': (
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
  ),
  'person.fill': (
    <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
  ),
  'person.circle': (
    <circle cx="12" cy="8" r="4" fill="none"/>
  ),

  // Communication
  'envelope': (
    <path d="M3 8l7.89 4.26a2 2 0 0 0 2.22 0L21 8M5 19h14a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2z"/>
  ),
  'phone': (
    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
  ),

  // Interface Elements
  'gear': (
    <path d="M12 15.5A3.5 3.5 0 0 1 8.5 12A3.5 3.5 0 0 1 12 8.5a3.5 3.5 0 0 1 3.5 3.5 3.5 3.5 0 0 1-3.5 3.5zm7.43-2.53c.04-.32.07-.64.07-.97 0-.33-.03-.66-.07-1l2.11-1.63c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.31-.61-.22l-2.49 1c-.52-.39-1.06-.73-1.69-.98l-.37-2.65A.506.506 0 0 0 14 2h-4c-.25 0-.46.18-.5.42l-.37 2.65c-.63.25-1.17.59-1.69.98l-2.49-1c-.22-.09-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64L4.57 11c-.04.34-.07.67-.07 1 0 .33.03.65.07.97l-2.11 1.66c-.19.15-.25.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1.01c.52.4 1.06.74 1.69.99l.37 2.65c.04.24.25.42.5.42h4c.25 0 .46-.18.5-.42l.37-2.65c.63-.26 1.17-.59 1.69-.99l2.49 1.01c.22.08.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.66zM12 15.5A3.5 3.5 0 0 1 8.5 12A3.5 3.5 0 0 1 12 8.5a3.5 3.5 0 0 1 3.5 3.5 3.5 3.5 0 0 1-3.5 3.5z"/>
  ),
  'bell': (
    <path d="M18 13v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a8 8 0 1 1 16 0zM9 19h6v2H9v-2z"/>
  ),
  'bell.fill': (
    <path d="M18 13v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a8 8 0 1 1 16 0z"/>
  ),

  // Media & Content
  'play': (
    <path d="M8 5v14l11-7z"/>
  ),
  'pause': (
    <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
  ),
  'photo': (
    <path d="M4 16l4.586-4.586a2 2 0 0 1 2.828 0L16 16m-2-2l1.586-1.586a2 2 0 0 1 2.828 0L20 14m-6-6h.01M6 20h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2z"/>
  ),

  // Medical & Healthcare
  'heart': (
    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
  ),
  'heart.fill': (
    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
  ),
  'stethoscope': (
    <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.29 1.51 4.04 3 5.5V19a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5z"/>
  ),
  'pills': (
    <path d="M19.5 12c.9-1.9 1.5-4.1 1.5-6.5A7.5 7.5 0 0 0 13.5 0c-2.4 0-4.6.6-6.5 1.5M12 12l-8-8M8 8l8 8"/>
  ),

  // Actions & Controls
  'pencil': (
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
  ),
  'trash': (
    <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
  ),
  'eye': (
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
  ),
  'eye.slash': (
    <path d="M13.875 18.825A10.05 10.05 0 0 1 12 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 0 1 1.563-3.029m5.858.908a3 3 0 1 1 4.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L21 21"/>
  ),

  // Status & Feedback
  'exclamationmark.triangle': (
    <path d="M12 9v3m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"/>
  ),
  'checkmark.circle': (
    <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
  ),
  'xmark.circle': (
    <path d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/>
  ),

  // Charts & Data
  'chart.bar': (
    <path d="M12 2v20m8-10V8m-8 4v10m-8-6v6"/>
  ),
  'chart.pie': (
    <path d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9c0 1.657-4.03 3-9 3s-9-1.343-9-3m18 0c0-1.657-4.03-3-9-3s-9 1.343-9 3"/>
  ),

  // Weather & Environment
  'sun.max': (
    <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
  ),
  'cloud': (
    <path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>
  ),

  // Transport & Travel
  'car': (
    <path d="M14 16c0 .88-.39 1.67-1 2.22V20a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2v-1.78c.61-.55 1-1.34 1-2.22V8a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v6c0 .88.39 1.67 1 2.22V20a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2v-1.78c-.61-.55-1-1.34-1-2.22z"/>
  ),
  'airplane': (
    <path d="M17.8 19.2L16.8 8.9c0-.2-.1-.3-.2-.4l-1.1-.9c-.2-.1-.3-.1-.5 0l-1.1.9c-.1.1-.2.2-.2.4l-1 10.3c0 .2 0 .4.1.5l.7.7c.1.1.3.1.4 0l2.3-2.3c.1-.1.2-.1.3 0l2.3 2.3c.1.1.3.1.4 0l.7-.7c.1-.1.1-.3.1-.5z"/>
  ),

  // Objects & Tools
  'wrench': (
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
  ),
  'hammer': (
    <path d="M15 12a3 3 0 0 1-3 3l-6-6a3 3 0 0 1 3-3l6 6zM8 9l6 6M13 4l-2-2M9 6l-2-2"/>
  ),

  // Symbols & Shapes
  'star': (
    <path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 0 0 .95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 0 0-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 0 0-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 0 0-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 0 0 .951-.69l1.519-4.674z"/>
  ),
  'star.fill': (
    <path d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 0 0 .95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 0 0-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 0 0-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 0 0-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 0 0 .951-.69l1.519-4.674z"/>
  ),

  // Default fallback
  'questionmark': (
    <path d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
  )
};

/**
 * macOS-style Icon Component
 */
const Icon = React.forwardRef(({
  name,
  size = 'default',
  color = 'default',
  className = '',
  style = {},
  ...props
}, ref) => {
  const { theme } = useTheme();

  // Size mapping
  const sizeMap = {
    small: 16,
    default: 20,
    large: 24,
    xlarge: 32
  };

  const iconSize = sizeMap[size] || sizeMap.default;

  // Color mapping
  const colorMap = {
    default: 'var(--mac-text-secondary)',
    primary: '#007aff',
    secondary: 'var(--mac-text-secondary)',
    success: '#34c759',
    warning: '#ff9500',
    danger: '#ff3b30',
    white: 'white',
    black: 'black'
  };

  const iconColor = colorMap[color] || colorMap.default;

  // Get the icon SVG
  const iconPath = ICONS[name] || ICONS['questionmark'];

  const iconStyles = {
    display: 'inline-block',
    width: `${iconSize}px`,
    height: `${iconSize}px`,
    color: iconColor,
    flexShrink: 0,
    ...style
  };

  return (
    <svg
      ref={ref}
      className={`mac-icon ${className}`}
      style={iconStyles}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {iconPath}
    </svg>
  );
});

Icon.displayName = 'macOS Icon';

export default Icon;
